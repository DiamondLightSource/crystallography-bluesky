import os

import bluesky.plan_stubs as bps
import bluesky.plans as bsp
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.i11.diff_stages import DiffractometerStage
from dodal.devices.i11.mythen import Mythen3
from dodal.log import LOGGER
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from dodal.utils import get_beamline_name
from ophyd_async.core import TriggerInfo  # ,DEFAULT_TIMEOUT
from ophyd_async.fastcs.panda import HDFPanda
from pydantic import NonNegativeFloat, NonNegativeInt, validate_call

BL = get_beamline_name(os.environ("BEAMLINE"))  # type: ignore

DEFAULT_MYTHEN = inject("mythen3")
DEFAULT_STAGE = inject("diff_stage")


@attach_data_session_metadata_decorator
@bpp.run_decorator()  #    # open/close run
@validate_call(config={"arbitrary_types_allowed": True})
def mythen_delta_scan(
    start_delta: float | int,
    end_delta: float | int | None,
    delta_step: float | int | None,
    duration: NonNegativeFloat | NonNegativeInt = 1,
    extra_dets: tuple = (),
    mythen: Mythen3 = DEFAULT_MYTHEN,
    stage: DiffractometerStage = DEFAULT_STAGE,
) -> MsgGenerator:
    """
    Simple software triggered count plan for the mythen3 on i11
    This will go to the start angle,
    take a count with a duration of duration (in Seconds)
    if there is an end angle, there must be a step.
    If end/step are present it will move through the positions taking a count at each

    This is equivalent to the gda commands 'scan 1 3 0.5 mythen_nx 1'
    """

    if (end_delta is not None) and (delta_step is not None):
        delta_step_points = np.arange(start_delta, end_delta + delta_step, delta_step)
    elif (end_delta is not None) and (delta_step is None):
        delta_step_points = [start_delta, end_delta]
    else:
        delta_step_points = [start_delta]

    number_of_images = len(delta_step_points)

    LOGGER.info(f"delta steps used {delta_step_points}")

    # Move delta to initial position
    yield from bps.mv(stage.delta, start_delta, group="setup")

    trigger_info = TriggerInfo(number_of_events=number_of_images, livetime=duration)
    yield from bps.stage(mythen, group="setup")
    yield from bps.prepare(mythen, trigger_info, group="setup")
    yield from bps.wait(group="setup")

    dets = [mythen, stage.delta].append(list(extra_dets))

    yield from bsp.list_scan(dets, stage.delta, delta_step_points)  # type: ignore

    # for delta_pos in delta_step_points:
    #     yield from bps.trigger(mythen)


def mythen_trigger(mythen: Mythen3, panda: HDFPanda):
    pass
