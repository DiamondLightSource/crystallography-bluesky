import asyncio
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.simulators import RunEngineSimulator

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
)
from crystallography_bluesky.i15_1.plans.room_temperature_collection import (
    _calculate_number_of_frames,
    data_collection,
    positions_to_percentage,
)


def test_calculate_number_of_frames_calculates_expected_frame_count():
    frames = _calculate_number_of_frames(
        percentage_of_time=0.2,
        full_collection_time=10,
        exposure_time_per_frame=0.5,
    )

    assert frames == 4


@patch("crystallography_bluesky.i15_1.plans.room_temperature_collection.LOGGER")
def test_calculate_number_of_frames_returns_one_and_warns_when_no_frames(
    logger: MagicMock,
):
    frames = _calculate_number_of_frames(
        percentage_of_time=0.05,
        full_collection_time=0.01,
        exposure_time_per_frame=1,
    )

    assert frames == 1
    logger.warning.assert_called_once()
    assert "no frames" in logger.warning.call_args.args[0]


@patch(
    "crystallography_bluesky.i15_1.plans.room_temperature_collection.setup_and_teardown_collection"
)
def test_data_collection_calls_setup_with_expected_arguments(
    mock_setup: MagicMock,
    common_collection_devices: GenericCollectionDevices,
):
    baseline_devices = [common_collection_devices.tth]

    def fake_setup(*_, **__):
        yield from bps.null()

    mock_setup.side_effect = fake_setup

    run_engine = RunEngine()
    run_engine(
        data_collection(
            full_collection_time=2,
            exposure_time_per_frame=0.01,
            generic_collection_devices=common_collection_devices,
            baseline_devices=baseline_devices,
        )
    )

    expected_total_frames = sum(
        _calculate_number_of_frames(percentage, 2, 0.01)
        for percentage in positions_to_percentage.values()
    )

    setup_call_args = mock_setup.call_args.args
    assert setup_call_args[0] == expected_total_frames
    assert setup_call_args[1] == 0.01
    assert setup_call_args[2] is common_collection_devices
    assert callable(setup_call_args[3])
    assert (
        setup_call_args[4]
        == [
            common_collection_devices.robot.spinner,
            common_collection_devices.xtal,
        ]
        + baseline_devices
    )

    assert (
        asyncio.run(common_collection_devices.tth.movable_logic.calculate_timeout())
        == 60
    )


def test_data_collection_takes_one_frame_per_position_for_short_collection(
    common_collection_devices: GenericCollectionDevices,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        data_collection(
            full_collection_time=0.02,
            exposure_time_per_frame=0.01,
            generic_collection_devices=common_collection_devices,
        )
    )

    tth_positions = [
        msg.args[0] for msg in msgs if msg.command == "set" and msg.obj.name == "tth"
    ]
    assert tth_positions == list(positions_to_percentage.keys())

    detector_high_triggers = [
        msg
        for msg in msgs
        if msg.command == "set"
        and msg.obj.name == "zebra-inputs-soft_in_1"
        and msg.args[0] == 1
    ]
    assert len(detector_high_triggers) == len(positions_to_percentage)

    tth_stream_creates = [
        msg
        for msg in msgs
        if msg.command == "create" and msg.kwargs.get("name") == "tth"
    ]
    assert len(tth_stream_creates) == len(positions_to_percentage)
