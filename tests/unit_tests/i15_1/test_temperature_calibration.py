from unittest.mock import MagicMock, patch

from bluesky import RunEngine
from dodal.devices.beamlines.i15_1.blower import CalibratedBlower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.hexapod import Hexapod
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock

from crystallography_bluesky.i15_1.plans import temperature_calibration
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
    calibrated_blower: CalibratedBlower,
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
            blower=calibrated_blower,
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
        blower=calibrated_blower,
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
        calibrated_blower,
    )
    patch_robot_unload.assert_called_once_with()
