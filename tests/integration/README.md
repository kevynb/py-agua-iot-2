# Integration test harness

This repository uses `pytest` + `vcrpy` for record/replay integration tests.

## Install test dependencies

```bash
python -m pip install -e ".[test]"
```

## Run replay-only integration tests

```bash
pytest tests/integration -m integration
```

By default, cassettes run in `VCR_RECORD_MODE=none` (no outbound HTTP allowed).

## Record cassettes with real credentials

Set the required environment variables:

- `AGUA_API_URL`
- `AGUA_CUSTOMER_CODE`
- `AGUA_EMAIL`
- `AGUA_PASSWORD`
- `AGUA_UNIQUE_ID`

Optional:

- `AGUA_LOGIN_API_URL`
- `AGUA_BRAND_ID` (default `1`)

Then record:

```bash
VCR_RECORD_MODE=once pytest tests/integration -m integration
```

After recording, inspect `tests/integration/cassettes/*.yaml` diffs and ensure no
sensitive values are present.
