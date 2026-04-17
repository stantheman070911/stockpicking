"""
Parsers — convert FinMind's long-format financial statements into usable structures.

FinMind returns Taiwan financial statements in a painful long format:

    date       | stock_id | type                | value       | origin_name
    2024-09-30 | 2330     | Revenue             | 7.57e11     | 營業收入合計
    2024-09-30 | 2330     | GrossProfit         | 4.40e11     | 營業毛利（毛損）
    ...

This module pivots into wide format keyed on common English 'type' codes.
When a type is not present, the corresponding field is None with a flag.

The canonical type names below are what FinMind actually returns. If you see
different names in the wild, add them to the LEDGER dicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


# ──────────────────────────────────────────────────────────────────────────
# Canonical field mappings — FinMind 'type' codes → our field names.
# Multiple variants allowed per field; first match wins.
# ──────────────────────────────────────────────────────────────────────────

INCOME_STATEMENT_LEDGER = {
    "revenue": ["Revenue", "OperatingRevenue"],
    "cogs": ["CostOfGoodsSold", "OperatingCosts"],
    "gross_profit": ["GrossProfit"],
    "operating_expenses": ["OperatingExpenses"],
    "operating_income": ["OperatingIncome"],
    "nonop_income": ["NonoperatingIncomeAndExpenses"],
    "pretax_income": ["IncomeBeforeTax", "ProfitBeforeTax"],
    "tax_expense": ["IncomeTaxExpense"],
    "net_income": ["IncomeAfterTax", "IncomeAfterTaxes", "NetIncome"],
    "eps": ["EPS", "EarningsPerShare"],
    "depreciation": ["Depreciation"],
    "interest_expense": ["InterestExpense"],
}

BALANCE_SHEET_LEDGER = {
    "cash_and_equivalents": ["CashAndCashEquivalents"],
    "accounts_receivable": ["AccountsReceivable", "AccountsReceivableNet"],
    "inventory": ["Inventories"],
    "current_assets": ["CurrentAssets"],
    "total_assets": ["TotalAssets", "Assets"],
    "short_term_borrowings": ["ShortTermBorrowings", "ShortTermLoans"],
    "accounts_payable": ["AccountsPayable"],
    "current_liabilities": ["CurrentLiabilities"],
    "long_term_borrowings": ["LongTermBorrowings", "LongTermLoans"],
    "total_liabilities": ["Liabilities", "TotalLiabilities"],
    "equity": ["Equity", "TotalEquity", "StockholdersEquity"],
}

CASH_FLOW_LEDGER = {
    "cfo": ["CashFlowsFromOperatingActivities", "NetCashProvidedByOperatingActivities"],
    "cfi": ["CashFlowsFromInvestingActivities"],
    "cff": ["CashFlowsFromFinancingActivities"],
    "capex": ["PropertyPlantAndEquipment", "AcquisitionOfPropertyPlantAndEquipment"],
    "depreciation_cf": ["Depreciation"],
    "dividends_paid": ["CashDividendsPaid", "PaymentOfCashDividends"],
}


# ──────────────────────────────────────────────────────────────────────────
# Structured records
# ──────────────────────────────────────────────────────────────────────────

@dataclass
class IncomeStatement:
    date: str
    stock_id: str
    revenue: Optional[float] = None
    cogs: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_expenses: Optional[float] = None
    operating_income: Optional[float] = None
    nonop_income: Optional[float] = None
    pretax_income: Optional[float] = None
    tax_expense: Optional[float] = None
    net_income: Optional[float] = None
    eps: Optional[float] = None
    depreciation: Optional[float] = None
    interest_expense: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def gross_margin(self) -> Optional[float]:
        if self.revenue and self.gross_profit is not None and self.revenue != 0:
            return self.gross_profit / self.revenue
        return None

    @property
    def operating_margin(self) -> Optional[float]:
        if self.revenue and self.operating_income is not None and self.revenue != 0:
            return self.operating_income / self.revenue
        return None

    @property
    def net_margin(self) -> Optional[float]:
        if self.revenue and self.net_income is not None and self.revenue != 0:
            return self.net_income / self.revenue
        return None


@dataclass
class BalanceSheet:
    date: str
    stock_id: str
    cash_and_equivalents: Optional[float] = None
    accounts_receivable: Optional[float] = None
    inventory: Optional[float] = None
    current_assets: Optional[float] = None
    total_assets: Optional[float] = None
    short_term_borrowings: Optional[float] = None
    accounts_payable: Optional[float] = None
    current_liabilities: Optional[float] = None
    long_term_borrowings: Optional[float] = None
    total_liabilities: Optional[float] = None
    equity: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def total_debt(self) -> Optional[float]:
        if self.short_term_borrowings is not None and self.long_term_borrowings is not None:
            return self.short_term_borrowings + self.long_term_borrowings
        return None

    @property
    def net_debt(self) -> Optional[float]:
        td = self.total_debt
        if td is not None and self.cash_and_equivalents is not None:
            return td - self.cash_and_equivalents
        return None

    @property
    def current_ratio(self) -> Optional[float]:
        if self.current_liabilities and self.current_assets is not None and self.current_liabilities != 0:
            return self.current_assets / self.current_liabilities
        return None

    @property
    def debt_to_equity(self) -> Optional[float]:
        td = self.total_debt
        if td is not None and self.equity and self.equity != 0:
            return td / self.equity
        return None


@dataclass
class CashFlow:
    date: str
    stock_id: str
    cfo: Optional[float] = None
    cfi: Optional[float] = None
    cff: Optional[float] = None
    capex: Optional[float] = None
    depreciation_cf: Optional[float] = None
    dividends_paid: Optional[float] = None
    missing_fields: list[str] = field(default_factory=list)

    @property
    def free_cash_flow(self) -> Optional[float]:
        # Capex in FinMind is typically reported as negative (investment outflow).
        # FCF = CFO - |Capex|. If capex is reported positive, flip sign.
        if self.cfo is not None and self.capex is not None:
            return self.cfo - abs(self.capex)
        return None


# ──────────────────────────────────────────────────────────────────────────
# Parser functions
# ──────────────────────────────────────────────────────────────────────────

def _pivot_long_format(df: pd.DataFrame, ledger: dict[str, list[str]]) -> pd.DataFrame:
    """
    Pivot FinMind long-format (date/stock_id/type/value) into wide format
    with columns defined by the ledger.
    """
    if df.empty:
        return pd.DataFrame()

    # Group by (date, stock_id) and pivot type → value
    wide = df.pivot_table(
        index=["date", "stock_id"],
        columns="type",
        values="value",
        aggfunc="first",
    ).reset_index()

    # Map raw FinMind types to canonical names
    renamed_cols = {"date": "date", "stock_id": "stock_id"}
    for canonical, variants in ledger.items():
        for v in variants:
            if v in wide.columns:
                renamed_cols[v] = canonical
                break

    wide = wide.rename(columns=renamed_cols)
    # Keep only canonical columns + date/stock_id
    keep = ["date", "stock_id"] + [c for c in ledger.keys() if c in wide.columns]
    return wide[keep].sort_values("date").reset_index(drop=True)


def parse_income_statements(df: pd.DataFrame) -> list[IncomeStatement]:
    """Parse a TaiwanStockFinancialStatements response into IncomeStatement records."""
    wide = _pivot_long_format(df, INCOME_STATEMENT_LEDGER)
    out: list[IncomeStatement] = []
    for _, row in wide.iterrows():
        rec = IncomeStatement(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in INCOME_STATEMENT_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def parse_balance_sheets(df: pd.DataFrame) -> list[BalanceSheet]:
    """Parse a TaiwanStockBalanceSheet response into BalanceSheet records."""
    wide = _pivot_long_format(df, BALANCE_SHEET_LEDGER)
    out: list[BalanceSheet] = []
    for _, row in wide.iterrows():
        rec = BalanceSheet(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in BALANCE_SHEET_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def parse_cash_flows(df: pd.DataFrame) -> list[CashFlow]:
    """Parse a TaiwanStockCashFlowsStatement response into CashFlow records."""
    wide = _pivot_long_format(df, CASH_FLOW_LEDGER)
    out: list[CashFlow] = []
    for _, row in wide.iterrows():
        rec = CashFlow(date=str(row["date"]), stock_id=str(row["stock_id"]))
        for k in CASH_FLOW_LEDGER.keys():
            if k in wide.columns:
                v = row[k]
                if pd.notna(v):
                    setattr(rec, k, float(v))
                else:
                    rec.missing_fields.append(k)
            else:
                rec.missing_fields.append(k)
        out.append(rec)
    return out


def latest(records: list) -> Optional[object]:
    """Return the most recent record by date, or None if list is empty."""
    if not records:
        return None
    return sorted(records, key=lambda r: r.date)[-1]


def ttm(records: list, n: int = 4) -> list:
    """Return the most recent n quarters (trailing-twelve-months basis)."""
    if not records:
        return []
    return sorted(records, key=lambda r: r.date)[-n:]
