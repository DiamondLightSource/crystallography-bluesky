from unittest.mock import patch

import bluesky.plan_stubs as bps
from bluesky import RunEngine
from dodal.devices.beamlines.i15_1.beam_health import BeamHealth
from ophyd_async.core import set_mock_value

from crystallography_bluesky.i15_1.plans import wait_for_beam


def test_wait_for_beam_returns_immediately_if_beam_is_healthy(
    beam_health: BeamHealth,
):
    set_mock_value(beam_health._healthy_float, 1.0)
    run_engine = RunEngine()
    with patch(
        "crystallography_bluesky.i15_1.plans.wait_for_beam.bps.sleep"
    ) as mock_sleep:
        run_engine(wait_for_beam(beam_health))
    mock_sleep.assert_not_called()


def test_wait_for_beam_waits_until_beam_healthy_to_return(
    beam_health: BeamHealth,
):
    i = 0

    def _mock_sleep(*_, **__):
        nonlocal i
        yield from bps.null()
        i += 1
        if i == 10:
            set_mock_value(beam_health._healthy_float, 1.0)

    run_engine = RunEngine()
    with patch(
        "crystallography_bluesky.i15_1.plans.wait_for_beam.bps.sleep",
        side_effect=_mock_sleep,
    ) as mock_sleep:
        run_engine(wait_for_beam(beam_health))
    assert mock_sleep.call_count == 10
