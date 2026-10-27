from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.hexapod import Hexapod
from dodal.devices.beamlines.i15_1.robot import Robot, SpinnerState
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock
from ophyd_async.core import get_mock_put, init_devices, set_mock_value

from crystallography_bluesky.i15_1.plans import (
    move_hexapod_to_home_position,
    robot_load,
    robot_unload,
)
from crystallography_bluesky.i15_1.plans.robot import prepare_beamline_for_robot_action


@pytest.fixture
async def hutch_interlock() -> PSSInterlock:
    async with init_devices(mock=True):
        hutch_interlock = PSSInterlock("", "")
    set_mock_value(hutch_interlock.status, 0)
    return hutch_interlock


@pytest.fixture
async def gonio_interlock() -> IntPLCInterlock:
    async with init_devices(mock=True):
        gonio_interlock = IntPLCInterlock("", "")
    set_mock_value(gonio_interlock.status, 65535)
    return gonio_interlock


@pytest.fixture
async def hexapod() -> Hexapod:
    async with init_devices(mock=True):
        hexapod = Hexapod("", "")
    return hexapod


async def test_plan_loads_robot(
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    run_engine = RunEngine()
    run_engine(
        robot_load(
            1,
            2,
            True,
            robot,
            hutch_interlock,
            gonio_interlock,
            hexapod,
            blower,
            cobra,
        )
    )

    assert await robot.puck_sel.get_value() == 1
    assert await robot.pos_sel.get_value() == 2


async def test_load_robot_plan_starts_spinner(
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    run_engine = RunEngine()
    run_engine(
        robot_load(
            1,
            2,
            True,
            robot,
            hutch_interlock,
            gonio_interlock,
            hexapod,
            blower,
            cobra,
        )
    )

    assert await robot.spinner.get_value() == SpinnerState.ON


async def test_prepare_beamline_for_robot_action_moves_sample_env_into_safe_position(
    blower: Blower,
    cobra: Cobra,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
):
    run_engine = RunEngine()
    run_engine(
        prepare_beamline_for_robot_action(
            blower, cobra, hutch_interlock, gonio_interlock, hexapod
        )
    )
    get_mock_put(blower.motor.user_setpoint).assert_called_once_with(6.0)
    # Cobra currently is not mounted on the beamline
    # get_mock_put(cobra.motor.user_setpoint).assert_called_once_with(5.0)


@pytest.mark.parametrize(
    "status, reason",
    (
        [2, "Experimental hutch interlock status was not safe to operate."],
        [7, "Experimental hutch interlock status was not safe to operate."],
    ),
)
async def test_correct_error_is_raised_when_hutch_is_not_safe_to_operate(
    blower: Blower,
    cobra: Cobra,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    status: int,
    reason: str,
):
    set_mock_value(hutch_interlock.status, status)
    run_engine = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        run_engine(
            prepare_beamline_for_robot_action(
                blower, cobra, hutch_interlock, gonio_interlock, hexapod
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
    blower: Blower,
    cobra: Cobra,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    status: float,
    reason: str,
):
    set_mock_value(gonio_interlock.status, status)
    run_engine = RunEngine()
    with pytest.raises(AssertionError, match=reason):
        run_engine(
            prepare_beamline_for_robot_action(
                blower, cobra, hutch_interlock, gonio_interlock, hexapod
            )
        )


@pytest.mark.parametrize(
    "x_home, y_home, z_home, rx_home, ry_home, rz_home",
    ([1, 2, 3, 4, 5, 6], [0, 0, 0, 0, 0, 0]),
)
async def test_plan_moves_hexapod_to_home_position(
    hexapod: Hexapod,
    x_home: float,
    y_home: float,
    z_home: float,
    rx_home: float,
    ry_home: float,
    rz_home: float,
):
    run_engine = RunEngine()
    run_engine(
        move_hexapod_to_home_position(
            hexapod=hexapod,
            x_home=x_home,
            y_home=y_home,
            z_home=z_home,
            rx_home=rx_home,
            ry_home=ry_home,
            rz_home=rz_home,
            wait=True,
        )
    )

    assert await hexapod.x.user_readback.get_value() == x_home
    assert await hexapod.y.user_readback.get_value() == y_home
    assert await hexapod.z.user_readback.get_value() == z_home
    assert await hexapod.rx.user_readback.get_value() == rx_home
    assert await hexapod.ry.user_readback.get_value() == ry_home
    assert await hexapod.rz.user_readback.get_value() == rz_home


@patch("crystallography_bluesky.i15_1.plans.robot.move_hexapod_to_home_position")
async def test_prepare_beamline_homes_hexapod(
    mock_home: MagicMock,
    blower: Blower,
    cobra: Cobra,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
):
    run_engine = RunEngine()
    run_engine(
        prepare_beamline_for_robot_action(
            blower,
            cobra,
            hutch_interlock,
            gonio_interlock,
            hexapod,
        )
    )
    mock_home.assert_called_once()


@patch("crystallography_bluesky.i15_1.plans.robot.prepare_beamline_for_robot_action")
async def test_robot_load_calls_prepare_beamline(
    mock_prepare: MagicMock,
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    run_engine = RunEngine()
    run_engine(
        robot_load(
            1,
            2,
            True,
            robot,
            hutch_interlock,
            gonio_interlock,
            hexapod,
            blower,
            cobra,
        )
    )
    mock_prepare.assert_called_once()


@patch("crystallography_bluesky.i15_1.plans.robot.prepare_beamline_for_robot_action")
async def test_robot_unload_calls_prepare_beamline(
    mock_prepare: MagicMock,
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    run_engine = RunEngine()
    run_engine(
        robot_unload(
            robot,
            hutch_interlock,
            gonio_interlock,
            hexapod,
            blower,
            cobra,
        )
    )
    mock_prepare.assert_called_once()


async def test_plan_unloads_robot(
    robot: Robot,
    hutch_interlock: PSSInterlock,
    gonio_interlock: IntPLCInterlock,
    hexapod: Hexapod,
    blower: Blower,
    cobra: Cobra,
):
    set_mock_value(robot.current_sample.puck, 1)
    set_mock_value(robot.current_sample.position, 2)

    run_engine = RunEngine()
    run_engine(
        robot_unload(robot, hutch_interlock, gonio_interlock, hexapod, blower, cobra)
    )

    assert await robot.current_sample.puck.get_value() == 0
    assert await robot.current_sample.position.get_value() == 0
