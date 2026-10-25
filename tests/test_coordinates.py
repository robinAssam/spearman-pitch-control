import numpy as np
import pandas as pd
import pytest

from pitch_control.config import PitchDimensions
from pitch_control.coordinates import flip_periods, periods_to_flip, to_metres

PITCH = PitchDimensions(length=105, width=68)


@pytest.mark.parametrize("x, y, expected", [
    (0.5, 0.5, (0.0, 0.0)),      # centre spot
    (0.0, 0.0, (-52.5, 34.0)),   # top-left corner -> left, up
    (1.0, 1.0, (52.5, -34.0)),   # bottom-right corner -> right, down
])
def test_to_metres_maps_corners_and_centre(x, y, expected):
    assert to_metres(x, y, PITCH) == pytest.approx(expected)


def test_to_metres_keeps_nan():
    x, y = to_metres([np.nan], [np.nan], PITCH)
    assert np.isnan(x[0]) and np.isnan(y[0])


def _two_halves(home_x_p1, away_x_p1):
    # Teams swap ends at half-time.
    return pd.DataFrame({
        "Period": [1, 1, 2, 2],
        "Home_1_x": [home_x_p1] * 2 + [-home_x_p1] * 2,
        "Home_1_y": [5.0] * 4,
        "Away_1_x": [away_x_p1] * 2 + [-away_x_p1] * 2,
        "Away_1_y": [-5.0] * 4,
    })


def test_periods_to_flip_detects_home_attacking_right_to_left():
    df = _two_halves(home_x_p1=30.0, away_x_p1=-30.0)  # Home deep on the right in P1
    assert periods_to_flip(df, ["Home_1_x"], ["Away_1_x"]) == [1]


def test_periods_to_flip_detects_home_attacking_left_to_right():
    df = _two_halves(home_x_p1=-30.0, away_x_p1=30.0)
    assert periods_to_flip(df, ["Home_1_x"], ["Away_1_x"]) == [2]


def test_flip_periods_rotates_only_the_given_period():
    df = _two_halves(home_x_p1=30.0, away_x_p1=-30.0)
    out = flip_periods(df, [1], ["Home_1_x", "Away_1_x"], ["Home_1_y", "Away_1_y"])
    assert (out["Home_1_x"] == -30.0).all()                  # same side in both halves now
    assert out.loc[out.Period == 1, "Home_1_y"].eq(-5.0).all()  # rotated, not mirrored
    assert out.loc[out.Period == 2, "Home_1_y"].eq(5.0).all()   # untouched
    assert df["Home_1_x"].iloc[0] == 30.0                    # input not modified
