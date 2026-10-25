"""Integration tests on the real sample games (skipped if data is not downloaded).

Run `python scripts/download_data.py` first.
"""
import numpy as np
import pytest

from pitch_control.loaders import DEFAULT_DATA_DIR, EVENT_COLUMNS, load_match

pytestmark = pytest.mark.skipif(
    not (DEFAULT_DATA_DIR / "Sample_Game_3").exists(),
    reason="sample data not downloaded",
)

# Final scores, counted from the goal events and (for Game 3) the metadata.
SCORES = {1: (3, 0), 2: (3, 2), 3: (0, 2)}


@pytest.fixture(scope="module", params=[1, 2, 3])
def match(request):
    return load_match(request.param)


def _goals(events):
    return events[(events.type == "SHOT") & events.subtype.str.contains("-GOAL", na=False)]


def test_columns_are_consistent(match):
    assert list(match.events.columns) == EVENT_COLUMNS
    for team in ("Home", "Away"):
        xs, ys = match.xy_columns(team)
        assert all(c in match.tracking.columns for c in xs + ys)
    assert {"Period", "Time [s]", "ball_x", "ball_y"} <= set(match.tracking.columns)


def test_frames_are_consecutive_at_25hz(match):
    assert np.all(np.diff(match.tracking.index) == 1)
    assert np.allclose(np.diff(match.tracking["Time [s]"]), 1 / match.fps)


def test_eleven_players_per_team_on_pitch(match):
    # 12 is allowed: Metrica shows the outgoing and incoming player together
    # for exactly one frame at each substitution in Games 1 and 2.
    for team in ("Home", "Away"):
        xs, _ = match.xy_columns(team)
        on_pitch = match.tracking[xs].notna().sum(axis=1)
        assert on_pitch.min() == 11
        assert on_pitch.max() <= 12
        assert (on_pitch == 12).sum() < 10


def test_positions_within_pitch_margin(match):
    half_l, half_w = match.pitch.length / 2, match.pitch.width / 2
    x = match.tracking[[c for c in match.tracking.columns if c.endswith("_x")]].to_numpy()
    y = match.tracking[[c for c in match.tracking.columns if c.endswith("_y")]].to_numpy()
    assert np.nanmax(np.abs(x)) < half_l + 8
    assert np.nanmax(np.abs(y)) < half_w + 8


def test_home_attacks_positive_x_in_both_halves(match):
    goals = _goals(match.events)
    home, away = goals[goals.team == "Home"], goals[goals.team == "Away"]
    assert (home.end_x > 40).all()
    assert (away.end_x < -40).all()
    # Home goalkeeper (the deepest Home player on average) is on the left in both halves.
    xs, _ = match.xy_columns("Home")
    for _, half in match.tracking.groupby("Period"):
        assert half[xs].mean().min() < -30


def test_score_matches(match):
    goals = _goals(match.events)
    assert ((goals.team == "Home").sum(), (goals.team == "Away").sum()) == SCORES[match.game]


def test_event_players_exist_in_tracking(match):
    ev = match.events
    for team in ("Home", "Away"):
        named = set(ev.loc[ev.team == team, "from"].dropna())
        assert named <= set(match.players(team))


def test_goalkeepers_detected(match):
    # Metrica lists each team's goalkeeper first: Player11/Player25 in Games
    # 1-2; channel 'player1' (= Player 11) and Player 28 in Game 3.
    expected = {1: ("11", "25"), 2: ("11", "25"), 3: ("11", "28")}[match.game]
    assert (match.goalkeeper("Home"), match.goalkeeper("Away")) == expected


def test_game2_player_with_space_in_name_is_loaded():
    m = load_match(2)
    assert "26" in m.players("Away")
    assert m.tracking["Away_26_x"].notna().any()


def test_game3_direction_agrees_with_metadata():
    # Metadata: Team A (Home) attacks right_to_left in the first half,
    # so standardising must flip period 1 only.
    assert load_match(3).flipped_periods == [1]
