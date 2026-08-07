import pytest
from bluesky import RunEngine
from dodal.devices.zebra.zebra import TrigSource, Zebra
from ophyd_async.core import get_mock_put

from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_hardware_triggering,
    setup_zebra_for_software_triggering,
)


def test_setup_zebra_for_hardware_triggering_sets_expected_pvs(
    run_engine: RunEngine, zebra: Zebra
):
    run_engine(setup_zebra_for_hardware_triggering(zebra, 100, 0.1))
    get_mock_put(zebra.pc.pulse_max).assert_called_once_with(100)
    get_mock_put(zebra.pc.pulse_source).assert_called_once_with(TrigSource.TIME)
    get_mock_put(zebra.pc.pulse_start).assert_called_once_with(0)
    get_mock_put(zebra.pc.pulse_width).assert_called_once_with(0.05)
    get_mock_put(zebra.pc.pulse_step).assert_called_once_with(0.1)
    get_mock_put(zebra.pc.gate_width).assert_called_once_with(10)

    get_mock_put(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER]
    ).assert_called_once_with(31)
    get_mock_put(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0]
    ).assert_called_once_with(31)


def test_setup_zebra_for_hardware_raises_error_if_pulse_width_less_than_frame_time(
    run_engine: RunEngine, zebra: Zebra
):
    with pytest.raises(AssertionError):
        run_engine(setup_zebra_for_hardware_triggering(zebra, 100, 0.1, 0.2))


def test_setup_zebra_for_software_triggering_sets_expected_pvs(
    run_engine: RunEngine, zebra: Zebra
):
    run_engine(setup_zebra_for_software_triggering(zebra))

    get_mock_put(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER]
    ).assert_called_once_with(60)
    get_mock_put(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0]
    ).assert_called_once_with(60)
