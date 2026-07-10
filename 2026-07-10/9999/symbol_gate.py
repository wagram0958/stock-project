from dataclasses import dataclass


MARKET = "TW"
INVALID_FORMAT = "INVALID_FORMAT"
WRONG_SYMBOL = "WRONG_SYMBOL"
VALID_TW_SYMBOL = "VALID_TW_SYMBOL"


DEFAULT_TW_SYMBOLS = frozenset({"2002", "6214", "6753", "1314"})


@dataclass(frozen=True)
class SymbolProvider:
    symbols: frozenset[str]

    @classmethod
    def default(cls):
        return cls(DEFAULT_TW_SYMBOLS)

    @classmethod
    def from_symbols(cls, symbols):
        normalized = {str(symbol).strip() for symbol in symbols}
        return cls(frozenset(normalized))

    def with_updated_symbols(self, symbols):
        return self.from_symbols(symbols)

    def has_symbol(self, symbol):
        return symbol in self.symbols


def validate_symbol_gate(user_input, provider=None):
    symbol = _normalize_symbol(user_input)

    if not _is_valid_tw_symbol_format(symbol):
        return _blocked(INVALID_FORMAT)

    symbol_provider = provider or SymbolProvider.default()
    if not symbol_provider.has_symbol(symbol):
        return _blocked(WRONG_SYMBOL)

    return {
        "verification_reason": VALID_TW_SYMBOL,
        "confidence_score": 1,
        "hermes_analysis_allowed": True,
        "market": MARKET,
    }


def _normalize_symbol(user_input):
    if user_input is None:
        return ""
    return str(user_input).strip()


def _is_valid_tw_symbol_format(symbol):
    return len(symbol) == 4 and symbol.isdigit()


def _blocked(reason):
    return {
        "verification_reason": reason,
        "confidence_score": 0,
        "hermes_analysis_allowed": False,
        "market": MARKET,
    }
