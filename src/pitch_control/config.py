"""Central configuration. Model parameters will be added here in a later stage."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PitchDimensions:
    """Pitch size in metres.

    105 x 68 is FIFA's recommended size and the only size Metrica states
    (Game 3 metadata). Use 106 x 68 to match the Friends of Tracking code.
    """

    length: float = 105.0
    width: float = 68.0


FPS = 25  # Metrica tracking frame rate (verified: 0.04 s between all frames)


@dataclass(frozen=True)
class VelocityConfig:
    """Settings for estimating player velocities from positions.

    max_speed: steps faster than this are tracking errors, not running. Elite
        athletes' theoretical maximum speed is 7.5-11 m/s (Haugen et al., 2019,
        doi:10.1371/journal.pone.0215551), so 12 m/s leaves a margin.
    window: Savitzky-Golay window in frames (7 frames = 0.28 s at 25 Hz). Must
        be odd. Longer windows are smoother but lag behind sharp turns.
    polyorder: degree of the local polynomial. 1 fits a straight line in each
        window, which is enough over 0.28 s and smooths the most.
    max_acceleration: largest change in velocity per second (m/s^2) after
        smoothing. Elite athletes' maximum horizontal force is 7-10 N/kg, i.e.
        at most about 10 m/s^2 (Haugen et al., 2019); in the Metrica data
        99% of smoothed accelerations are below 5 m/s^2, while tracking
        artefacts reach 40+ m/s^2. None disables the limit (the standard
        method, as in the Friends of Tracking reference code).
    """

    max_speed: float = 12.0
    window: int = 7
    polyorder: int = 1
    max_acceleration: float | None = 10.0


@dataclass(frozen=True)
class PitchControlConfig:
    """Parameters of Spearman's (2018) pitch-control model.

    Values follow the Friends of Tracking reference implementation, which
    takes them from the paper unless noted.

    reaction_time: seconds a player keeps moving at their current velocity
        before they can change direction (s).
    max_player_speed: speed at which a player then runs straight to the
        target (m/s).
    tti_sigma: uncertainty in a player's arrival time (s). The probability of
        having arrived by time T is a logistic curve centred on the expected
        arrival time with this standard deviation.
    lambda_att: control rate (1/s): once a player is at the ball, how quickly
        they bring it under control. 1/4.3 = 0.23 s on average.
    kappa_def: defenders' control rate is lambda_att * kappa_def. The paper
        uses 1.72 (defenders have an advantage); the reference code uses 1.
    gk_factor: the defending goalkeeper's control rate is multiplied by this,
        because they can use their hands. Reference-code choice, not the paper.
    ball_speed: average ball speed used to compute travel time (m/s).
    dt, max_time, convergence_tol: numerical integration settings (s, s, -).
    offside: exclude attackers in an offside position (they cannot legally
        receive a pass). offside_tol is a margin (m) for marginal positions.
    integration: 'exponential' solves each time step exactly; 'euler' is the
        first-order scheme used in the reference code (kept for comparison).
    """

    reaction_time: float = 0.7
    max_player_speed: float = 5.0
    tti_sigma: float = 0.45
    lambda_att: float = 4.3
    kappa_def: float = 1.0
    gk_factor: float = 3.0
    ball_speed: float = 15.0
    dt: float = 0.04
    max_time: float = 10.0
    convergence_tol: float = 0.01
    offside: bool = True
    offside_tol: float = 0.2
    integration: str = "exponential"

    @property
    def lambda_def(self) -> float:
        return self.lambda_att * self.kappa_def
