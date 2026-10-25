"""Coordinate transforms: Metrica's normalised units -> metres, and playing direction.

Metrica coordinates are in [0, 1] with (0, 0) at the top-left corner of the
pitch and y increasing downwards. We convert to metres with the origin on the
centre spot and y increasing upwards, which is the usual convention for plots
and makes the pitch symmetric around (0, 0).
"""
import numpy as np
import pandas as pd

from .config import PitchDimensions


def to_metres(x, y, pitch: PitchDimensions):
    """Convert normalised Metrica coordinates to centred metres."""
    x_m = (np.asarray(x, dtype=float) - 0.5) * pitch.length
    y_m = -(np.asarray(y, dtype=float) - 0.5) * pitch.width
    return x_m, y_m


def periods_to_flip(df: pd.DataFrame, home_x_cols, away_x_cols) -> list[int]:
    """Return the periods in which Home attacks towards -x (right to left).

    The team defending the left-hand goal has its players, on average, further
    left. So if Home's mean x over a period is greater than Away's, Home is
    attacking right-to-left in that period and the period must be flipped.
    """
    flips = []
    for period, part in df.groupby("Period"):
        home_mean = np.nanmean(part[home_x_cols].to_numpy())
        away_mean = np.nanmean(part[away_x_cols].to_numpy())
        if home_mean > away_mean:
            flips.append(int(period))
    return flips


def flip_periods(df: pd.DataFrame, periods, x_cols, y_cols) -> pd.DataFrame:
    """Rotate the pitch by 180 degrees (x -> -x, y -> -y) in the given periods.

    A rotation, not a mirror: negating both axes keeps left/right wings on the
    correct side from the attacking team's point of view.
    """
    df = df.copy()
    mask = df["Period"].isin(periods)
    cols = list(x_cols) + list(y_cols)
    df.loc[mask, cols] = -df.loc[mask, cols]
    return df
