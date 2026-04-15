import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.beamlines.i15_1.gonio_interlock import GonioInterlock
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.hutch_shutter import HutchInterlock
from ophyd_async.core import init_devices, set_mock_value

from crystallography_bluesky.i15_1.plans import robot_load, robot_unload


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


@pytest.fixture
async def hutch_interlock() -> HutchInterlock:
    async with init_devices(mock=True):
        hutch_interlock = HutchInterlock("", "")
    return hutch_interlock


@pytest.fixture
async def gonio_interlock() -> GonioInterlock:
    async with init_devices(mock=True):
        gonio_interlock = GonioInterlock("", "")
    return gonio_interlock


async def test_plan_loads_robot(robot: Robot, hutch_interlock: HutchInterlock):
    RE = RunEngine()
    RE(robot_load(1, 2, robot, hutch_interlock))

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2


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


@pytest.mark.parametrize(
    "status, reason",
    (
        [65535, "Hutch status was not 0, but instead 2."],
        [65535, "Hutch status was not 0, but instead 7."],
    ),
)
async def test_correct_error_is_raised_when_gonio_is_not_safe_to_operate(
    robot: Robot,
    hutch_interlock: HutchInterlock,
    gonio_interlock: GonioInterlock,
    status: float,
    reason: str,
):
    set_mock_value(gonio_interlock.status, 65535)
    RE = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        RE(robot_load(1, 2, robot, hutch_interlock))
