"""
FinMind API client — thin wrapper around the REST endpoint with async batch support.

Prefer `get_multi(...)` over looping `get(...)` for peer analysis: it hits the
API concurrently and returns a dict keyed by stock_id. This is the single most
important performance lever when comparing a candidate against a peer set.

Usage:
    client = FinMindClient(token=load_token())
    df = client.get('TaiwanStockFinancialStatements', stock_id='2330', start_date='2020-01-01')
    panel = client.get_multi('TaiwanStockMonthRevenue', stock_ids=['2330', '2303'], start_date='2023-01-01')
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd
import requests

from taiwan_equity_toolkit.config import (
    FINMIND_BASE_URL,
    FINMIND_USER_INFO_URL,
    MAX_RETRIES,
    PREMIUM_DATASETS,
    RATE_LIMIT_PER_HOUR,
    RETRY_BACKOFF_SEC,
    DEFAULT_TIMEOUT_SEC,
)

log = logging.getLogger(__name__)


class FinMindError(Exception):
    """Raised when the API returns an error or response is unparseable."""


class RateLimitExceeded(FinMindError):
    """API quota exhausted."""


class PremiumDatasetRequired(FinMindError):
    """Raised when a premium (Backer/Sponsor) dataset is requested on a
    free-tier client.

    This replaces the previous behaviour of letting the HTTP call 400 silently.
    Callers in V2 catch this and surface Status.NOT_ASSESSED with a clear note.
    """


def is_premium(dataset: str) -> bool:
    """Return True if dataset is Backer/Sponsor-only on FinMind.

    Consulted by FinMindClient.get() before every HTTP call so free-tier runs
    never silently 400 on a tier-locked endpoint.
    """
    return dataset in PREMIUM_DATASETS


@dataclass
class UsageInfo:
    user_count: int
    api_request_limit: int

    @property
    def remaining(self) -> int:
        return self.api_request_limit - self.user_count

    @property
    def utilization_pct(self) -> float:
        if self.api_request_limit == 0:
            return 0.0
        return self.user_count / self.api_request_limit


class FinMindClient:
    """FinMind REST client with retry, rate-limit awareness, and async batching."""

    def __init__(
        self,
        token: str,
        base_url: str = FINMIND_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT_SEC,
        allow_premium: bool = False,
        premium_tier_confirmed: bool = False,
    ):
        if not token:
            raise ValueError("FinMind token is required.")
        self._token = token
        self._base_url = base_url
        self._timeout = timeout
        self._allow_premium = allow_premium
        self._premium_tier_confirmed = premium_tier_confirmed
        self._headers = {"Authorization": f"Bearer {token}"}

    @property
    def allow_premium(self) -> bool:
        return self._allow_premium

    @property
    def premium_tier_confirmed(self) -> bool:
        return self._premium_tier_confirmed

    @staticmethod
    def is_premium(dataset: str) -> bool:
        """Free-tier-unsafe datasets, per Finmind.md tier notes."""
        return is_premium(dataset)

    # ──────────────────────────────────────────────────────────────────
    # Quota
    # ──────────────────────────────────────────────────────────────────

    def usage(self) -> UsageInfo:
        """Check current API quota usage."""
        resp = requests.get(FINMIND_USER_INFO_URL, headers=self._headers, timeout=self._timeout)
        resp.raise_for_status()
        j = resp.json()
        return UsageInfo(user_count=int(j["user_count"]), api_request_limit=int(j["api_request_limit"]))

    # ──────────────────────────────────────────────────────────────────
    # Synchronous single-dataset fetch
    # ──────────────────────────────────────────────────────────────────

    def get(
        self,
        dataset: str,
        stock_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch a dataset from FinMind.

        Returns an empty DataFrame if the API returns no data. Raises FinMindError
        on non-recoverable failures after retries.

        Args:
            dataset: FinMind dataset name (e.g., 'TaiwanStockFinancialStatements')
            stock_id: Data ID (stock code for most TW datasets)
            start_date: YYYY-MM-DD
            end_date: YYYY-MM-DD

        Returns:
            DataFrame with the raw response rows.
        """
        # Gate premium datasets BEFORE the HTTP call so free-tier pipelines
        # never silently 400. Two conditions must be true before a premium
        # request is even attempted:
        #   1. the caller explicitly enables the premium path; and
        #   2. the active token has been positively verified as Backer/Sponsor.
        # This prevents `allow_premium=True` from being treated as proof that
        # the token is premium-tier.
        if is_premium(dataset):
            if not self._premium_tier_confirmed:
                raise PremiumDatasetRequired(
                    f"Dataset '{dataset}' requires FinMind Backer/Sponsor tier. "
                    f"This client is not confirmed premium-tier, so the request "
                    f"is blocked before the HTTP call."
                )
            if not self._allow_premium:
                raise PremiumDatasetRequired(
                    f"Dataset '{dataset}' requires FinMind Backer/Sponsor tier "
                    f"and premium calls are disabled on this client."
                )

        params: dict[str, Any] = {"dataset": dataset}
        if stock_id:
            params["data_id"] = stock_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(
                    f"{self._base_url}/data",
                    params=params,
                    headers=self._headers,
                    timeout=self._timeout,
                )
                if resp.status_code == 402:
                    raise RateLimitExceeded(f"FinMind quota exceeded: {resp.text}")
                if resp.status_code == 400:
                    # 400 = dataset requires higher membership tier (Backer/Sponsor).
                    # Not a transient error — do not retry.
                    raise FinMindError(
                        f"FinMind tier limit: dataset '{dataset}' requires Backer/Sponsor "
                        f"tier (HTTP 400). Skipping."
                    )
                resp.raise_for_status()
                payload = resp.json()
                if payload.get("status") != 200:
                    raise FinMindError(f"FinMind error: {payload}")
                rows = payload.get("data", [])
                return pd.DataFrame(rows)
            except RateLimitExceeded:
                raise  # don't retry on quota exhaustion
            except FinMindError:
                raise  # don't retry on known API errors (tier, bad dataset)
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("FinMind fetch failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
        raise FinMindError(f"FinMind fetch failed after {MAX_RETRIES} retries: {last_err}")

    # ──────────────────────────────────────────────────────────────────
    # Async batch fetch — the edge over retail workflows
    # ──────────────────────────────────────────────────────────────────

    async def _fetch_async(
        self,
        dataset: str,
        stock_id: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> tuple[str, pd.DataFrame]:
        """Wrapper that runs sync fetch in a thread."""
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None, lambda: self.get(dataset, stock_id, start_date, end_date)
        )
        return stock_id, df

    async def _get_multi_async(
        self,
        dataset: str,
        stock_ids: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> dict[str, pd.DataFrame]:
        tasks = [
            self._fetch_async(dataset, sid, start_date, end_date) for sid in stock_ids
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, pd.DataFrame] = {}
        for res in results:
            if isinstance(res, Exception):
                log.warning("Peer fetch failed: %s", res)
                continue
            stock_id, df = res
            out[stock_id] = df
        return out

    def get_multi(
        self,
        dataset: str,
        stock_ids: list[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Async batch fetch across multiple stocks.

        Returns {stock_id: DataFrame}. Failed fetches are logged and omitted.
        Not supported by: info, snapshot, tick, total-aggregation, CB datasets
        (those take no data_id or have special semantics — call get() instead).
        """
        return asyncio.run(self._get_multi_async(dataset, stock_ids, start_date, end_date))

    # ──────────────────────────────────────────────────────────────────
    # Convenience shortcuts for the most common datasets
    # ──────────────────────────────────────────────────────────────────

    def price(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPrice", stock_id, start_date, end_date)

    def price_adj(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPriceAdj", stock_id, start_date, end_date)

    def financial_statements(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockFinancialStatements", stock_id, start_date)

    def balance_sheet(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockBalanceSheet", stock_id, start_date)

    def cash_flow(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockCashFlowsStatement", stock_id, start_date)

    def monthly_revenue(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockMonthRevenue", stock_id, start_date)

    def per(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockPER", stock_id, start_date, end_date)

    def market_value(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockMarketValue", stock_id, start_date, end_date)

    def institutional_flow(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockInstitutionalInvestorsBuySell", stock_id, start_date, end_date)

    def foreign_ownership(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockShareholding", stock_id, start_date, end_date)

    def margin_short(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockMarginPurchaseShortSale", stock_id, start_date, end_date)

    def securities_lending(self, stock_id: str, start_date: str, end_date: Optional[str] = None) -> pd.DataFrame:
        return self.get("TaiwanStockSecuritiesLending", stock_id, start_date, end_date)

    def news(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockNews", stock_id, start_date)

    def dividend(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self.get("TaiwanStockDividend", stock_id, start_date)

    def industry_chain(self) -> pd.DataFrame:
        return self.get("TaiwanStockIndustryChain")

    def stock_info(self) -> pd.DataFrame:
        return self.get("TaiwanStockInfo")
