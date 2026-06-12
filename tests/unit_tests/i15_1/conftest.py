from pathlib import Path

import pytest
from bluesky import RunEngine
from daq_config_server import ConfigClient
from dodal.devices.beamlines.i15_1.laue import LaueMonochrometer
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.motors import XYZStage
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra, ZebraMapping
from dodal.devices.zebra.zebra_controlled_shutter import ZebraFastShutter
from ophyd_async.core import StaticFilenameProvider, StaticPathProvider, init_devices
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
)


@pytest.fixture
def run_engine():
    return RunEngine()


@pytest.fixture
def path_provider() -> StaticPathProvider:
    return StaticPathProvider(StaticFilenameProvider(""), Path(""))


@pytest.fixture
async def i0(path_provider: StaticPathProvider) -> TetrammDetector:
    async with init_devices(mock=True):
        i0 = TetrammDetector(
            "",
            path_provider,
            name="i0",
        )
    return i0


@pytest.fixture
async def zebra() -> Zebra:
    async with init_devices(mock=True):
        zebra = Zebra(
            ZebraMapping(),
            "",
            "zebra",
        )
    return zebra


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


@pytest.fixture
async def tth() -> Motor:
    async with init_devices(mock=True):
        tth = Motor("", "")

    return tth


@pytest.fixture
async def eiger(path_provider: StaticPathProvider) -> EigerDetector:
    async with init_devices(mock=True):
        eiger = EigerDetector(
            name="fastcs-eiger",
            prefix="",
            path_provider=path_provider,
        )
    return eiger


@pytest.fixture
async def fast_shutter() -> ZebraFastShutter:
    async with init_devices(mock=True):
        zebra_fast_shutter = ZebraFastShutter("", "", "fast_shutter")
    return zebra_fast_shutter


@pytest.fixture
async def hexapod() -> XYZStage:
    async with init_devices(mock=True):
        hexapod = XYZStage("")
    return hexapod


@pytest.fixture
async def xtal() -> LaueMonochrometer:
    async with init_devices(mock=True):
        xtal = LaueMonochrometer("", ConfigClient(""), "")
    return xtal


@pytest.fixture
async def common_collection_devices(
    eiger: EigerDetector,
    i0: TetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
    xtal: LaueMonochrometer,
) -> GenericCollectionDevices:
    return GenericCollectionDevices(eiger, i0, zebra, robot, tth, fast_shutter, xtal)
