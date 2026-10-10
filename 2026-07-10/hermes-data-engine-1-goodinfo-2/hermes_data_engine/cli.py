"""Command-line interface for Hermes daily data generation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from functools import partial
from pathlib import Path

from hermes_data_engine.http import fetch_text
from hermes_data_engine.pipeline import HermesPipeline
from hermes_data_engine.providers.goodinfo import GoodinfoProvider
from hermes_data_engine.providers.mops import MopsProvider
from hermes_data_engine.providers.twse import TwseProvider
from hermes_data_engine.providers.yahoo import YahooProvider
from hermes_data_engine.storage import atomic_write, load_previous
from hermes_data_engine.models import validate_document
from hermes_data_engine.readiness import assess_market_readiness


DEFAULT_SYMBOLS = ("3033", "6214", "6753", "1314", "2002")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-data-engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--date")
    run_parser.add_argument("--output-dir", default="data")
    run_parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    run_parser.add_argument("--timeout", type=int, default=10)
    run_parser.add_argument("--attempts", type=int, default=2)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("paths", nargs="+")

    readiness_parser = subparsers.add_parser(
        "readiness", help="Read-only, fail-closed check of end-of-day market data"
    )
    readiness_parser.add_argument("paths", nargs="+")
    readiness_parser.add_argument("--expected-trading-date", required=True)
    readiness_parser.add_argument(
        "--official-session-confirmed", action="store_true",
        help="Assert an independent official trading-day/closure verification"
    )
    readiness_parser.add_argument(
        "--official-session-source",
        help="Record the checked official market-calendar/result reference",
    )
    return parser


def _configured_fetcher(timeout: int, attempts: int):
    return partial(fetch_text, timeout=timeout, attempts=attempts)


def _default_pipeline(timeout: int = 10, attempts: int = 2) -> HermesPipeline:
    fetcher = _configured_fetcher(timeout, attempts)
    return HermesPipeline(
        GoodinfoProvider(fetcher=fetcher),
        TwseProvider(fetcher=fetcher),
        MopsProvider(fetcher=fetcher),
        YahooProvider(fetcher=fetcher),
    )


def _symbols(value: str) -> list[str]:
    return [symbol.strip() for symbol in value.split(",") if symbol.strip()]


def effective_trading_date(today: date | None = None) -> str:
    candidate = today or date.today()
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.isoformat()


def _run(args, pipeline_factory) -> int:
    output_dir = Path(args.output_dir)
    failed = False
    try:
        pipeline = pipeline_factory(timeout=args.timeout, attempts=args.attempts)
    except TypeError:
        pipeline = pipeline_factory()
    trading_date = args.date or effective_trading_date()
    for symbol in _symbols(args.symbols):
        path = output_dir / f"{symbol}.json"
        try:
            previous = load_previous(path)
            document = pipeline.run(symbol, trading_date, previous)
            atomic_write(path, document)
        except Exception as exc:  # noqa: BLE001 - CLI reports per-symbol failures.
            failed = True
            print(f"{symbol}: {exc}", file=sys.stderr)
    return 1 if failed else 0


def _validate(args) -> int:
    failed = False
    for raw_path in args.paths:
        try:
            previous = load_previous(raw_path)
            if previous is None:
                raise FileNotFoundError(raw_path)
            validate_document(previous)
        except Exception as exc:  # noqa: BLE001 - report all invalid files.
            failed = True
            print(f"{raw_path}: {exc}", file=sys.stderr)
    return 1 if failed else 0


def _readiness(args) -> int:
    failed = False
    for raw_path in args.paths:
        try:
            document = load_previous(raw_path)
            if document is None:
                raise FileNotFoundError(raw_path)
            result = assess_market_readiness(
                document, args.expected_trading_date,
                session_confirmed=args.official_session_confirmed,
                session_source=args.official_session_source,
            )
            result["path"] = raw_path
            failed |= not result["ready"]
        except (OSError, ValueError, TypeError, KeyError) as exc:
            failed = True
            result = {"path": raw_path, "ready": False, "issues": [str(exc)]}
        print(json.dumps(result, ensure_ascii=False))
    return 1 if failed else 0


def main(argv: list[str] | None = None, pipeline_factory=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    pipeline_factory = pipeline_factory or _default_pipeline
    if args.command == "run":
        return _run(args, pipeline_factory)
    if args.command == "validate":
        return _validate(args)
    if args.command == "readiness":
        return _readiness(args)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
