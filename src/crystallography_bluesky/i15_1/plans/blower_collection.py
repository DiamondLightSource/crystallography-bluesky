import json
from functools import partial
from typing import Any, TypeAlias

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable
from pydantic import BaseModel

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


class CollectionSpecPerTemp(BaseModel):
    # The structure of this is put in the nexus file and subsequently
    # used by analysis. If we change it we need to change it there too
    temperature_celsius: float
    collection_specification: CollectionSpecification


TemperatureCollectionSpecification: TypeAlias = list[CollectionSpecPerTemp]


def _collection(
    generic_collection_devices: GenericCollectionDevices,
    blower: Blower,
    collection_spec: TemperatureCollectionSpecification,
    exposure_time_per_frame: float,
):
    detector_trigger = generic_collection_devices.zebra.inputs.soft_in_1

    for collection in collection_spec:
        LOGGER.info(f"Moving to temperature {collection.temperature_celsius}")
        yield from bps.mv(blower.temperature, collection.temperature_celsius)
        yield from inner_collection(
            generic_collection_devices.tth,
            detector_trigger,
            generic_collection_devices.fast_shutter,
            generic_collection_devices.slow_attenuator,
            generic_collection_devices.fast_attenuator,
            collection.collection_specification,
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

    yield from setup_zebra_for_software_triggering(generic_collection_devices.zebra)

    yield from bps.abs_set(blower.settle_time_s, settle_time)
    yield from bps.abs_set(blower.ramp_rate_c_per_sec, ramp_rate_c_per_min / 60)

    single_collection_spec, total_frames = get_collection_specification(
        time_per_collection, exposure_time_per_frame
    )

    temperature_collection_spec = [
        CollectionSpecPerTemp(
            temperature_celsius=temperature,
            collection_specification=single_collection_spec,
        )
        for temperature in temperatures_celsius
    ]

    total_frames *= len(temperatures_celsius)

    collection = partial(
        _collection,
        generic_collection_devices,
        blower,
        temperature_collection_spec,
        exposure_time_per_frame,
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(generic_collection_devices.tth)

    metadata = metadata or {}
    metadata.update(
        {
            "collection_specification": json.dumps(
                [
                    collection_spec_per_temperature.model_dump()
                    for collection_spec_per_temperature in temperature_collection_spec
                ],
            )
        }
    )

    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        all_baseline_devices,
        metadata=metadata,
    )
