import pytest

from core.pipeline import build_sheet_name, SectionFailure
from core.utils import sanitize_excel_sheet_name


def test_sheet_name_mapping():
    assert build_sheet_name("Climate Change Mitigation", "3.5") == "CCM_3.5"


def test_unknown_objective_fails():
    with pytest.raises(SectionFailure):
        build_sheet_name("Unknown", "1")


def test_sanitize_sheet_name():
    assert sanitize_excel_sheet_name("A/B:C*") == "ABC"
