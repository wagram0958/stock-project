## Task 6 Report: Atomic Storage and Batch CLI

Status: complete

RED evidence:
- `python -m pytest tests/test_storage.py -q` failed with `ModuleNotFoundError: No module named 'hermes_data_engine.storage'`.
- `python -m pytest tests/test_cli.py -q` failed with `ModuleNotFoundError: No module named 'hermes_data_engine.cli'`.

GREEN evidence:
- `python -m pytest tests/test_storage.py tests/test_cli.py -q`: 7 passed.
- `python -m pytest -q`: 68 passed.

Implemented:
- `load_previous(path) -> dict | None`.
- `atomic_write(path, document) -> None` using validated same-directory temporary files and `os.replace`.
- `hermes-data-engine run` and `hermes-data-engine validate` command behavior through `hermes_data_engine.cli:main`.
- Default symbols: 3033, 6214, 6753, 1314, 2002.

Commit: deferred per user instruction to commit only after all remaining tests and integration checks pass.
