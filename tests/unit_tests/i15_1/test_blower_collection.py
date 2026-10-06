from functools import partial
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.attenuators import (
    FastAttenuatorDemand,
    SlowAttenuatorPositions,
)
from dodal.devices.beamlines.i15_1.blower import CalibratedBlower
from dodal.devices.zebra.zebra import ArmDemand

from crystallography_bluesky.i15_1.plans.blower_collection import blower_collection
from crystallography_bluesky.i15_1.plans.generic_collection import (
    AuxiliaryScanType,
    DataCollectionScanType,
    GenericCollectionDevices,
)
from crystallography_bluesky.i15_1.plans.room_temperature_collection import (
    CollectionSpecPerPosition,
)


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
    calibrated_blower: CalibratedBlower,
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
            scan_type=DataCollectionScanType.DATA_COLLECTION,
            generic_collection_devices=common_collection_devices,
            blower=calibrated_blower,
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
    calibrated_blower: CalibratedBlower,
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
            scan_type=DataCollectionScanType.DATA_COLLECTION,
            generic_collection_devices=common_collection_devices,
            blower=calibrated_blower,
        )
    )

    expected_per_sec = ramp_rate_per_min / 60
    assert await calibrated_blower.ramp_rate_c_per_sec.get_value() == expected_per_sec


def test_blower_collection_collects_at_all_specified_temperatures(
    common_collection_devices: GenericCollectionDevices,
    calibrated_blower: CalibratedBlower,
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
            scan_type=DataCollectionScanType.DATA_COLLECTION,
            generic_collection_devices=common_collection_devices,
            blower=calibrated_blower,
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
                    and msg.obj.name == common_collection_devices.zebra.pc.arm.name
                    and msg.args[0] == ArmDemand.ARM
                ),
            )


@patch(
    "crystallography_bluesky.i15_1.plans.blower_collection.setup_and_teardown_collection"
)
async def test_blower_collection_adds_expected_info_to_metadata(
    mock_setup: MagicMock,
    common_collection_devices: GenericCollectionDevices,
    calibrated_blower: CalibratedBlower,
):
    run_engine = RunEngine()
    run_engine(
        blower_collection(
            time_per_collection=1.0,
            exposure_time_per_frame=0.01,
            temperatures_celsius=[25, 50],
            ramp_rate_c_per_min=100,
            settle_time=0.5,
            scan_type=AuxiliaryScanType.EMPTY_CAPILLARY,
            generic_collection_devices=common_collection_devices,
            blower=calibrated_blower,
        )
    )
    _, kwargs = mock_setup.call_args
    assert kwargs["metadata"] == {
        "data_shape": [(2, "temperatures_celsius"), (100, "collection")],
        "variables": {"temperatures_celsius": [25, 50]},
        "collection_specification": {
            10.0: CollectionSpecPerPosition(
                frames=5,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_0_001,
                fast_attenuator=FastAttenuatorDemand.IN,
            ),
            20.0: CollectionSpecPerPosition(
                frames=5,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_0_01,
                fast_attenuator=FastAttenuatorDemand.IN,
            ),
            30.0: CollectionSpecPerPosition(
                frames=10,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_0_1,
                fast_attenuator=FastAttenuatorDemand.IN,
            ),
            40.0: CollectionSpecPerPosition(
                frames=20,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_10,
                fast_attenuator=FastAttenuatorDemand.OUT,
            ),
            50.0: CollectionSpecPerPosition(
                frames=30,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_50,
                fast_attenuator=FastAttenuatorDemand.OUT,
            ),
            60.0: CollectionSpecPerPosition(
                frames=30,
                slow_attenuator_position=SlowAttenuatorPositions.TRANS_100,
                fast_attenuator=FastAttenuatorDemand.OUT,
            ),
        },
        "blower_calibration": {
            "real_to_setpoint": {
                "coefficients": pytest.approx(
                    (
                        1.3632771786784056e-06,
                        -0.00012637763892185146,
                        1.2595608567266412,
                        -8.873849368257947,
                    )
                )
            },
            "rows": [
                [50.0, 0.62034],
                [100.0, 16.89903],
                [150.0, 26.49641],
                [200.0, 33.91664],
                [250.0, 47.85712],
                [300.0, 62.41245],
                [350.0, 80.13215],
                [400.0, 96.91991],
                [450.0, 115.6384],
                [500.0, 135.89034],
                [550.0, 155.75917],
            ],
            "column_names": ["setpoint", "negative_error"],
        },
    }


def test_by_default_blower_collection_reads_raw_and_calibrated_temperature(
    common_collection_devices: GenericCollectionDevices,
    calibrated_blower: CalibratedBlower,
):
    """Test that temperatures read at each tth."""
    temperatures = [25.0, 50.0, 75.0]

    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        blower_collection(
            time_per_collection=1.0,
            exposure_time_per_frame=0.01,
            temperatures_celsius=temperatures,
            ramp_rate_c_per_min=60,
            settle_time=0.1,
            scan_type=DataCollectionScanType.DATA_COLLECTION,
            generic_collection_devices=common_collection_devices,
            blower=calibrated_blower,
        )
    )
    frames = int(1.0 / 0.01)
    for _ in temperatures:
        for _ in range(frames):
            msgs = assert_message_and_return_remaining(
                msgs,
                predicate=lambda msg: (
                    msg.command == "read"
                    and msg.obj.name == calibrated_blower.temperature.name
                ),
            )
            msgs = assert_message_and_return_remaining(
                msgs,
                predicate=lambda msg: (
                    msg.command == "read"
                    and msg.obj.name == calibrated_blower.raw_temperature.name
                ),
            )
