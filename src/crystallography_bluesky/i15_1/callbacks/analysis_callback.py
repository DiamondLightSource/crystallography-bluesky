from pathlib import Path

from bluesky.callbacks import CallbackBase
from dodal.log import LOGGER
from event_model.documents import RunStart, RunStop
from heliotrapi.client import AnalysisClient

I15_1_ANALYSIS_URL = "https://i15-1-analysis.diamond.ac.uk"


class TriggerAnalysisCallback(CallbackBase):
    """A callback that will pass the nexus file location to analysis on a plan end."""

    def __init__(self, analysis_url: str, analysis_name: str, **kwargs):
        """Create a callback to trigger analysis on plan end.

        Args:
            analysis_url (str): The url where the analysis listener is running.
            analysis_name (str): The name of the analysis to trigger.
            **kwargs: Additional kwargs passed on to the analysis
        """
        self._client = AnalysisClient(analysis_url)
        self._analysis_name = analysis_name
        self._kwargs = kwargs

    def start(self, doc: RunStart) -> RunStart | None:
        self._directory = doc.get("data_session_directory")
        self._file = doc.get("scan_file")

    def stop(self, doc: RunStop) -> RunStop | None:
        if doc["exit_status"] != "success":
            return doc

        if not self._directory or not self._file:
            LOGGER.warning(
                "Not triggering analysis as nexus information could not be found"
            )
            return doc

        full_nexuspath = Path(self._directory) / Path(f"{self._file}.nxs")

        self._client.submit(
            self._analysis_name,
            nexus_filepath=full_nexuspath,
            **self._kwargs,
        )

    def wait_on_and_retrieve_result(self):
        result = self._client.get_result()
        LOGGER.info(f"Received result from analysis {result}")
        return result.result
