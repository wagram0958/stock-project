from pathlib import Path


WORKFLOW = Path(".github/workflows/hermes-data-engine.yml")


def test_workflow_contract_for_daily_generation():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "cron: '30 8 * * 1-5'" in text
    assert "workflow_dispatch:" in text
    assert "contents: write" in text
    assert "concurrency:" in text
    assert "python-version: '3.12'" in text
    assert "\"pytest>=8,<9\"" in text
    assert "python -m pytest -q" in text
    assert "hermes-data-engine run" in text
    assert "hermes-data-engine validate" in text
    assert text.index("python -m pytest -q") < text.index("hermes-data-engine run")
    assert text.index("hermes-data-engine validate") < text.index("git commit")
    for symbol in ("3033", "6214", "6753", "1314", "2002"):
        assert f"data/{symbol}.json" in text
    assert "--force" not in text
    assert "push --force" not in text
