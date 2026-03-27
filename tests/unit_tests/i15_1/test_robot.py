import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.beamlines.i15_1.robot import Robot
from ophyd_async.core import init_devices, set_mock_value

from crystallography_bluesky.i15_1.plans import robot_load, robot_unload


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


async def test_plan_loads_robot(robot: Robot):
    RE = RunEngine()
    RE(robot_load(1, 2, robot))

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2


async def test_plan_unloads_robot(robot: Robot):
    set_mock_value(robot.current_sample.puck, 1)
    set_mock_value(robot.current_sample.position, 2)

    RE = RunEngine()
    RE(robot_unload(robot))

    assert await robot.current_sample.puck.get_value() == 0
    assert await robot.current_sample.position.get_value() == 0
