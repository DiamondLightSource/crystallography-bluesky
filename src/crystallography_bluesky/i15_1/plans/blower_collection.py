from functools import partial
from typing import Any

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.attenuator import Attenuator
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.motors import Motor
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable

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
    setup_zebra_for_hardware_triggering,
)

devices = inject("")
blower = inject("blower")


def _collection(
    blower: Blower,
    tth: Motor,
    attenuator: Attenuator,
    temperatures_celsius: list[float],
    collection_spec: CollectionSpecification,
    time_between_frames: float,
):
    for temperature in temperatures_celsius:
        LOGGER.info(f"Moving to temperature {temperature}")
        yield from bps.mv(blower.temperature, temperature)
        yield from inner_collection(
            tth,
            attenuator,
            collection_spec,
            time_between_frames,
            [blower.temperature],
        )
        # Is room_temperature_collection the correct place to
        # get inner_collection from?
        # Would single_temperature_collection be a better desciption?


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

    yield from bps.abs_set(blower.settle_time_s, settle_time)
    yield from bps.abs_set(blower.ramp_rate_c_per_sec, ramp_rate_c_per_min / 60)

    collection_spec, total_frames = get_collection_specification(
        time_per_collection, exposure_time_per_frame
    )

    pulse_width = 0.0001  # Assumes zebra is set to seconds timebase
    first_frames_value = next(iter(collection_spec.values())).frames
    time_between_frames = exposure_time_per_frame + pulse_width

    yield from setup_zebra_for_hardware_triggering(
        generic_collection_devices.zebra,
        first_frames_value,
        time_between_frames,
    )

    total_frames *= len(temperatures_celsius)

    tth = generic_collection_devices.tth

    collection = partial(
        _collection,
        blower,
        tth,
        generic_collection_devices.attenuator,
        temperatures_celsius,
        collection_spec,
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
