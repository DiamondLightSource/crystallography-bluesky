import pytest
from bluesky.run_engine import RunEngine
from daq_config_server import ConfigClient
from daq_config_server.models.i15_1.xpdf_parameters import TemperatureControllerParams
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.hutch_shutter import HutchInterlock
from ophyd_async.core import get_mock_put, init_devices, set_mock_value

from crystallography_bluesky.i15_1.plans import robot_load, robot_unload
from crystallography_bluesky.i15_1.plans.robot import (
    move_devices_to_beam_position,
    prepare_beamline_for_robot_load,
)


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


@pytest.fixture
async def blower() -> Blower:
    async with init_devices(mock=True):
        blower = Blower("", ConfigClient(""), "")

    def mock_config():
        return TemperatureControllerParams(
            beam_position=40.7,
            safe_position=6.0,
            settle_time=0,
            tolerance=5.0,
            units="C",
            ramp_units="/min",
            use_calibration=True,
            use_fast_cool=None,
            calibration_file="blower_cal_10_03_2026.txt",
        )

    blower.get_config = mock_config
    return blower


@pytest.fixture
async def cobra() -> Cobra:
    async with init_devices(mock=True):
        cobra = Cobra("", ConfigClient(""), "")

    def mock_config():
        return TemperatureControllerParams(
            beam_position=400.5,
            safe_position=5.0,
            settle_time=600,
            tolerance=5.0,
            units="K",
            ramp_units="/h",
            use_calibration=True,
            use_fast_cool=True,
            calibration_file="cobra_calibration_2025-09-11.txt",
        )

    cobra.get_config = mock_config
    return cobra


@pytest.fixture
async def hutch_interlock() -> HutchInterlock:
    async with init_devices(mock=True):
        hutch_interlock = HutchInterlock("", "")
    return hutch_interlock


async def test_plan_loads_robot(
    robot: Robot, hutch_interlock: HutchInterlock, blower: Blower, cobra: Cobra
):
    RE = RunEngine()
    RE(robot_load(1, 2, robot, hutch_interlock, blower, cobra))

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2


async def test_prepare_beamline_for_robot_load(blower: Blower, cobra: Cobra):
    RE = RunEngine()
    RE(prepare_beamline_for_robot_load(blower, cobra))
    get_mock_put(blower.motor.user_setpoint).assert_called_once_with(6.0)
    get_mock_put(cobra.motor.user_setpoint).assert_called_once_with(5.0)


async def test_move_devices_into_beam_position(blower: Blower, cobra: Cobra):
    RE = RunEngine()
    RE(move_devices_to_beam_position(blower, cobra))
    get_mock_put(blower.motor.user_setpoint).assert_called_once_with(40.7)
    get_mock_put(cobra.motor.user_setpoint).assert_called_once_with(400.5)


async def test_robot_load_plan_moves_cobra_and_blower_into_safe_position(
    robot: Robot, hutch_interlock: HutchInterlock, blower: Blower, cobra: Cobra
):
    RE = RunEngine()
    RE(robot_load(1, 2, robot, hutch_interlock, blower, cobra))
    get_mock_put(blower.motor.user_setpoint).assert_called_once_with(6.0)
    get_mock_put(cobra.motor.user_setpoint).assert_called_once_with(5.0)


async def test_plan_unloads_robot(robot: Robot, hutch_interlock: HutchInterlock):
    set_mock_value(robot.current_sample.puck, 1)
    set_mock_value(robot.current_sample.position, 2)

    RE = RunEngine()
    RE(robot_unload(robot, hutch_interlock))

    assert await robot.current_sample.puck.get_value() == 0
    assert await robot.current_sample.position.get_value() == 0


@pytest.mark.parametrize(
    "status, reason",
    (
        [2, "Hutch status was not 0, but instead 2."],
        [7, "Hutch status was not 0, but instead 7."],
    ),
)
async def test_correct_error_is_raised_when_hutch_is_not_safe_to_operate(
    robot: Robot, hutch_interlock: HutchInterlock, status: int, reason: str
):
    set_mock_value(hutch_interlock.status, status)
    RE = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        RE(robot_load(1, 2, robot, hutch_interlock))
