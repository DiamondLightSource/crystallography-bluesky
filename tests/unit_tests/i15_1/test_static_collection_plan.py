from unittest.mock import AsyncMock, MagicMock

import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.devices.zebra.zebra_controlled_shutter import OpenClose, ZebraFastShutter
from ophyd_async.core import get_mock_put
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.static_collection import (
    static_collection_plan,
)


def test_take_eiger_and_i0_data_makes_expected_calls(
    eiger: EigerDetector,
    i0: TetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        static_collection_plan(10, 0.01, eiger, i0, zebra, robot, tth, fast_shutter)
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "unstage" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "unstage" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "stage" and msg.obj.name == "fastcs-eiger",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "stage" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "open_run",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "declare_stream" and msg.kwargs["name"] == "baseline"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "read" and msg.obj.name == "robot-spinner",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "read" and msg.obj.name == "tth",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "prepare" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "prepare" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "declare_stream" and msg.kwargs["name"] == "primary"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "kickoff" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "kickoff" and msg.obj.name == "i0",
    )

    for _ in range(10):
        msgs = assert_message_and_return_remaining(
            msgs,
            predicate=lambda msg: (
                msg.command == "trigger"
                and msg.obj.name == "fastcs-eiger-detector-trigger"
            ),
        )
        msgs = assert_message_and_return_remaining(
            msgs,
            predicate=lambda msg: (
                msg.command == "set"
                and msg.obj.name == "zebra-inputs-soft_in_1"
                and msg.args[0] == 1
            ),
        )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "complete" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "complete" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "collect",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "read" and msg.obj.name == "robot-spinner",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "read" and msg.obj.name == "tth",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "close_run",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "unstage" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "unstage" and msg.obj.name == "fastcs-eiger"
        ),
    )


def test_shutter_opened_before_detectors_kicked_off(
    eiger: EigerDetector,
    i0: TetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        static_collection_plan(10, 0.01, eiger, i0, zebra, robot, tth, fast_shutter)
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "set"
            and msg.obj.name == "fast_shutter"
            and msg.args[0] == OpenClose.OPEN
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "kickoff" and msg.obj.name == "fastcs-eiger"
        ),
    )


def test_shutter_closed_after_complete(
    eiger: EigerDetector,
    i0: TetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        static_collection_plan(10, 0.01, eiger, i0, zebra, robot, tth, fast_shutter)
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "complete" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "set"
            and msg.obj.name == "fast_shutter"
            and msg.args[0] == OpenClose.CLOSE
        ),
    )


@pytest.skip(
    "Needs https://github.com/DiamondLightSource/crystallography-bluesky/issues/78"
)
async def test_given_plan_throws_exception_then_shutters_closed(
    eiger: EigerDetector,
    i0: TetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
    run_engine: RunEngine,
):
    run_engine = RunEngine()

    zebra.inputs.soft_in_1.set = AsyncMock(ValueError)

    with pytest.raises(ValueError):
        run_engine(
            static_collection_plan(10, 0.01, eiger, i0, zebra, robot, tth, fast_shutter)
        )

    get_mock_put(fast_shutter._set_pv).assert_called()
    assert (await fast_shutter.shutter_state.get_value()) == OpenClose.CLOSE
