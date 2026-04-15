import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.beamlines.i15_1.gonio_interlock import GonioInterlock
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.hutch_shutter import HutchInterlock
from dodal.devices.motors import XYZStage
from ophyd_async.core import init_devices, set_mock_value

from crystallography_bluesky.i15_1.plans import (
    move_hexapod_to_home_position,
    robot_load,
    robot_unload,
)


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


@pytest.fixture
async def hutch_interlock() -> HutchInterlock:
    async with init_devices(mock=True):
        hutch_interlock = HutchInterlock("", "")
    set_mock_value(hutch_interlock.status, 0)
    return hutch_interlock


@pytest.fixture
async def gonio_interlock() -> GonioInterlock:
    async with init_devices(mock=True):
        gonio_interlock = GonioInterlock("", "")
    set_mock_value(gonio_interlock.status, 65535)
    return gonio_interlock


@pytest.fixture
async def hexapod() -> XYZStage:
    async with init_devices(mock=True):
        hexapod = XYZStage("", "")
    return hexapod


@pytest.fixture
async def hexapod_rot() -> XYZStage:
    async with init_devices(mock=True):
        hexapod_rot = XYZStage("", "")
    return hexapod_rot


async def test_plan_loads_robot(
    robot: Robot,
    hutch_interlock: HutchInterlock,
    gonio_interlock: GonioInterlock,
    hexapod: XYZStage,
    hexapod_rot: XYZStage,
):
    RE = RunEngine()
    RE(robot_load(1, 2, robot, hutch_interlock, gonio_interlock, hexapod, hexapod_rot))

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2


async def test_plan_unloads_robot(
    robot: Robot,
    hutch_interlock: HutchInterlock,
    gonio_interlock: GonioInterlock,
    hexapod: XYZStage,
    hexapod_rot: XYZStage,
):
    set_mock_value(robot.current_sample.puck, 1)
    set_mock_value(robot.current_sample.position, 2)

    RE = RunEngine()
    RE(robot_unload(robot, hutch_interlock, gonio_interlock, hexapod, hexapod_rot))

    assert await robot.current_sample.puck.get_value() == 0
    assert await robot.current_sample.position.get_value() == 0


@pytest.mark.parametrize(
    "status, reason",
    (
        [2, "Experimental hutch interlock status was not safe to operate."],
        [7, "Experimental hutch interlock status was not safe to operate."],
    ),
)
async def test_correct_error_is_raised_when_hutch_is_not_safe_to_operate(
    robot: Robot,
    hutch_interlock: HutchInterlock,
    gonio_interlock: GonioInterlock,
    hexapod: XYZStage,
    hexapod_rot: XYZStage,
    status: int,
    reason: str,
):
    set_mock_value(hutch_interlock.status, status)
    RE = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        RE(
            robot_load(
                1, 2, robot, hutch_interlock, gonio_interlock, hexapod, hexapod_rot
            )
        )


@pytest.mark.parametrize(
    "status, reason",
    (
        [65439, "Goniometer interlock status was not safe to operate."],
        [65534, "Goniometer interlock status was not safe to operate."],
    ),
)
async def test_correct_error_is_raised_when_gonio_is_not_safe_to_operate(
    robot: Robot,
    hutch_interlock: HutchInterlock,
    gonio_interlock: GonioInterlock,
    hexapod: XYZStage,
    hexapod_rot: XYZStage,
    status: float,
    reason: str,
):
    set_mock_value(gonio_interlock.status, status)
    RE = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        RE(
            robot_load(
                1, 2, robot, hutch_interlock, gonio_interlock, hexapod, hexapod_rot
            )
        )


@pytest.mark.parametrize(
    "x_home, y_home, z_home, rx_home, ry_home, rz_home",
    ([1, 2, 3, 4, 5, 6], [0, 0, 0, 0, 0, 0]),
)
async def test_plan_moves_hexapod_to_home_position(
    hexapod: XYZStage,
    hexapod_rot: XYZStage,
    x_home: float,
    y_home: float,
    z_home: float,
    rx_home: float,
    ry_home: float,
    rz_home: float,
):
    RE = RunEngine()
    RE(
        move_hexapod_to_home_position(
            hexapod=hexapod,
            hexapod_rot=hexapod_rot,
            x_home=x_home,
            y_home=y_home,
            z_home=z_home,
            rx_home=rx_home,
            ry_home=ry_home,
            rz_home=rz_home,
        )
    )

    assert await hexapod.x.user_readback.get_value() == x_home
    assert await hexapod.y.user_readback.get_value() == y_home
    assert await hexapod.z.user_readback.get_value() == z_home
    assert await hexapod_rot.x.user_readback.get_value() == rx_home
    assert await hexapod_rot.y.user_readback.get_value() == ry_home
    assert await hexapod_rot.z.user_readback.get_value() == rz_home
