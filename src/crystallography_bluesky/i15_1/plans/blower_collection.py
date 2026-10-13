import json
from functools import partial
from typing import Any

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower, CalibratedBlower
from dodal.log import LOGGER
from ophyd_async.core import SignalR, StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    AuxiliaryScanType,
    DataCollectionScanType,
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_hardware_triggering,
)
from crystallography_bluesky.i15_1.plans.single_temperature_collection import (
    CollectionSpecPerTemp,
    TemperatureCollectionSpecification,
    get_collection_specification,
    inner_collection,
)

devices = inject("")
blower = inject("calibrated_blower")


def _collection(
    generic_collection_devices: GenericCollectionDevices,
    blower: Blower,
    collection_spec: TemperatureCollectionSpecification,
    exposure_time_per_frame: float,
    signals_to_read_per_point: list[StandardReadable | SignalR],
):
    for collection in collection_spec:
        LOGGER.info(f"Moving to temperature {collection.temperature_celsius}")
        yield from bps.mv(blower.temperature, collection.temperature_celsius)
        yield from inner_collection(
            generic_collection_devices.tth,
            generic_collection_devices.zebra,
            generic_collection_devices.fast_shutter,
            generic_collection_devices.slow_attenuator,
            generic_collection_devices.fast_attenuator,
            collection.collection_specification,
            exposure_time_per_frame,
            signals_to_read_per_point,
        )


def blower_collection(
    time_per_collection: float,
    exposure_time_per_frame: float,
    temperatures_celsius: list[float],
    ramp_rate_c_per_min: float,
    settle_time: float,
    scan_type: DataCollectionScanType | AuxiliaryScanType,
    generic_collection_devices: GenericCollectionDevices = devices,
    blower: Blower = blower,
    baseline_devices: list[StandardReadable] | None = None,
    signals_to_read_per_point: list[StandardReadable | SignalR] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:

    yield from bps.abs_set(blower.settle_time_s, settle_time)
    yield from bps.abs_set(blower.ramp_rate_c_per_sec, ramp_rate_c_per_min / 60)

    single_collection_spec, total_frames = get_collection_specification(
        time_per_collection, exposure_time_per_frame
    )
    minimum_dead_time = 0.0001  # Minimum value independent of timebase
    trigger_pulse_width = 0.0001  # Assumes zebra is set to seconds timebase

    temperature_collection_spec = [
        CollectionSpecPerTemp(
            temperature_celsius=temperature,
            collection_specification=single_collection_spec,
            temperature_unit="C",
        )
        for temperature in temperatures_celsius
    ]

    first_frames_value = next(iter(single_collection_spec)).frames
    time_between_frames = exposure_time_per_frame + minimum_dead_time

    yield from setup_zebra_for_hardware_triggering(
        generic_collection_devices.zebra,
        first_frames_value,
        time_between_frames,
        trigger_pulse_width,
    )

    total_frames *= len(temperatures_celsius)

    if signals_to_read_per_point is None:
        signals_to_read_per_point = [blower.temperature, blower.raw_temperature]

    collection = partial(
        _collection,
        generic_collection_devices,
        blower,
        temperature_collection_spec,
        exposure_time_per_frame,
        signals_to_read_per_point,
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(generic_collection_devices.tth)

    metadata = metadata or {}
    metadata.update(
        {  # Need to serialise because nexus writer can't handle lists
            "collection_specification": json.dumps(
                [spec.model_dump() for spec in temperature_collection_spec]
            )
        }
    )
    if isinstance(blower, CalibratedBlower):
        metadata.update(
            {"blower_calibration": blower.temperature_calibration.model_dump()}
        )

    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        scan_type,
        all_baseline_devices,
        metadata=metadata,
    )
