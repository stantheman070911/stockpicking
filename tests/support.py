from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


QUARTER_DATES = ["2025-06-30", "2025-09-30", "2025-12-31", "2026-03-31"]


def make_price_df(days: int = 320, trading_money: float = 120_000_000, close_start: float = 100.0, close_step: float = 0.3) -> pd.DataFrame:
    dates = pd.date_range("2025-06-01", periods=days, freq="D")
    rows = []
    close = close_start
    for idx, date in enumerate(dates):
        if idx % 9 == 0:
            close -= close_step * 0.4
        else:
            close += close_step
        rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "close": round(close, 2),
                "Trading_money": trading_money,
            }
        )
    return pd.DataFrame(rows)


def make_per_df(days: int = 320, base: float = 14.0) -> pd.DataFrame:
    dates = pd.date_range("2025-06-01", periods=days, freq="D")
    values = [base + ((idx % 30) / 10) for idx in range(days)]
    return pd.DataFrame(
        {
            "date": [date.strftime("%Y-%m-%d") for date in dates],
            "PER": values,
        }
    )


def make_monthly_revenue_df(stock_id: str = "2330", values: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2024-04-01", periods=24, freq="MS")
    if values is None:
        values = [300.0] * 12 + [400.0] * 9 + [400.0, 400.0, 400.0]
    return pd.DataFrame(
        {
            "date": [date.strftime("%Y-%m-%d") for date in dates],
            "stock_id": stock_id,
            "revenue": values,
        }
    )


def make_income_df(
    stock_id: str = "2330",
    revenue: list[float] | None = None,
    net_income: list[float] | None = None,
    operating_income: list[float] | None = None,
    depreciation: list[float] | None = None,
    interest_expense: list[float] | None = None,
) -> pd.DataFrame:
    revenue = revenue or [900.0, 1000.0, 1100.0, 1200.0]
    net_income = net_income or [90.0, 100.0, 110.0, 120.0]
    operating_income = operating_income or [180.0, 200.0, 220.0, 240.0]
    depreciation = depreciation or [20.0, 20.0, 20.0, 20.0]
    interest_expense = interest_expense or [5.0, 5.0, 5.0, 5.0]

    rows = []
    for idx, date in enumerate(QUARTER_DATES):
        gp = revenue[idx] * 0.45
        rows.extend(
            [
                {"date": date, "stock_id": stock_id, "type": "Revenue", "value": revenue[idx]},
                {"date": date, "stock_id": stock_id, "type": "GrossProfit", "value": gp},
                {"date": date, "stock_id": stock_id, "type": "OperatingIncome", "value": operating_income[idx]},
                {"date": date, "stock_id": stock_id, "type": "IncomeAfterTax", "value": net_income[idx]},
                {"date": date, "stock_id": stock_id, "type": "Depreciation", "value": depreciation[idx]},
                {"date": date, "stock_id": stock_id, "type": "InterestExpense", "value": interest_expense[idx]},
            ]
        )
    return pd.DataFrame(rows)


def make_balance_df(stock_id: str = "2330") -> pd.DataFrame:
    rows = []
    for date in QUARTER_DATES:
        rows.extend(
            [
                {"date": date, "stock_id": stock_id, "type": "CashAndCashEquivalents", "value": 500.0},
                {"date": date, "stock_id": stock_id, "type": "CurrentAssets", "value": 1200.0},
                {"date": date, "stock_id": stock_id, "type": "CurrentLiabilities", "value": 600.0},
                {"date": date, "stock_id": stock_id, "type": "ShortTermBorrowings", "value": 120.0},
                {"date": date, "stock_id": stock_id, "type": "LongTermBorrowings", "value": 180.0},
                {"date": date, "stock_id": stock_id, "type": "TotalAssets", "value": 4000.0},
                {"date": date, "stock_id": stock_id, "type": "TotalLiabilities", "value": 1800.0},
                {"date": date, "stock_id": stock_id, "type": "Equity", "value": 2200.0},
            ]
        )
    return pd.DataFrame(rows)


def make_cash_flow_df(stock_id: str = "2330", cfo_values: list[float] | None = None, capex_values: list[float] | None = None) -> pd.DataFrame:
    cfo_values = cfo_values or [100.0, 110.0, 120.0, 130.0]
    capex_values = capex_values or [-30.0, -30.0, -35.0, -35.0]
    rows = []
    for idx, date in enumerate(QUARTER_DATES):
        rows.extend(
            [
                {"date": date, "stock_id": stock_id, "type": "CashFlowsFromOperatingActivities", "value": cfo_values[idx]},
                {"date": date, "stock_id": stock_id, "type": "PropertyPlantAndEquipment", "value": capex_values[idx]},
                {"date": date, "stock_id": stock_id, "type": "Depreciation", "value": 20.0},
            ]
        )
    return pd.DataFrame(rows)


def make_institutional_flow_df() -> pd.DataFrame:
    dates = pd.date_range("2026-02-01", periods=5, freq="14D")
    rows = []
    for date in dates:
        rows.extend(
            [
                {"date": date.strftime("%Y-%m-%d"), "name": "Foreign_Investor", "buy": 1000, "sell": 400},
                {"date": date.strftime("%Y-%m-%d"), "name": "Investment_Trust", "buy": 700, "sell": 300},
                {"date": date.strftime("%Y-%m-%d"), "name": "Dealer", "buy": 500, "sell": 450},
            ]
        )
    return pd.DataFrame(rows)


def make_shareholding_df(shares_issued: float = 1_000_000_000) -> pd.DataFrame:
    dates = pd.date_range("2026-02-01", periods=4, freq="MS")
    return pd.DataFrame(
        {
            "date": [date.strftime("%Y-%m-%d") for date in dates],
            "ForeignInvestmentSharesRatio": [28.0, 28.2, 28.5, 28.8],
            "NumberOfSharesIssued": [shares_issued] * len(dates),
        }
    )


def make_margin_df(values: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2026-02-01", periods=30, freq="D")
    values = values or [1_000_000 + idx * 10_000 for idx in range(len(dates))]
    return pd.DataFrame(
        {
            "date": [date.strftime("%Y-%m-%d") for date in dates],
            "MarginPurchaseTodayBalance": values,
        }
    )


def make_sbl_df(values: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2026-02-01", periods=30, freq="D")
    values = values or [100_000 + idx * 1_000 for idx in range(len(dates))]
    return pd.DataFrame(
        {
            "date": [date.strftime("%Y-%m-%d") for date in dates],
            "SBLShortSalesCurrentDayBalance": values,
        }
    )


def make_news_df(titles: list[str] | None = None) -> pd.DataFrame:
    titles = titles or ["Normal operations update", "Capacity expansion on track"]
    return pd.DataFrame(
        {
            "date": ["2026-04-05", "2026-04-10"][: len(titles)],
            "title": titles,
        }
    )


def make_stock_info_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"stock_id": "2330", "industry_category": "半導體業", "stock_name": "TSMC"},
            {"stock_id": "2303", "industry_category": "半導體業", "stock_name": "UMC"},
            {"stock_id": "3711", "industry_category": "半導體業", "stock_name": "ASE"},
            {"stock_id": "2317", "industry_category": "電腦及週邊設備業", "stock_name": "Hon Hai"},
            {"stock_id": "1101", "industry_category": "水泥工業", "stock_name": "TCC"},
        ]
    )


@dataclass
class DummyFreeTierClient:
    dataset_map: dict[str, dict[str, pd.DataFrame]] = field(default_factory=dict)
    dataset_singletons: dict[str, pd.DataFrame] = field(default_factory=dict)

    def _lookup(self, dataset: str, stock_id: str | None = None) -> pd.DataFrame:
        if stock_id is None:
            return self.dataset_singletons.get(dataset, pd.DataFrame()).copy()
        return self.dataset_map.get(dataset, {}).get(stock_id, pd.DataFrame()).copy()

    def price(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockPrice", stock_id)

    def price_adj(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockPriceAdj", stock_id)

    def financial_statements(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self._lookup("TaiwanStockFinancialStatements", stock_id)

    def balance_sheet(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self._lookup("TaiwanStockBalanceSheet", stock_id)

    def cash_flow(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self._lookup("TaiwanStockCashFlowsStatement", stock_id)

    def monthly_revenue(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self._lookup("TaiwanStockMonthRevenue", stock_id)

    def institutional_flow(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockInstitutionalInvestorsBuySell", stock_id)

    def foreign_ownership(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockShareholding", stock_id)

    def margin_short(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockMarginPurchaseShortSale", stock_id)

    def news(self, stock_id: str, start_date: str) -> pd.DataFrame:
        return self._lookup("TaiwanStockNews", stock_id)

    def per(self, stock_id: str, start_date: str, end_date: str | None = None) -> pd.DataFrame:
        return self._lookup("TaiwanStockPER", stock_id)

    def stock_info(self) -> pd.DataFrame:
        return self.dataset_singletons.get("TaiwanStockInfo", pd.DataFrame()).copy()

    def industry_chain(self) -> pd.DataFrame:
        return self.dataset_singletons.get("TaiwanStockIndustryChain", pd.DataFrame()).copy()

    def usage(self):
        return type("Usage", (), {"remaining": 500, "api_request_limit": 600, "user_count": 100, "utilization_pct": 100 / 600})()

    def get(self, dataset: str, stock_id: str | None = None, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
        if stock_id is None:
            return self.dataset_singletons.get(dataset, pd.DataFrame()).copy()
        return self._lookup(dataset, stock_id)

    def get_multi(self, dataset: str, stock_ids: list[str], start_date: str | None = None, end_date: str | None = None) -> dict[str, pd.DataFrame]:
        return {stock_id: self.get(dataset, stock_id, start_date, end_date) for stock_id in stock_ids}


def make_default_client() -> DummyFreeTierClient:
    base_price = make_price_df()
    peer_price = make_price_df(close_start=80.0, close_step=0.25)
    book_price = base_price.copy()

    dataset_map = {
        "TaiwanStockPrice": {
            "2330": base_price,
            "2303": peer_price,
            "3711": make_price_df(close_start=60.0, close_step=0.2),
            "2317": book_price,
            "1101": make_price_df(close_start=35.0, close_step=0.05, trading_money=40_000_000),
        },
        "TaiwanStockPriceAdj": {
            "2330": base_price,
            "2303": peer_price,
            "3711": make_price_df(close_start=60.0, close_step=0.2),
            "2317": book_price,
            "1101": make_price_df(close_start=35.0, close_step=0.05, trading_money=40_000_000),
        },
        "TaiwanStockFinancialStatements": {
            "2330": make_income_df("2330"),
            "2303": make_income_df("2303"),
            "3711": make_income_df("3711"),
            "2317": make_income_df("2317"),
            "1101": make_income_df("1101", revenue=[500.0, 520.0, 510.0, 500.0], net_income=[20.0, 18.0, 15.0, 12.0]),
        },
        "TaiwanStockBalanceSheet": {
            "2330": make_balance_df("2330"),
            "2303": make_balance_df("2303"),
            "3711": make_balance_df("3711"),
            "2317": make_balance_df("2317"),
            "1101": make_balance_df("1101"),
        },
        "TaiwanStockCashFlowsStatement": {
            "2330": make_cash_flow_df("2330"),
            "2303": make_cash_flow_df("2303"),
            "3711": make_cash_flow_df("3711"),
            "2317": make_cash_flow_df("2317"),
            "1101": make_cash_flow_df("1101", cfo_values=[30.0, 25.0, 20.0, 18.0]),
        },
        "TaiwanStockMonthRevenue": {
            "2330": make_monthly_revenue_df("2330"),
            "2303": make_monthly_revenue_df("2303", values=[280.0] * 12 + [330.0] * 12),
            "3711": make_monthly_revenue_df("3711", values=[260.0] * 12 + [360.0] * 12),
            "2317": make_monthly_revenue_df("2317", values=[290.0] * 12 + [310.0] * 12),
            "1101": make_monthly_revenue_df("1101", values=[300.0] * 12 + [250.0] * 12),
        },
        "TaiwanStockInstitutionalInvestorsBuySell": {
            "2330": make_institutional_flow_df(),
            "2303": make_institutional_flow_df(),
            "3711": make_institutional_flow_df(),
            "2317": make_institutional_flow_df(),
            "1101": make_institutional_flow_df(),
        },
        "TaiwanStockShareholding": {
            "2330": make_shareholding_df(),
            "2303": make_shareholding_df(),
            "3711": make_shareholding_df(),
            "2317": make_shareholding_df(),
            "1101": make_shareholding_df(),
        },
        "TaiwanStockMarginPurchaseShortSale": {
            "2330": make_margin_df(),
            "2303": make_margin_df(),
            "3711": make_margin_df(),
            "2317": make_margin_df(),
            "1101": make_margin_df(values=[800_000 + idx * 5_000 for idx in range(30)]),
        },
        "TaiwanDailyShortSaleBalances": {
            "2330": make_sbl_df(),
            "2303": make_sbl_df(),
            "3711": make_sbl_df(),
            "2317": make_sbl_df(),
            "1101": make_sbl_df(),
        },
        "TaiwanStockNews": {
            "2330": make_news_df(),
            "2303": make_news_df(),
            "3711": make_news_df(),
            "2317": make_news_df(),
            "1101": make_news_df(),
        },
        "TaiwanStockCapitalReductionReferencePrice": {
            "2330": pd.DataFrame(),
            "2303": pd.DataFrame(),
            "3711": pd.DataFrame(),
            "2317": pd.DataFrame(),
            "1101": pd.DataFrame(),
        },
        "TaiwanStockPER": {
            "2330": make_per_df(),
            "2303": make_per_df(base=12.0),
            "3711": make_per_df(base=16.0),
            "2317": make_per_df(base=15.0),
            "1101": make_per_df(base=10.0),
        },
        "TaiwanExchangeRate": {
            "USD": pd.DataFrame(
                {
                    "date": ["2026-03-01", "2026-04-01"],
                    "spot_sell": [31.8, 32.2],
                }
            )
        },
        "GovernmentBondsYield": {
            "United States 10-Year": pd.DataFrame(
                {
                    "date": ["2026-03-01", "2026-04-01"],
                    "value": [4.10, 4.20],
                }
            )
        },
    }
    dataset_singletons = {
        "TaiwanStockInfo": make_stock_info_df(),
    }
    return DummyFreeTierClient(dataset_map=dataset_map, dataset_singletons=dataset_singletons)
