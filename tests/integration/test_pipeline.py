from pathlib import Path

import pytest

from core.pipeline import process_excel


FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def test_pipeline_formel_extrakt(tmp_path):
    input_path = FIXTURES / "Formel_extrakt.xlsx"
    if not input_path.exists():
        pytest.skip("Fixture file missing")
    results = process_excel(input_path, tmp_path, 2000)
    assert results


def test_pipeline_with_error_continues(tmp_path):
    input_path = FIXTURES / "Formel_extrakt_with_error.xlsx"
    if not input_path.exists():
        pytest.skip("Fixture file missing")
    results = process_excel(input_path, tmp_path, 2000)
    total = sum(len(sections) for sections in results.values())
    failed = sum(len([s for s in sections if s.status != "OK"]) for sections in results.values())
    assert total > 0
    assert failed >= 1
