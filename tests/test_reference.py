"""Checks on real frames: probabilities sum to ~1, and equivalence with the reference code.

Skipped if the sample data (scripts/download_data.py) or the reference code
(downloaded by scripts/validate_against_reference.py) is not present.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from pitch_control.config import PitchControlConfig, PitchDimensions
from pitch_control.loaders import DEFAULT_DATA_DIR, load_match
from pitch_control.model import make_grid, pitch_control_at_frame
from pitch_control.velocities import add_velocities

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

needs_data = pytest.mark.skipif(not (DEFAULT_DATA_DIR / "Sample_Game_2").exists(),
                                reason="sample data not downloaded")
needs_reference = pytest.mark.skipif(
    not (ROOT / "data" / "reference" / "Metrica_PitchControl.py").exists(),
    reason="reference code not downloaded (run scripts/validate_against_reference.py)")

PITCH = PitchDimensions(106, 68)


@pytest.fixture(scope="module")
def game2():
    match = load_match(2, pitch=PITCH)
    tracking = add_velocities(match.tracking, match.fps)
    goalkeepers = {t: match.goalkeeper(t) for t in ("Home", "Away")}
    return match, tracking, goalkeepers


@needs_data
def test_control_sums_to_one_on_real_frames(game2):
    match, tracking, goalkeepers = game2
    grid = make_grid(PITCH, n_x=25)
    in_play = tracking.index[tracking.ball_x.notna()]
    frames = np.random.default_rng(0).choice(in_play, size=40, replace=False)
    for frame in frames:
        for team in ("Home", "Away"):
            s = pitch_control_at_frame(tracking, frame, team, goalkeepers, grid)
            total = s.attack + s.defence
            assert total.min() >= 0.99 and total.max() <= 1 + 1e-9


@needs_data
@needs_reference
@pytest.mark.parametrize("frame, team", [(73955, "Home"), (78332, "Home"), (53000, "Away")])
def test_matches_reference_without_shortcuts(game2, frame, team):
    import validate_against_reference as v
    match, tracking, goalkeepers = game2
    grid = make_grid(PITCH, n_x=20)
    ref = v.load_reference()
    expected = v.reference_surface(ref, tracking.loc[frame], team, goalkeepers, grid, shortcuts=False)
    mine = pitch_control_at_frame(tracking, frame, team, goalkeepers, grid,
                                  PitchControlConfig(integration="euler"))
    assert mine.attack == pytest.approx(expected, abs=1e-6)
