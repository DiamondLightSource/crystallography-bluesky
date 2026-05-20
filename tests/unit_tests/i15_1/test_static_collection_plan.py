from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.static_collection import (
    static_collection_plan,
)


def test_take_eiger_and_i0_data_makes_expected_calls(
    eiger: EigerDetector, i0: TetrammDetector, zebra: Zebra, robot: Robot, tth: Motor
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        static_collection_plan(10, 0.01, eiger, i0, zebra, robot, tth)
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
            msg.command == "prepare" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "prepare" and msg.obj.name == "i0",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "declare_stream",
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
