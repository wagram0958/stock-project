import unittest

from symbol_gate import SymbolProvider, validate_symbol_gate


EXPECTED_BLOCKED_BASE = {
    "confidence_score": 0,
    "hermes_analysis_allowed": False,
    "market": "TW",
}


class ExplodingProvider:
    def has_symbol(self, symbol):
        raise AssertionError("provider must not be called for invalid format")


class SymbolValidationGateTest(unittest.TestCase):
    def setUp(self):
        self.provider = SymbolProvider.from_symbols({"2002", "6214", "6753", "1314"})

    def test_allows_known_tw_symbols(self):
        for symbol in ("2002", "6214", "6753", "1314"):
            with self.subTest(symbol=symbol):
                result = validate_symbol_gate(symbol, self.provider)

                self.assertEqual(result["market"], "TW")
                self.assertEqual(result["verification_reason"], "VALID_TW_SYMBOL")
                self.assertEqual(result["confidence_score"], 1)
                self.assertTrue(result["hermes_analysis_allowed"])

    def test_blocks_unknown_tw_formatted_symbols(self):
        for symbol in ("9999", "8888"):
            with self.subTest(symbol=symbol):
                result = validate_symbol_gate(symbol, self.provider)

                self.assertEqual(
                    result,
                    {
                        **EXPECTED_BLOCKED_BASE,
                        "verification_reason": "WRONG_SYMBOL",
                    },
                )

    def test_blocks_invalid_formats(self):
        for symbol in ("ABCDE", "20O2", "200233", "12", ""):
            with self.subTest(symbol=symbol):
                result = validate_symbol_gate(symbol, self.provider)

                self.assertEqual(
                    result,
                    {
                        **EXPECTED_BLOCKED_BASE,
                        "verification_reason": "INVALID_FORMAT",
                    },
                )

    def test_invalid_format_stops_before_symbol_provider(self):
        result = validate_symbol_gate("ABCDE", ExplodingProvider())

        self.assertEqual(
            result,
            {
                **EXPECTED_BLOCKED_BASE,
                "verification_reason": "INVALID_FORMAT",
            },
        )


if __name__ == "__main__":
    unittest.main()
