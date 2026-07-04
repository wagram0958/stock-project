from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_DATA_FILE = Path("data/sample_stocks.csv")


@dataclass(frozen=True)
class ScreeningRule:
    name: str
    reason: str


RULES = {
    "pe_ratio": ScreeningRule(
        name="pe_ratio",
        reason="PE ratio is reasonable",
    ),
    "revenue_growth": ScreeningRule(
        name="revenue_growth",
        reason="Revenue growth is strong",
    ),
    "dividend_yield": ScreeningRule(
        name="dividend_yield",
        reason="Dividend yield is attractive",
    ),
    "price_trend": ScreeningRule(
        name="price_trend",
        reason="Price is above MA60",
    ),
    "volume_strength": ScreeningRule(
        name="volume_strength",
        reason="Trading volume is stronger than average",
    ),
}


REQUIRED_COLUMNS = {
    "symbol",
    "name",
    "pe_ratio",
    "revenue_growth",
    "dividend_yield",
    "price",
    "ma60",
    "volume_ratio",
}


def load_stocks(file_path: Path) -> pd.DataFrame:
    stocks = pd.read_csv(file_path)
    missing_columns = REQUIRED_COLUMNS - set(stocks.columns)

    if missing_columns:
        columns = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {columns}")

    return stocks


def score_stock(row: pd.Series) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []

    if row["pe_ratio"] <= 25:
        score += 1
        reasons.append(RULES["pe_ratio"].reason)

    if row["revenue_growth"] >= 10:
        score += 1
        reasons.append(RULES["revenue_growth"].reason)

    if row["dividend_yield"] >= 3:
        score += 1
        reasons.append(RULES["dividend_yield"].reason)

    if row["price"] > row["ma60"]:
        score += 1
        reasons.append(RULES["price_trend"].reason)

    if row["volume_ratio"] >= 1.2:
        score += 1
        reasons.append(RULES["volume_strength"].reason)

    return score, reasons


def screen_stocks(stocks: pd.DataFrame, min_score: int) -> pd.DataFrame:
    scored_rows = stocks.copy()
    scores = scored_rows.apply(score_stock, axis=1)

    scored_rows["score"] = [score for score, _ in scores]
    scored_rows["reasons"] = [reasons for _, reasons in scores]

    filtered = scored_rows[scored_rows["score"] >= min_score]
    return filtered.sort_values(
        by=["score", "revenue_growth", "volume_ratio"],
        ascending=[False, False, False],
    )


def print_results(results: pd.DataFrame) -> None:
    if results.empty:
        print("No stocks matched the current screening rules.")
        return

    print("Top stock candidates")
    print()

    for _, row in results.iterrows():
        print(f"{row['symbol']} {row['name']} | Score: {row['score']}/5")
        for reason in row["reasons"]:
            print(f"- {reason}")
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank stocks by screening rules.")
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="CSV file path. Default: data/sample_stocks.csv",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=3,
        choices=range(1, 6),
        help="Minimum score from 1 to 5. Default: 3",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stocks = load_stocks(args.file)
    results = screen_stocks(stocks, args.min_score)
    print_results(results)


if __name__ == "__main__":
    main()
