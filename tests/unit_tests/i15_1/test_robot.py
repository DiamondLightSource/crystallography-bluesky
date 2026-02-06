import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.beamlines.i15_1.robot import Robot
from ophyd_async.core import init_devices

from crystallography_bluesky.i15_1.plans import robot_load


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot(prefix="")

    return robot


async def test_plan_loads_robot(robot: Robot):
    RE = RunEngine()
    RE(robot_load(1, 2, robot))

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2
