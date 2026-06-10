from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.motors import XYZStage
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.devices.zebra.zebra_controlled_shutter import ZebraFastShutter
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.centre_sample import centre_sample
from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
)


def test_centre_sample_plan_makes_expected_calls(
    common_collection_devices: GenericCollectionDevices,
    hexapod: XYZStage,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        centre_sample(10, 20, 10, 0.01, common_collection_devices, hexapod)
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "set"
            and msg.obj.name == "fastcs-eiger-detector-ntrigger"
            and msg.args[0] == 10
        ),
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
                msg.command == "set"
                and msg.obj.name == "zebra-inputs-soft_in_1"
                and msg.args[0] == 1
            ),
        )
        msgs = assert_message_and_return_remaining(
            msgs,
            predicate=lambda msg: msg.command == "read" and msg.obj.name == "hexapod",
        )
        # Needs https://github.com/DiamondLightSource/crystallography-bluesky/issues/78
        # to test better as all moves are relative
        msgs = assert_message_and_return_remaining(
            msgs,
            predicate=lambda msg: msg.command == "set" and msg.obj.name == "hexapod-z",
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


def test_centre_sample_moved_to_start_before_stage(
    common_collection_devices: GenericCollectionDevices,
    hexapod: XYZStage,
):
    run_engine = RunEngineSimulator()
    msgs = run_engine.simulate_plan(
        centre_sample(10, 20, 10, 0.01, common_collection_devices, hexapod)
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "set" and msg.obj.name == "hexapod-z" and msg.args[0] == 10
        ),
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "stage" and msg.obj.name == "fastcs-eiger",
    )


@pytest.fixture
def blueapi_run_engine():
    # This adds the info the blueapi will add in prod
    RE = RunEngine()
    RE.md["data_session_directory"] = "/dls/i15-1/data/2026/cm44163-3"
    RE.md["scan_file"] = "i15-1-95557"
    return RE


@patch("crystallography_bluesky.i15_1.callbacks.analysis_callback.AnalysisClient")
@patch("crystallography_bluesky.i15_1.plans.centre_sample.generic_collection")
def test_centre_sample_calls_analysis_and_retrieves_result(
    mock_generic_collection: MagicMock,
    mock_analysis_client_cls: MagicMock,
    hexapod: XYZStage,
    blueapi_run_engine: RunEngine,
):
    mock_analysis_client_cls.return_value = (mock_client := MagicMock())

    @bpp.run_decorator()
    def my_plan(*_):
        yield from bps.null()

    mock_generic_collection.side_effect = my_plan
    blueapi_run_engine(centre_sample(10, 20, 10, 0.01, MagicMock(), hexapod))

    mock_client.submit.assert_called_once()
    mock_client.get_result.assert_called_once()
