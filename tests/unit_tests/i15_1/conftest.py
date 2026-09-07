from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bluesky import RunEngine
from daq_config_server.client import ConfigClient
from daq_config_server.models.i15_1.positions_to_times import AnglesToTimes
from dodal.devices.beamlines.i15_1.attenuator import Attenuator
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.laue import LaueMonochrometer
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.motors import XYZStage
from dodal.devices.tetramm import SummingTetrammDetector
from dodal.devices.zebra.zebra import Zebra, ZebraMapping
from dodal.devices.zebra.zebra_constants_mapping import ZebraTTLOutputs
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
async def i0(path_provider: StaticPathProvider) -> SummingTetrammDetector:
    async with init_devices(mock=True):
        i0 = SummingTetrammDetector(
            "",
            path_provider,
            name="i0",
        )
    return i0


@pytest.fixture
async def zebra() -> Zebra:
    async with init_devices(mock=True):
        zebra = Zebra(
            ZebraMapping(outputs=ZebraTTLOutputs(TTL_EIGER=3, TTL_I0=2)),
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
async def attenuator() -> Attenuator:
    async with init_devices(mock=True):
        attenuator = Attenuator("", "")

    return attenuator


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
        xtal = LaueMonochrometer("", ConfigClient.from_url(""), "")
    return xtal


@pytest.fixture
async def common_collection_devices(
    eiger: EigerDetector,
    i0: SummingTetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
    xtal: LaueMonochrometer,
    attenuator: Attenuator,
) -> GenericCollectionDevices:
    return GenericCollectionDevices(
        eiger, i0, zebra, robot, tth, fast_shutter, xtal, attenuator
    )


@pytest.fixture
async def blower() -> Blower:
    """Blower device for testing."""
    async with init_devices(mock=True):
        blower = Blower("", "", "", MagicMock(), "")
    return blower


@pytest.fixture
def positions_to_fraction():
    return {
        10: 0.05,
        20: 0.05,
        30: 0.1,
        40: 0.2,
        50: 0.3,
        60: 0.3,
    }


@pytest.fixture
def mock_positions_to_fraction_config_client(positions_to_fraction):
    mock_client = MagicMock()
    mock_client.get_file_contents = MagicMock(
        wraps=lambda _, __: AnglesToTimes(
            tth_angle_to_collection_time=positions_to_fraction
        )
    )
    with patch(
        "crystallography_bluesky.i15_1.plans.room_temperature_collection.get_config_client",
        return_value=mock_client,
    ):
        yield mock_client
