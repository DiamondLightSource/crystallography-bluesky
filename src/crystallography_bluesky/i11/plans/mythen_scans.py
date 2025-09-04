import os

import bluesky.plan_stubs as bps
import bluesky.plans as bsp
import bluesky.preprocessors as bpp
import numpy as np
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.i11.mythen import Mythen3
from dodal.devices.motors import Motor
from dodal.log import LOGGER
from dodal.plan_stubs.data_session import attach_data_session_metadata_decorator
from dodal.utils import get_beamline_name
from ophyd_async.core import DEFAULT_TIMEOUT, TriggerInfo
from pydantic import NonNegativeFloat, NonNegativeInt, validate_call

BL = get_beamline_name(os.environ("BEAMLINE"))  # type: ignore

DEFAULT_MYTHEN: Mythen3 = inject("mythen3")
DEFAULT_AXIS: Motor = inject("diff_stage.delta")


def create_steps(
    start: float | int, stop: float | int | None = None, step: float | int | None = None
) -> list[float]:
    if (stop is not None) and (step is not None):
        step_points = np.arange(start, stop + step, step, dtype=float)
    elif (stop is not None) and (step is None):
        step_points = [float(start), float(stop)]
    else:
        step_points = [float(start)]

    step_points = list(step_points)

    return step_points


@attach_data_session_metadata_decorator
@bpp.run_decorator()  #    # open/close run
@validate_call(config={"arbitrary_types_allowed": True})
def mythen_scan(
    start: float | int,
    stop: float | int | None = None,
    step: float | int | None = None,
    duration: NonNegativeFloat | NonNegativeInt = 1.0,
    mythen: Mythen3 = DEFAULT_MYTHEN,
    axis: Motor = DEFAULT_AXIS,
) -> MsgGenerator:
    """
    Simple software triggered count plan for the mythen3 on i11
    This will go to the start angle,
    take a count with a duration of duration (in Seconds)
    if there is an end angle, there must be a step.
    If end/step are present it will move through the positions taking a count at each

    This is equivalent to the gda commands 'scan 1 3 0.5 mythen_nx 1'
    """

    step_points = create_steps(start, stop, step)
    number_of_images = len(step_points)

    LOGGER.info(f"{axis} steps used {step_points}")

    # Move delta to initial position
    yield from bps.mv(axis, start, group="setup")

    trigger_info = TriggerInfo(number_of_events=number_of_images, livetime=duration)
    yield from bps.prepare(mythen, trigger_info, group="setup")
    yield from bps.wait(group="setup", timeout=DEFAULT_TIMEOUT)

    yield from bsp.list_scan(
        [mythen], (axis, step_points)
    )  # contains the stage and unstage
