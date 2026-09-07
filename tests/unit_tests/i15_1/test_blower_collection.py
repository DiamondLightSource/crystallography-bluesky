from functools import partial
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.blower import Blower

from crystallography_bluesky.i15_1.plans.blower_collection import blower_collection
from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
)


@pytest.fixture(autouse=True)
def always_mock_collection_spec_config_client(
    mock_collection_spec_config_client,
): ...


@pytest.mark.parametrize(
    "temperatures, time_per_collection, exposure_per_frame, expected_frames",
    (
        [[25.0], 20, 0.1, 200],
        [[25.0, 50.0], 20, 0.1, 400],
        [[25.0, 50.0], 40, 0.1, 800],
        [[25.0, 50.0], 40, 1, 80],
    ),
)
@patch(
    "crystallography_bluesky.i15_1.plans.blower_collection.setup_and_teardown_collection"
)
def test_blower_collection_calls_setup_with_expected_frame_counts(
    mock_setup: MagicMock,
    common_collection_devices: GenericCollectionDevices,
    blower: Blower,
    temperatures,
    time_per_collection,
    exposure_per_frame,
    expected_frames,
):

    def fake_setup(*_, **__):
        yield from bps.null()

    mock_setup.side_effect = fake_setup

    run_engine = RunEngine()
    run_engine(
        blower_collection(
            time_per_collection=time_per_collection,
            exposure_time_per_frame=exposure_per_frame,
            temperatures_celsius=temperatures,
            ramp_rate_c_per_min=10,
            settle_time=0.5,
            generic_collection_devices=common_collection_devices,
            blower=blower,
        )
    )

    setup_call_args = mock_setup.call_args.args
    assert setup_call_args[0] == expected_frames


@patch(
    "crystallography_bluesky.i15_1.plans.blower_collection.setup_and_teardown_collection"
)
async def test_blower_collection_sets_blower_ramp_rate_from_per_minute_to_per_second(
    mock_setup: MagicMock,
    common_collection_devices: GenericCollectionDevices,
    blower: Blower,
):
    """Test that blower ramp rate is converted from per_min to per_sec."""
    ramp_rate_per_min = 120  # 2 degrees per second

    def fake_setup(*_, **__):
        yield from bps.null()

    mock_setup.side_effect = fake_setup

    run_engine = RunEngine()
    run_engine(
        blower_collection(
            time_per_collection=1.0,
            exposure_time_per_frame=0.01,
            temperatures_celsius=[25, 50],
            ramp_rate_c_per_min=ramp_rate_per_min,
            settle_time=0.5,
            generic_collection_devices=common_collection_devices,
            blower=blower,
        )
    )

    expected_per_sec = ramp_rate_per_min / 60
    assert await blower.ramp_rate_c_per_sec.get_value() == expected_per_sec


def test_blower_collection_collects_at_all_specified_temperatures(
    common_collection_devices: GenericCollectionDevices,
    blower: Blower,
):
    """Test that data collection occurs at each specified temperature."""
    temperatures = [25.0, 50.0, 75.0]

    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        blower_collection(
            time_per_collection=1.0,
            exposure_time_per_frame=0.01,
            temperatures_celsius=temperatures,
            ramp_rate_c_per_min=60,
            settle_time=0.1,
            generic_collection_devices=common_collection_devices,
            blower=blower,
        )
    )

    for temp in temperatures:

        def _check_temp_being_set(msg, temp):
            return (
                msg.command == "set"
                and msg.obj.name == "blower-temperature"
                and msg.args[0] == temp
            )

        msgs = assert_message_and_return_remaining(
            msgs,
            partial(_check_temp_being_set, temp=temp),
        )

        for tth in [10, 20, 30, 40, 50, 60]:

            def _check_tth_being_set(msg, tth):
                return (
                    msg.command == "set"
                    and msg.obj.name == "tth"
                    and msg.args[0] == tth
                )

            msgs = assert_message_and_return_remaining(
                msgs,
                predicate=partial(_check_tth_being_set, tth=tth),
            )

            msgs = assert_message_and_return_remaining(
                msgs,
                predicate=lambda msg: (
                    msg.command == "set"
                    and msg.obj.name
                    == common_collection_devices.zebra.inputs.soft_in_1.name
                    and msg.args[0] == 1
                ),
            )
