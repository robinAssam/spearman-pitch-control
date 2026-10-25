"""Player velocities from tracking positions.

Four steps, done separately for each half (so we never difference across the
half-time break):

1. Raw velocity: the change in position between consecutive frames divided by
   the time between them (0.04 s). Tracking positions jitter by a few
   centimetres, and dividing by 0.04 s turns that jitter into large speed noise.
2. Remove impossible steps: any frame where the raw speed exceeds `max_speed`
   is a tracking glitch. We discard it and fill it in by linear interpolation
   from the frames on either side.
3. Smooth: a Savitzky-Golay filter fits a low-order polynomial to a sliding
   window of frames and keeps the fitted value at the centre. Unlike a simple
   moving average it can be set up to follow genuine accelerations closely
   while averaging out the jitter.
4. Limit acceleration: the speed cap misses artefacts that are too *sudden*
   rather than too fast (e.g. 0 -> 11.9 m/s in one frame, then a perfectly
   straight line, then an instant stop). We cap how much the velocity may
   change per frame at a human maximum. See `limit_acceleration`.

Ball velocity is not computed: the pitch-control model only needs players'
velocities, and the ball's flight is modelled separately.
"""
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter

from .config import VelocityConfig


def raw_velocity(pos: np.ndarray, dt: float) -> np.ndarray:
    """Finite-difference velocity of a (frames, players) position array.

    The first frame has no previous frame, so it copies the second frame's
    velocity. NaN positions give NaN velocities.
    """
    vel = np.empty_like(pos, dtype=float)
    vel[1:] = np.diff(pos, axis=0) / dt
    vel[0] = vel[1] if len(pos) > 1 else np.nan
    return vel


def remove_impossible(vx: np.ndarray, vy: np.ndarray, max_speed: float):
    """Set both velocity components to NaN where speed exceeds `max_speed`."""
    too_fast = np.hypot(vx, vy) > max_speed
    vx, vy = vx.copy(), vy.copy()
    vx[too_fast] = np.nan
    vy[too_fast] = np.nan
    return vx, vy, int(too_fast.sum())


def fill_gaps(vel: np.ndarray, present: np.ndarray) -> np.ndarray:
    """Interpolate NaN velocities, but only while the player is on the pitch."""
    filled = (pd.DataFrame(vel)
              .interpolate(limit_area="inside")
              .ffill().bfill()
              .to_numpy(copy=True))
    filled[~present] = np.nan
    return filled


def smooth(vel: np.ndarray, window: int, polyorder: int) -> np.ndarray:
    """Savitzky-Golay filter over each player's continuous time on the pitch.

    savgol_filter cannot handle NaN, so it is applied to each run of valid
    frames separately. Runs shorter than the window are left unsmoothed.
    """
    out = vel.copy()
    for j in range(vel.shape[1]):
        valid = ~np.isnan(vel[:, j])
        if not valid.any():
            continue
        # Start/end indices of each run of consecutive valid frames.
        edges = np.flatnonzero(np.diff(np.r_[0, valid.astype(int), 0]))
        for start, end in zip(edges[::2], edges[1::2]):
            if end - start >= window:
                out[start:end, j] = savgol_filter(vel[start:end, j], window, polyorder)
    return out


def _limit_pass(vx: np.ndarray, vy: np.ndarray, max_step: float):
    """One pass through time, never letting velocity change by more than max_step."""
    out_x, out_y = vx.copy(), vy.copy()
    for t in range(1, len(vx)):
        dx = vx[t] - out_x[t - 1]
        dy = vy[t] - out_y[t - 1]
        step = np.hypot(dx, dy)
        # Scale the change down where it is too big. Where the previous value
        # is NaN (player just came on), step is NaN and the value is kept.
        scale = np.where(step > max_step, max_step / np.where(step > 0, step, 1), 1.0)
        out_x[t] = np.where(np.isnan(step), vx[t], out_x[t - 1] + dx * scale)
        out_y[t] = np.where(np.isnan(step), vy[t], out_y[t - 1] + dy * scale)
    return out_x, out_y


def limit_acceleration(vx: np.ndarray, vy: np.ndarray, max_acceleration: float, dt: float):
    """Remove velocity changes no human could make.

    Between two frames, a player's velocity may change by at most
    max_acceleration * dt (10 m/s^2 * 0.04 s = 0.4 m/s). Walking through time
    and clipping each change to that size leaves normal play untouched but
    flattens tracking artefacts that jump from 0 to 12 m/s in one frame.

    A single forward pass would lag behind the data (it can only react after
    the fact), so we also run the same pass backwards in time and average the
    two, which keeps the result centred on the original timing.
    """
    max_step = max_acceleration * dt
    fx, fy = _limit_pass(vx, vy, max_step)
    bx, by = _limit_pass(vx[::-1], vy[::-1], max_step)
    return (fx + bx[::-1]) / 2, (fy + by[::-1]) / 2


def add_velocities(tracking: pd.DataFrame, fps: int,
                   config: VelocityConfig = VelocityConfig()) -> pd.DataFrame:
    """Return a copy of `tracking` with `<player>_vx`, `_vy` and `_speed` columns (m/s)."""
    x_cols = [c for c in tracking.columns if c.endswith("_x") and not c.startswith("ball")]
    y_cols = [c[:-2] + "_y" for c in x_cols]
    players = [c[:-2] for c in x_cols]

    vx_all = np.full((len(tracking), len(players)), np.nan)
    vy_all = np.full_like(vx_all, np.nan)
    period = tracking["Period"].to_numpy()
    for p in np.unique(period):
        rows = period == p
        x = tracking.loc[rows, x_cols].to_numpy()
        y = tracking.loc[rows, y_cols].to_numpy()
        present = ~np.isnan(x)

        vx, vy, _ = remove_impossible(raw_velocity(x, 1 / fps), raw_velocity(y, 1 / fps),
                                      config.max_speed)
        vx = smooth(fill_gaps(vx, present), config.window, config.polyorder)
        vy = smooth(fill_gaps(vy, present), config.window, config.polyorder)
        if config.max_acceleration is not None:
            vx, vy = limit_acceleration(vx, vy, config.max_acceleration, 1 / fps)
        vx_all[rows], vy_all[rows] = vx, vy

    speed = np.hypot(vx_all, vy_all)
    new = {}
    for j, player in enumerate(players):
        new[player + "_vx"] = vx_all[:, j]
        new[player + "_vy"] = vy_all[:, j]
        new[player + "_speed"] = speed[:, j]
    return pd.concat([tracking, pd.DataFrame(new, index=tracking.index)], axis=1)
