import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.motors import XYZStage
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable

from crystallography_bluesky.i15_1.callbacks.analysis_callback import (
    I15_1_ANALYSIS_URL,
    TriggerAnalysisCallback,
)
from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    generic_collection,
)

devices = inject("")
hexapod = inject("hexapod")


def centre_sample(
    start_z: float,
    end_z: float,
    steps: int,
    exposure_time: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    hexapod: XYZStage = hexapod,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
    """Run a step scan in hexapod z, trigger analysis to find the centre and
    move to the centre that is returned.

    Args:
        start_z (float): The start of the scan.
        end_z (float): The end of the scan.
        steps (int): The number of steps to scan across.
        exposure_time (float): Exposure time of each frame.
        devices (GenericCollectionDevices, optional): The standard devices needed for the collection.
        hexapod (XYZStage, optional): The hexapod that is used to scan the sample.
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
        record metadata from. Defaults to None.
    """
    eiger = generic_collection_devices.fastcs_eiger

    analysis_callback = TriggerAnalysisCallback(
        I15_1_ANALYSIS_URL,
        "read_number_of_frames_from_nxs",
        datapath=f"/entry/instrument/{eiger.name}/{eiger.name}",
    )

    yield from bps.mv(hexapod.z, start_z)
    step_size = (end_z - start_z) / steps

    def per_step():
        yield from bps.create(name="hexapod")
        yield from bps.read(hexapod)
        yield from bps.save()
        current_z = yield from bps.rd(hexapod.z)
        LOGGER.info(f"Hexapod at {current_z}, moving {step_size}")
        yield from bps.mvr(hexapod.z, step_size)

    yield from bpp.subs_wrapper(
        generic_collection(
            steps, exposure_time, per_step, generic_collection_devices, baseline_devices
        ),
        analysis_callback,
    )

    analysis_result = analysis_callback.wait_on_and_retrieve_result()
    LOGGER.info(f"Got {analysis_result} from analysis but moving to guessed centre")

    yield from bps.mv(hexapod.z, (end_z - start_z) / 2)
