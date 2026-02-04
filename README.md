# Truth Table Generator

A Windows-friendly Python desktop app to parse logical formulas from Excel, convert to DNF, and export truth tables plus documentation files.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python -m app
```

## Fixtures

Place the provided Excel fixtures into `fixtures/`:
- `Formel_extrakt.xlsx`
- `Formel_extrakt_with_error.xlsx`
- `CCM_3.5.xlsx`

## Tests

```bash
pytest
```

## Optional: Build Windows EXE

```bash
pyinstaller --onefile --name truth-table-generator -m app
```
