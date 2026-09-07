from functools import partial
from typing import Any

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.attenuator import Attenuator
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.motors import Motor
from dodal.log import LOGGER
from ophyd_async.core import SignalRW, StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.room_temperature_collection import (
    CollectionSpecification,
    get_collection_specification,
    inner_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_software_triggering,
)

devices = inject("")
blower = inject("blower")


def _collection(
    blower: Blower,
    tth: Motor,
    detector_trigger: SignalRW,
    attenuator: Attenuator,
    temperatures_celsius: list[float],
    collection_spec: CollectionSpecification,
    exposure_time_per_frame: float,
):
    for temperature in temperatures_celsius:
        LOGGER.info(f"Moving to temperature {temperature}")
        yield from bps.mv(blower.temperature, temperature)
        yield from inner_collection(
            tth,
            detector_trigger,
            attenuator,
            collection_spec,
            exposure_time_per_frame,
            [blower.temperature],
        )


def blower_collection(
    time_per_collection: float,
    exposure_time_per_frame: float,
    temperatures_celsius: list[float],
    ramp_rate_c_per_min: float,
    settle_time: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    blower: Blower = blower,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:

    async def calc_timeout(*_, **__):
        return 60

    # tth is currently very slow, speed will be improved for run
    generic_collection_devices.tth.movable_logic.calculate_timeout = calc_timeout

    yield from setup_zebra_for_software_triggering(generic_collection_devices.zebra)

    yield from bps.abs_set(blower.settle_time_s, settle_time)
    yield from bps.abs_set(blower.ramp_rate_c_per_sec, ramp_rate_c_per_min / 60)

    frames_per_angle, total_frames = get_collection_specification(
        time_per_collection, exposure_time_per_frame
    )

    total_frames *= len(temperatures_celsius)

    detector_trigger = generic_collection_devices.zebra.inputs.soft_in_1
    tth = generic_collection_devices.tth

    collection = partial(
        _collection,
        blower,
        tth,
        detector_trigger,
        generic_collection_devices.attenuator,
        temperatures_celsius,
        frames_per_angle,
        exposure_time_per_frame,
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(generic_collection_devices.tth)

    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        all_baseline_devices,
        metadata=metadata,
    )
