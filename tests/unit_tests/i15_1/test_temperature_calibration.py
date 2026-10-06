from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
from bluesky import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.hexapod import Hexapod
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.interlocks import (
    IntPLCInterlock,
    PSSInterlock,
)

from crystallography_bluesky.i15_1.plans import (
    temperature_calibration,
)
from crystallography_bluesky.i15_1.plans.generic_collection import (
    AuxiliaryScanType,
    GenericCollectionDevices,
)


@patch("crystallography_bluesky.i15_1.plans.temperature_calibration.robot_unload")
@patch("crystallography_bluesky.i15_1.plans.temperature_calibration.blower_collection")
@patch("crystallography_bluesky.i15_1.plans.temperature_calibration.centre_sample")
@patch("crystallography_bluesky.i15_1.plans.temperature_calibration.robot_load")
def test_temperature_calibration_calls_expected_plans(
    patch_robot_load: MagicMock,
    patch_centre_sample: MagicMock,
    patch_blower_collection: MagicMock,
    patch_robot_unload: MagicMock,
    common_collection_devices: GenericCollectionDevices,
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    run_engine = RunEngine()
    run_engine(
        temperature_calibration(
            capillary="bs1.5",
            contents="Silicon",
            time_per_collection=100,
            exposure_time_per_frame=0.1,
            temperatures_celsius=[100, 200, 300, 400, 500],
            ramp_rate_c_per_min=0,
            settle_time=5,
            generic_collection_devices=common_collection_devices,
            robot=robot,
            hutch_interlock=hutch_interlock,
            gonio_interlock=gonio_interlock,
            hexapod=hexapod,
            blower=blower,
            cobra=cobra,
        )
    )

    patch_robot_load.assert_called_once_with(
        puck=1,
        position=4,
        robot=robot,
        hutch_interlock=hutch_interlock,
        gonio_interlock=gonio_interlock,
        hexapod=hexapod,
        blower=blower,
        cobra=cobra,
    )
    patch_centre_sample.assert_called_once_with(
        -20, 5, 100, 0.1, common_collection_devices, hexapod
    )
    patch_blower_collection.assert_called_once_with(
        100,
        0.1,
        [100, 200, 300, 400, 500],
        0,
        5,
        AuxiliaryScanType.STANDARD_SAMPLE,
        common_collection_devices,
        blower,
        signals_to_read_per_point=[blower.raw_temperature],
    )
    patch_robot_unload.assert_called_once_with(
        robot, hutch_interlock, gonio_interlock, hexapod
    )


def do_nothing(*_, **__):
    yield from bps.null()


@patch(
    "crystallography_bluesky.i15_1.plans.temperature_calibration.robot_load", do_nothing
)
@patch(
    "crystallography_bluesky.i15_1.plans.temperature_calibration.centre_sample",
    do_nothing,
)
@patch(
    "crystallography_bluesky.i15_1.plans.temperature_calibration.robot_unload",
    do_nothing,
)
def test_by_default_blower_collection_reads_raw_temperature_per_point(
    common_collection_devices: GenericCollectionDevices,
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    """Test that temperatures read at each tth."""
    temperatures = [25.0, 50.0, 75.0]

    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        temperature_calibration(
            capillary="fq1.0",
            contents="Si/Al2O3",
            time_per_collection=1.0,
            exposure_time_per_frame=0.01,
            temperatures_celsius=temperatures,
            ramp_rate_c_per_min=60,
            settle_time=0.1,
            generic_collection_devices=common_collection_devices,
            robot=robot,
            hutch_interlock=hutch_interlock,
            gonio_interlock=gonio_interlock,
            hexapod=hexapod,
            blower=blower,
            cobra=cobra,
        )
    )

    frames = int(1.0 / 0.01)
    for _ in temperatures:
        for _ in range(frames):
            msgs = assert_message_and_return_remaining(
                msgs,
                predicate=lambda msg: (
                    msg.command == "read"
                    and msg.obj.name == blower.raw_temperature.name
                ),
            )
