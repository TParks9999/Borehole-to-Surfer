import pandas as pd
import pytest

from borehole_stick_gui.app import validate_run_inputs


def test_validate_run_inputs_rejects_negative_offset():
    collar_df = pd.DataFrame({"hole_id": ["BH1"]})
    lith_df = pd.DataFrame({"lithology": ["SAND"]})
    with pytest.raises(ValueError, match="Max Off-Line Distance"):
        validate_run_inputs(
            collar_df=collar_df,
            lith_df=lith_df,
            collar_hole_col="hole_id",
            classification_col="lithology",
            max_offset_m=-0.1,
        )


def test_validate_run_inputs_rejects_duplicate_collars():
    collar_df = pd.DataFrame({"hole_id": ["BH1", "BH1"]})
    lith_df = pd.DataFrame({"lithology": ["SAND", "CLAY"]})
    with pytest.raises(ValueError, match="Duplicate collar hole IDs"):
        validate_run_inputs(
            collar_df=collar_df,
            lith_df=lith_df,
            collar_hole_col="hole_id",
            classification_col="lithology",
            max_offset_m=25.0,
        )


def test_validate_run_inputs_rejects_missing_classification_values():
    collar_df = pd.DataFrame({"hole_id": ["BH1"]})
    lith_df = pd.DataFrame({"lithology": ["SAND", "", None]})
    with pytest.raises(ValueError, match="Missing values in classification column"):
        validate_run_inputs(
            collar_df=collar_df,
            lith_df=lith_df,
            collar_hole_col="hole_id",
            classification_col="lithology",
            max_offset_m=25.0,
        )

