from pathlib import Path

import pytest
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from ophyd_async.core import StaticFilenameProvider, StaticPathProvider, init_devices
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.take_eiger_data import take_eiger_data


@pytest.fixture
async def eiger() -> EigerDetector:
    async with init_devices(mock=True):
        eiger = EigerDetector(
            name="fastcs-eiger",
            prefix="",
            path_provider=StaticPathProvider(StaticFilenameProvider(""), Path("")),
        )
    return eiger


def test_take_eiger_data_makes_expected_calls(eiger: EigerDetector):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(take_eiger_data(10, 0.1, eiger))
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "unstage" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "stage" and msg.obj.name == "fastcs-eiger",
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
        predicate=lambda msg: (
            msg.command == "trigger" and msg.obj.name == "fastcs-eiger-detector-trigger"
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
        predicate=lambda msg: (
            msg.command == "collect" and msg.obj.name == "fastcs-eiger"
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "close_run",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "unstage" and msg.obj.name == "fastcs-eiger"
        ),
    )
