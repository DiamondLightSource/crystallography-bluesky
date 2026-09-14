from unittest.mock import MagicMock, patch

from bluesky import RunEngine

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    setup_and_teardown_collection,
)


def test_setup_and_tear_down_collection_changes_sample_md_key_and_adds_detectors(
    run_engine: RunEngine,
    common_collection_devices: GenericCollectionDevices,
):
    with patch(
        "crystallography_bluesky.i15_1.plans.generic_collection.bpp.run_decorator"
    ) as mock_run_decorator:
        run_engine(
            setup_and_teardown_collection(
                frames=10,
                exposure_time=0.01,
                devices=common_collection_devices,
                collection=MagicMock(),
                metadata={"experiment_definition": {"a": "b"}, "sample": {"c": "d"}},
            )
        )

    mock_run_decorator.assert_called_once_with(
        md={
            "experiment_definition": {"a": "b"},
            "sample_info": {"c": "d"},
            "detectors": ["fastcs-eiger", "i0"],
        }
    )
