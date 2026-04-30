import pytest
from bluesky import RunEngine
from dodal.beamlines.i15_1 import cam_1
from dodal.common.visit import DataCollectionIdentifier, StaticVisitPathProvider
from ophyd_async.core import init_devices
from ophyd_async.epics.adcore import ADImageMode, ContAcqDetector

from crystallography_bluesky.i15_1.plans.snapshots import take_snapshot


@pytest.fixture
async def camera(tmp_path) -> ContAcqDetector:
    assert tmp_path.exists()
    path_provider = StaticVisitPathProvider("i15_1", tmp_path)
    path_provider._filename_provider.collectionId = DataCollectionIdentifier(
        collectionNumber=0
    )
    async with init_devices(mock=True):
        camera = cam_1(path_provider)

    await camera.driver.image_mode.set(ADImageMode.CONTINUOUS)
    await camera.driver.acquire.set(True)

    return camera


def test_take_snapshot_plan(run_engine: RunEngine, camera: ContAcqDetector):
    run_engine(take_snapshot(camera))
