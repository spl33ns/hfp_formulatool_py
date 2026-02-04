from datetime import datetime as real_datetime

from core.utils import create_run_output_dir


def test_create_run_output_dir_format_and_uniqueness(tmp_path, monkeypatch):
    import core.utils as utils

    fixed = real_datetime(2026, 2, 4, 16, 19, 36, 123000)  # -> ...-123

    class FakeDatetime:
        @classmethod
        def now(cls):
            return fixed

    monkeypatch.setattr(utils, "datetime", FakeDatetime)

    first = create_run_output_dir(str(tmp_path))
    assert first.exists()
    assert first.is_dir()
    assert first.name == "2026-02-04 16-19-36-123"

    second = create_run_output_dir(str(tmp_path))
    assert second.exists()
    assert second.is_dir()
    assert second.name == "2026-02-04 16-19-36-123_1"
