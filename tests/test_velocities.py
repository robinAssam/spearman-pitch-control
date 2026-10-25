import numpy as np
import pandas as pd
import pytest

from pitch_control.config import VelocityConfig
from pitch_control.velocities import (add_velocities, fill_gaps, limit_acceleration,
                                      raw_velocity, remove_impossible, smooth)

DT = 0.04


def test_raw_velocity_of_constant_motion():
    t = np.arange(10) * DT
    pos = np.c_[3.0 * t, -2.0 * t]  # two players moving at 3 and -2 m/s
    assert raw_velocity(pos, DT) == pytest.approx(np.tile([3.0, -2.0], (10, 1)))


def test_remove_impossible_flags_only_fast_frames():
    vx = np.array([[5.0], [20.0], [5.0]])
    vy = np.zeros_like(vx)
    vx_out, vy_out, n = remove_impossible(vx, vy, max_speed=12)
    assert n == 1
    assert np.isnan(vx_out[1, 0]) and np.isnan(vy_out[1, 0])
    assert vx_out[0, 0] == 5.0


def test_fill_gaps_interpolates_inside_but_not_while_off_pitch():
    vel = np.array([[np.nan], [1.0], [np.nan], [3.0], [np.nan]])
    present = np.array([[False], [True], [True], [True], [False]])
    out = fill_gaps(vel, present)
    assert out[2, 0] == pytest.approx(2.0)
    assert np.isnan(out[0, 0]) and np.isnan(out[4, 0])


def test_smooth_keeps_a_straight_line_and_reduces_noise():
    rng = np.random.default_rng(0)
    line = np.linspace(0, 5, 200)[:, None]
    assert smooth(line, 7, 1) == pytest.approx(line)
    noisy = line + rng.normal(0, 0.5, line.shape)
    assert np.std(smooth(noisy, 7, 1) - line) < 0.5 * np.std(noisy - line)


def test_smooth_skips_nan_runs():
    vel = np.r_[np.full(5, np.nan), np.linspace(0, 1, 20)][:, None]
    out = smooth(vel, 7, 1)
    assert np.isnan(out[:5]).all() and not np.isnan(out[5:]).any()


def test_limit_acceleration_keeps_realistic_sprint():
    # Accelerating at 5 m/s^2 from 0 to 8 m/s, then holding speed.
    v = np.minimum(np.arange(100) * DT * 5, 8.0)[:, None]
    vx, vy = limit_acceleration(v, np.zeros_like(v), 10.0, DT)
    assert vx == pytest.approx(v)


def test_limit_acceleration_flattens_tracking_slide():
    # Artefact seen in the data: 0 -> 11.85 m/s for 7 frames, then 0 again.
    v = np.zeros((40, 1))
    v[15:22] = 11.85
    vx, _ = limit_acceleration(v, np.zeros_like(v), 10.0, DT)
    assert vx.max() < 2.0
    assert np.all(np.abs(np.diff(vx[:, 0])) <= 10.0 * DT + 1e-9)
    # Still centred on the artefact (frames 15-21): forward and backward
    # passes average to a symmetric bump, so its centre of mass is frame 18.
    centre = np.sum(np.arange(40) * vx[:, 0]) / np.sum(vx[:, 0])
    assert centre == pytest.approx(18.0)


def test_limit_acceleration_handles_player_coming_on():
    v = np.r_[np.full(5, np.nan), np.full(10, 4.0)][:, None]
    vx, _ = limit_acceleration(v, np.zeros_like(v), 10.0, DT)
    assert np.isnan(vx[:5]).all()
    assert vx[5:] == pytest.approx(4.0)


def _tracking(n=100):
    t = np.arange(n) * DT
    return pd.DataFrame({
        "Period": [1] * (n // 2) + [2] * (n - n // 2),
        "Home_1_x": 5.0 * t, "Home_1_y": np.zeros(n),              # 5 m/s along x
        "Away_1_x": np.r_[np.full(10, np.nan), np.zeros(n - 10)],  # comes on at frame 10
        "Away_1_y": np.r_[np.full(10, np.nan), np.zeros(n - 10)],
        "ball_x": np.zeros(n), "ball_y": np.zeros(n),
    }, index=pd.RangeIndex(1, n + 1, name="Frame"))


@pytest.mark.parametrize("max_acc", [None, 10.0])
def test_add_velocities_constant_speed_and_substitute(max_acc):
    out = add_velocities(_tracking(), fps=25, config=VelocityConfig(max_acceleration=max_acc))
    assert out["Home_1_speed"].to_numpy() == pytest.approx(5.0)
    assert out["Away_1_speed"].iloc[:10].isna().all()
    assert out["Away_1_speed"].iloc[10:].to_numpy() == pytest.approx(0.0)
    assert "ball_speed" not in out.columns


def test_add_velocities_does_not_difference_across_half_time():
    tr = _tracking()
    # Teams change ends: the player "teleports" between the last frame of
    # period 1 and the first frame of period 2. That must not show up as speed.
    tr.loc[tr.Period == 2, "Home_1_x"] += 50.0
    out = add_velocities(tr, fps=25)
    assert out["Home_1_speed"].to_numpy() == pytest.approx(5.0)
