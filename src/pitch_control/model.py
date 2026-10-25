"""Spearman's (2018) pitch-control model.

Question the model answers: if the ball were played to location r right now,
what is the probability that each team would end up controlling it there?

It is built from four pieces:

1. Ball travel time. The ball needs |r - ball| / ball_speed seconds to reach r.
2. Time to intercept. Each player first keeps moving at their current velocity
   for a reaction time (they cannot turn instantly), then runs straight at r at
   a maximum speed. That gives each player an expected arrival time tau.
3. Arrival uncertainty. Real players are faster or slower than this simple
   model, so the probability that a player has arrived by time T is a smooth
   S-shaped (logistic) curve around tau instead of a hard step.
4. Control. Once the ball is at r, each player who has arrived gains control at
   a rate lambda (per second), but only of the probability that nobody has
   controlled the ball yet:

       d control_j / dT = (1 - total control so far) * P(j has arrived by T) * lambda_j

   This is integrated over time, starting when the ball arrives, until nearly
   all probability is assigned. Summing over each team's players gives the
   team's control at r. Repeating this for every point on a grid gives the
   pitch-control surface.

Everything is vectorised over grid points and players; only the time loop is
explicit.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PitchControlConfig, PitchDimensions


@dataclass(frozen=True)
class Grid:
    """Cell centres of a regular grid over the pitch."""

    x: np.ndarray  # (n_x,)
    y: np.ndarray  # (n_y,)

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.y), len(self.x)

    @property
    def points(self) -> np.ndarray:
        """All cell centres as an (n_y * n_x, 2) array, row by row."""
        xx, yy = np.meshgrid(self.x, self.y)
        return np.c_[xx.ravel(), yy.ravel()]


def make_grid(pitch: PitchDimensions, n_x: int = 50) -> Grid:
    """Grid with n_x cells along the pitch and square-ish cells across it.

    The cost of the model grows with the number of cells (n_x = 50 gives
    50 x 32 = 1,600 cells), so n_x is the main speed/detail trade-off.
    """
    n_y = int(n_x * pitch.width / pitch.length)
    dx, dy = pitch.length / n_x, pitch.width / n_y
    x = np.arange(n_x) * dx - pitch.length / 2 + dx / 2
    y = np.arange(n_y) * dy - pitch.width / 2 + dy / 2
    return Grid(x=x, y=y)


# ---------------------------------------------------------------------------
# The four pieces of the model
# ---------------------------------------------------------------------------

def ball_travel_time(points: np.ndarray, ball: np.ndarray, ball_speed: float) -> np.ndarray:
    """Seconds for the ball to reach each point, shape (n_points,).

    If the ball position is unknown, it is assumed to already be at the point
    (travel time 0), as in the reference implementation.
    """
    if np.isnan(ball).any():
        return np.zeros(len(points))
    return np.linalg.norm(points - ball, axis=1) / ball_speed


def time_to_intercept(points: np.ndarray, positions: np.ndarray, velocities: np.ndarray,
                      reaction_time: float, max_speed: float) -> np.ndarray:
    """Expected arrival time of each player at each point, shape (n_points, n_players).

    The player keeps their current velocity for `reaction_time` seconds, then
    runs in a straight line to the point at `max_speed`.
    """
    after_reaction = positions + velocities * reaction_time               # (n_players, 2)
    distance = np.linalg.norm(points[:, None, :] - after_reaction[None, :, :], axis=2)
    return reaction_time + distance / max_speed


def intercept_probability(T, tau: np.ndarray, sigma: float) -> np.ndarray:
    """Probability that a player expected at time tau has arrived by time T.

    A logistic curve centred on tau. The factor pi / (sqrt(3) * sigma) makes
    sigma the standard deviation of the arrival time.
    """
    return 1.0 / (1.0 + np.exp(-np.pi / (np.sqrt(3.0) * sigma) * (T - tau)))


def integrate_control(tau: np.ndarray, lambdas: np.ndarray, t_ball: np.ndarray,
                      config: PitchControlConfig) -> np.ndarray:
    """Solve the control equation at every point. Returns (n_points, n_players).

    At each time step every player j has a control rate
        rate_j = P(j has arrived by T) * lambda_j
    and the probability still unassigned is shared out between players in
    proportion to their rates.

    'exponential' integration treats the rates as constant within each step
    and solves that step exactly: the unassigned probability decays by
    exp(-sum(rates) * dt). It can never assign more than 100%, however large
    the step. 'euler' takes the first-order step used in the reference code
    (unassigned * rate_j * dt), which can overshoot when many players have
    arrived and dt is large.

    Each point stops once its total control is within `convergence_tol` of 1.
    """
    n_points, n_players = tau.shape
    control = np.zeros((n_points, n_players))
    total = np.zeros(n_points)
    active = np.ones(n_points, dtype=bool)
    dt = config.dt

    for step in range(int(round(config.max_time / dt))):
        T = t_ball[active, None] + step * dt                           # control starts when the ball arrives
        rates = intercept_probability(T, tau[active], config.tti_sigma) * lambdas
        unassigned = (1.0 - total[active])[:, None]
        if config.integration == "euler":
            gain = unassigned * rates * dt
        else:
            total_rate = rates.sum(axis=1, keepdims=True)
            share = np.divide(rates, total_rate, out=np.zeros_like(rates), where=total_rate > 0)
            gain = unassigned * (1.0 - np.exp(-total_rate * dt)) * share
        control[active] += gain
        total[active] += gain.sum(axis=1)
        active = 1.0 - total > config.convergence_tol
        if not active.any():
            break
    return control


def offside_mask(attack_x: np.ndarray, defence_x: np.ndarray, ball_x: float,
                 attack_direction: int, tol: float) -> np.ndarray:
    """True for attackers in an offside position.

    In the standardised frame Home attacks towards +x (direction +1) and Away
    towards -x (direction -1). Multiplying x by the direction lets one rule
    cover both: a player is offside if they are beyond the second-last
    defender, beyond the ball, and in the opponent's half.
    """
    ax = attack_x * attack_direction
    dx = np.sort(defence_x * attack_direction)
    second_last_defender = dx[-2] if len(dx) >= 2 else -np.inf
    line = max(second_last_defender, 0.0)
    if not np.isnan(ball_x):
        line = max(line, ball_x * attack_direction)
    return ax > line + tol


# ---------------------------------------------------------------------------
# Applying the model to a frame of tracking data
# ---------------------------------------------------------------------------

@dataclass
class PitchControlSurface:
    frame: int
    attacking_team: str
    grid: Grid
    attack: np.ndarray           # (n_y, n_x) probability the attacking team controls the ball there
    defence: np.ndarray          # (n_y, n_x)
    player_control: dict = field(default_factory=dict)  # player column prefix -> (n_y, n_x)
    offside_players: list = field(default_factory=list)


def _team_state(row: pd.Series, team: str):
    """Ids, positions and velocities of the players of `team` on the pitch."""
    prefixes = [c[:-2] for c in row.index if c.startswith(team + "_") and c.endswith("_x")]
    prefixes = [p for p in prefixes if not np.isnan(row[p + "_x"])]
    pos = np.array([[row[p + "_x"], row[p + "_y"]] for p in prefixes]).reshape(-1, 2)
    vel = np.array([[row[p + "_vx"], row[p + "_vy"]] for p in prefixes]).reshape(-1, 2)
    return prefixes, pos, np.nan_to_num(vel)


def pitch_control_at_frame(tracking: pd.DataFrame, frame: int, attacking_team: str,
                           goalkeepers: dict[str, str], grid: Grid,
                           config: PitchControlConfig = PitchControlConfig()) -> PitchControlSurface:
    """Pitch-control surface for one frame.

    tracking: output of `add_velocities` (positions in metres, standardised so
        Home attacks towards +x).
    attacking_team: 'Home' or 'Away', the team in possession.
    goalkeepers: {'Home': id, 'Away': id}, e.g. from `Match.goalkeeper`.
    """
    defending_team = "Away" if attacking_team == "Home" else "Home"
    row = tracking.loc[frame]
    ball = np.array([row["ball_x"], row["ball_y"]], dtype=float)

    att_ids, att_pos, att_vel = _team_state(row, attacking_team)
    def_ids, def_pos, def_vel = _team_state(row, defending_team)

    offside = []
    if config.offside:
        direction = 1 if attacking_team == "Home" else -1
        mask = offside_mask(att_pos[:, 0], def_pos[:, 0], ball[0], direction, config.offside_tol)
        offside = [p for p, m in zip(att_ids, mask) if m]
        att_ids = [p for p, m in zip(att_ids, mask) if not m]
        att_pos, att_vel = att_pos[~mask], att_vel[~mask]

    gk = f"{defending_team}_{goalkeepers[defending_team]}"
    lambdas = np.r_[np.full(len(att_ids), config.lambda_att),
                    [config.lambda_def * (config.gk_factor if p == gk else 1.0) for p in def_ids]]

    points = grid.points
    tau = time_to_intercept(points, np.r_[att_pos, def_pos], np.r_[att_vel, def_vel],
                            config.reaction_time, config.max_player_speed)
    t_ball = ball_travel_time(points, ball, config.ball_speed)
    control = integrate_control(tau, lambdas, t_ball, config)

    n_att = len(att_ids)
    shape = grid.shape
    return PitchControlSurface(
        frame=frame,
        attacking_team=attacking_team,
        grid=grid,
        attack=control[:, :n_att].sum(axis=1).reshape(shape),
        defence=control[:, n_att:].sum(axis=1).reshape(shape),
        player_control={p: control[:, j].reshape(shape) for j, p in enumerate(att_ids + def_ids)},
        offside_players=offside,
    )
