from unittest.mock import AsyncMock

import pytest
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from dodal.common.visit import DataCollectionIdentifier, StaticVisitPathProvider
from ophyd_async.core import init_devices
from ophyd_async.epics.adcore import ADImageMode, ADWriterFactory, ContAcqDetector

from crystallography_bluesky.i15_1.plans.snapshots import take_snapshot


@pytest.fixture
async def camera(tmp_path) -> ContAcqDetector:
    path_provider = StaticVisitPathProvider("i15_1", tmp_path)
    path_provider._filename_provider.collectionId = DataCollectionIdentifier(
        collectionNumber=0
    )
    async with init_devices(mock=True):
        camera = ContAcqDetector("", ADWriterFactory.jpeg(path_provider), name="cam_1")

    await camera.driver.image_mode.set(ADImageMode.CONTINUOUS)
    await camera.driver.acquire.set(True)

    camera.jpeg.file_path_exists.get_value = AsyncMock(return_value=True)  # type: ignore

    return camera


def test_take_snapshot_plan_makes_expected_calls(camera: ContAcqDetector):
    run_engine = RunEngineSimulator()

    msgs = run_engine.simulate_plan(take_snapshot(camera))

    msgs = assert_message_and_return_remaining(
        msgs, predicate=lambda msg: msg.command == "open_run"
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "stage" and msg.obj.name == "cam_1",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "prepare" and msg.obj.name == "cam_1",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "trigger" and msg.obj.name == "cam_1",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "read" and msg.obj.name == "cam_1",
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: msg.command == "unstage" and msg.obj.name == "cam_1",
    )
    msgs = assert_message_and_return_remaining(
        msgs, predicate=lambda msg: msg.command == "close_run"
    )
