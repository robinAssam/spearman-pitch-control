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

    max_speed: steps faster than this are tracking errors, not running. The
        fastest footballers peak around 10-11 m/s, so 12 m/s leaves a margin.
    window: Savitzky-Golay window in frames (7 frames = 0.28 s at 25 Hz). Must
        be odd. Longer windows are smoother but lag behind sharp turns.
    polyorder: degree of the local polynomial. 1 fits a straight line in each
        window, which is enough over 0.28 s and smooths the most.
    max_acceleration: largest change in velocity per second (m/s^2) after
        smoothing. Elite sprinters reach roughly 10 m/s^2; in the Metrica data
        99% of smoothed accelerations are below 5 m/s^2, while tracking
        artefacts reach 40+ m/s^2. None disables the limit (the standard
        method, as in the Friends of Tracking reference code).
    """

    max_speed: float = 12.0
    window: int = 7
    polyorder: int = 1
    max_acceleration: float | None = 10.0
