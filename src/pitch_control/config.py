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
