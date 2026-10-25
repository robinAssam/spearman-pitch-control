import numpy as np
import pandas as pd
import pytest

from pitch_control.config import PitchControlConfig, PitchDimensions
from pitch_control.model import (ball_travel_time, integrate_control, intercept_probability,
                                 make_grid, offside_mask, pitch_control_at_frame,
                                 time_to_intercept)

CFG = PitchControlConfig()


def test_grid_cells_cover_pitch():
    grid = make_grid(PitchDimensions(105, 68), n_x=50)
    assert grid.shape == (32, 50)
    assert grid.points.shape == (1600, 2)
    assert grid.x[0] == pytest.approx(-52.5 + 1.05)        # first cell centre
    assert np.allclose(grid.x, -grid.x[::-1])                # symmetric about the centre spot


def test_ball_travel_time():
    points = np.array([[15.0, 0.0], [0.0, 30.0]])
    assert ball_travel_time(points, np.array([0.0, 0.0]), 15.0) == pytest.approx([1.0, 2.0])
    assert ball_travel_time(points, np.array([np.nan, np.nan]), 15.0) == pytest.approx([0.0, 0.0])


def test_time_to_intercept_standing_and_moving_player():
    point = np.array([[10.0, 0.0]])
    pos = np.array([[0.0, 0.0], [0.0, 0.0]])
    vel = np.array([[0.0, 0.0], [5.0, 0.0]])   # second player already running at the point
    tau = time_to_intercept(point, pos, vel, reaction_time=0.7, max_speed=5.0)
    assert tau[0, 0] == pytest.approx(0.7 + 10 / 5)         # standing: react, then run 10 m
    assert tau[0, 1] == pytest.approx(0.7 + (10 - 3.5) / 5)  # moving: already 3.5 m closer


def test_intercept_probability_is_a_centred_sigmoid():
    assert intercept_probability(2.0, np.array(2.0), 0.45) == pytest.approx(0.5)
    T = np.linspace(0, 4, 50)
    p = intercept_probability(T, np.array(2.0), 0.45)
    assert np.all(np.diff(p) > 0)
    assert p[0] < 0.01 and p[-1] > 0.99
    # sigma is the standard deviation of the arrival-time distribution
    density = np.gradient(intercept_probability(np.linspace(-3, 7, 20001), np.array(2.0), 0.45),
                          np.linspace(-3, 7, 20001))
    t = np.linspace(-3, 7, 20001)
    std = np.sqrt(np.trapezoid(density * (t - 2.0) ** 2, t))
    assert std == pytest.approx(0.45, rel=1e-3)


@pytest.mark.parametrize("integration", ["exponential", "euler"])
def test_single_player_gets_all_control(integration):
    cfg = PitchControlConfig(integration=integration)
    tau = np.array([[1.0], [3.0]])
    control = integrate_control(tau, np.array([4.3]), np.zeros(2), cfg)
    assert np.all(control.sum(axis=1) >= 1 - cfg.convergence_tol)


@pytest.mark.parametrize("integration", ["exponential", "euler"])
def test_two_identical_players_share_control(integration):
    cfg = PitchControlConfig(integration=integration)
    tau = np.array([[1.5, 1.5]])
    control = integrate_control(tau, np.array([4.3, 4.3]), np.zeros(1), cfg)
    assert control[0, 0] == pytest.approx(control[0, 1])
    assert control.sum() >= 1 - cfg.convergence_tol


def test_faster_arrival_and_higher_rate_win():
    cfg = PitchControlConfig()
    early_vs_late = integrate_control(np.array([[1.0, 1.5]]), np.array([4.3, 4.3]), np.zeros(1), cfg)
    assert early_vs_late[0, 0] > 0.6
    gk_vs_player = integrate_control(np.array([[1.0, 1.0]]), np.array([4.3, 12.9]), np.zeros(1), cfg)
    assert gk_vs_player[0, 1] == pytest.approx(0.75, abs=0.02)  # 12.9 / (4.3 + 12.9) when both have arrived


def test_exponential_never_overshoots_with_large_steps():
    # Many players already at the ball and a coarse time step: Euler would assign > 100%.
    cfg = PitchControlConfig(dt=0.2)
    tau = np.zeros((1, 8))
    control = integrate_control(tau, np.full(8, 4.3), np.zeros(1), cfg)
    assert control.sum() <= 1.0 + 1e-12
    assert np.all(control >= 0)


def test_control_only_starts_when_ball_arrives():
    # Attacker is there at 1 s, defender at 2 s. If the ball takes 3 s, both are
    # waiting when it arrives, so control is shared equally.
    cfg = PitchControlConfig()
    tau = np.array([[1.0, 2.0]])
    early = integrate_control(tau, np.array([4.3, 4.3]), np.array([0.0]), cfg)
    late = integrate_control(tau, np.array([4.3, 4.3]), np.array([3.0]), cfg)
    assert early[0, 0] > late[0, 0]
    assert late[0, 0] == pytest.approx(late[0, 1], abs=0.02)


@pytest.mark.parametrize("direction", [1, -1])
def test_offside_mask_both_directions(direction):
    s = direction
    attackers = np.array([10.0, 30.0, -20.0]) * s
    defenders = np.array([50.0, 25.0, 20.0]) * s       # GK deepest, second-last at 25
    mask = offside_mask(attackers, defenders, ball_x=0.0 * s, attack_direction=s, tol=0.2)
    assert mask.tolist() == [False, True, False]
    # Level with the ball: not offside even if beyond the second-last defender.
    assert not offside_mask(np.array([30.0 * s]), defenders, ball_x=35.0 * s,
                            attack_direction=s, tol=0.2)[0]
    # Own half: never offside.
    assert not offside_mask(np.array([-1.0 * s]), np.array([50.0, -5.0]) * s, ball_x=-10.0 * s,
                            attack_direction=s, tol=0.2)[0]


def _frame(home_xy, away_xy, ball):
    row = {"Period": 1, "Time [s]": 0.04, "ball_x": ball[0], "ball_y": ball[1]}
    for team, players in (("Home", home_xy), ("Away", away_xy)):
        for i, (x, y) in enumerate(players, start=1):
            row.update({f"{team}_{i}_x": x, f"{team}_{i}_y": y,
                        f"{team}_{i}_vx": 0.0, f"{team}_{i}_vy": 0.0})
    return pd.DataFrame([row], index=pd.Index([1], name="Frame"))


def test_symmetric_frame_gives_symmetric_control():
    # Mirror-image teams, ball on the centre spot, equal control rates, no GK
    # bonus: Home's control at (x, y) must equal Away's control at (-x, -y).
    cfg = PitchControlConfig(gk_factor=1.0, offside=False)
    home = [(-40.0, 0.0), (-10.0, 15.0), (-10.0, -15.0)]
    away = [(-x, -y) for x, y in home]
    tracking = _frame(home, away, (0.0, 0.0))
    grid = make_grid(PitchDimensions(105, 68), n_x=20)
    s = pitch_control_at_frame(tracking, 1, "Home", {"Home": "1", "Away": "1"}, grid, cfg)
    assert s.attack == pytest.approx(s.defence[::-1, ::-1], abs=1e-9)


def test_surface_probabilities_sum_to_one():
    tracking = _frame([(-30.0, 5.0), (0.0, -10.0)], [(20.0, 0.0), (45.0, 0.0)], (0.0, -10.0))
    grid = make_grid(PitchDimensions(105, 68), n_x=30)
    s = pitch_control_at_frame(tracking, 1, "Home", {"Home": "1", "Away": "2"}, grid)
    total = s.attack + s.defence
    assert np.all(total >= 1 - PitchControlConfig().convergence_tol)
    assert np.all(total <= 1 + 1e-9)
    assert sum(s.player_control.values()) == pytest.approx(total)


def test_player_on_the_ball_controls_it():
    tracking = _frame([(0.0, 0.0)], [(15.0, 0.0)], (0.0, 0.0))
    grid = make_grid(PitchDimensions(105, 68), n_x=105)
    s = pitch_control_at_frame(tracking, 1, "Home", {"Home": "1", "Away": "1"}, grid)
    iy, ix = np.argmin(np.abs(grid.y)), np.argmin(np.abs(grid.x))
    assert s.attack[iy, ix] > 0.95


def test_offside_attacker_is_excluded():
    # Home attacker at x=40 beyond the only outfield defender (x=20); GK at 50.
    tracking = _frame([(0.0, 0.0), (40.0, 0.0)], [(50.0, 0.0), (20.0, 0.0)], (0.0, 0.0))
    grid = make_grid(PitchDimensions(105, 68), n_x=20)
    s = pitch_control_at_frame(tracking, 1, "Home", {"Home": "1", "Away": "1"}, grid)
    assert s.offside_players == ["Home_2"]
    assert "Home_2" not in s.player_control
