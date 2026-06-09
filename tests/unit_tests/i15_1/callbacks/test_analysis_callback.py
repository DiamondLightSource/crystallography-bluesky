from pathlib import Path
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from crystallography_bluesky.i15_1.callbacks.analysis_callback import (
    TriggerAnalysisCallback,
)


@pytest.fixture
def blueapi_run_engine():
    # This adds the info the blueapi will add in prod
    RE = RunEngine()
    RE.md["data_session_directory"] = "/dls/i15-1/data/2026/cm44163-3"
    RE.md["scan_file"] = "i15-1-95557"
    return RE


def _run_plan_with_callback(RE, callback):
    @bpp.subs_decorator(callback)
    @bpp.run_decorator()
    def my_plan():
        yield from bps.null()

    RE(my_plan())


@pytest.mark.skip("This test uses the real analysis endpoint")
def test_system_against_prod(blueapi_run_engine: RunEngine):

    callback = TriggerAnalysisCallback(
        "https://i15-1-analysis.diamond.ac.uk",
        "read_number_of_frames_from_nxs",
        datapath="/entry/instrument/fastcs_eiger/fastcs_eiger",
    )

    _run_plan_with_callback(blueapi_run_engine, callback)

    assert callback.wait_on_and_retrieve_result() == 10


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_submit_called_with_correct_path(mock_client_cls, blueapi_run_engine):
    mock_client = mock_client_cls.return_value

    callback = TriggerAnalysisCallback(
        "http://fake-url",
        "my_analysis",
        extra_kw="value",
    )

    _run_plan_with_callback(blueapi_run_engine, callback)

    mock_client.submit.assert_called_once_with(
        "my_analysis",
        nexus_filepath=Path("/dls/i15-1/data/2026/cm44163-3/i15-1-95557.nxs"),
        extra_kw="value",
    )


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.LOGGER")
@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_missing_directory_logs_warning(mock_client_cls, mock_logger):
    mock_client = mock_client_cls.return_value

    RE = RunEngine()
    RE.md["scan_file"] = "scan123"  # directory missing

    callback = TriggerAnalysisCallback("url", "analysis")

    _run_plan_with_callback(RE, callback)

    mock_logger.warning.assert_called_once()
    mock_client.submit.assert_not_called()


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.LOGGER")
@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_missing_scan_file_logs_warning(mock_client_cls, mock_logger):
    mock_client = mock_client_cls.return_value

    RE = RunEngine()
    RE.md["data_session_directory"] = "/tmp/data"  # scan_file missing

    callback = TriggerAnalysisCallback("url", "analysis")

    _run_plan_with_callback(RE, callback)

    mock_logger.warning.assert_called_once()
    mock_client.submit.assert_not_called()


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_wait_on_and_retrieve_result(mock_client_cls):
    mock_client = mock_client_cls.return_value

    mock_result = MagicMock()
    mock_result.result = 42
    mock_client.get_result.return_value = mock_result

    callback = TriggerAnalysisCallback("url", "analysis")

    assert callback.wait_on_and_retrieve_result() == 42
    mock_client.get_result.assert_called_once()


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_submit_not_called_until_end_of_plan(mock_client_cls, blueapi_run_engine):
    mock_client = mock_client_cls.return_value

    callback = TriggerAnalysisCallback("url", "analysis")

    @bpp.subs_decorator(callback)
    @bpp.run_decorator()
    def my_plan():
        mock_client.submit.assert_not_called()

        yield from bps.null()

    blueapi_run_engine(my_plan())

    mock_client.submit.assert_called_once()


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
def test_submit_not_called_if_plan_fails(mock_client_cls, blueapi_run_engine):
    mock_client = mock_client_cls.return_value

    callback = TriggerAnalysisCallback("url", "analysis")

    @bpp.subs_decorator(callback)
    @bpp.run_decorator()
    def my_plan():
        raise ValueError()
        yield from bps.null()

    with pytest.raises(ValueError):
        blueapi_run_engine(my_plan())

    mock_client.submit.assert_not_called()
