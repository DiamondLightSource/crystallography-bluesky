import pytest
from bluesky import RunEngine

from crystallography_bluesky.i15_1.plans import bad_plan


def test_bad_plan_raises_error_with_message():
    run_engine = RunEngine()
    with pytest.raises(Exception) as exc_info:
        run_engine(bad_plan("my error message"))

    assert str(exc_info.value) == "my error message"
