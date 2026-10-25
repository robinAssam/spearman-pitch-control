import numpy as np
import pandas as pd
import pytest

from pitch_control.analysis import final_third_control, pass_control, possession_at_frames
from pitch_control.config import PitchDimensions
from pitch_control.loaders import EVENT_COLUMNS, Match
from pitch_control.model import make_grid

PITCH = PitchDimensions(105, 68)


def _events(rows):
    base = {c: np.nan for c in EVENT_COLUMNS}
    return pd.DataFrame([{**base, **r} for r in rows])[EVENT_COLUMNS]


def test_possession_follows_events_and_ball_lost_switches_team():
    events = _events([
        {"team": "Home", "type": "PASS", "start_frame": 10},
        {"team": "Home", "type": "BALL LOST", "start_frame": 20},
        {"team": "Away", "type": "CHALLENGE", "start_frame": 25},   # not a possession event
        {"team": "Away", "type": "PASS", "start_frame": 30},
    ])
    poss = possession_at_frames(events, [5, 10, 15, 20, 27, 40])
    assert poss.isna().iloc[0]                    # before the first event
    assert poss.iloc[1:].tolist() == ["Home", "Home", "Away", "Away", "Away"]


def _match():
    # One frame: Home players deep in Away's half, Away players in their own goal area.
    row = {"Period": 1, "Time [s]": 0.04, "ball_x": 20.0, "ball_y": 0.0}
    players = {"Home": [(-45.0, 0.0), (20.0, 0.0), (30.0, 15.0)],
               "Away": [(50.0, 0.0), (35.0, -10.0)]}
    for team, xy in players.items():
        for i, (x, y) in enumerate(xy, start=1):
            row.update({f"{team}_{i}_x": x, f"{team}_{i}_y": y,
                        f"{team}_{i}_vx": 0.0, f"{team}_{i}_vy": 0.0})
    tracking = pd.DataFrame([row], index=pd.Index([1], name="Frame"))
    events = _events([
        {"team": "Home", "type": "PASS", "start_frame": 1, "start_x": 20.0, "start_y": 0.0,
         "end_x": 30.0, "end_y": 15.0, "period": 1},     # forward to a free team-mate
        {"team": "Home", "type": "BALL LOST", "subtype": "INTERCEPTION", "start_frame": 1,
         "start_x": 20.0, "start_y": 0.0, "end_x": 35.0, "end_y": -10.0, "period": 1},
    ])
    return Match(game=0, tracking=tracking, events=events, pitch=PITCH), tracking


def test_final_third_control_is_a_probability_and_favours_the_dominant_team():
    match, tracking = _match()
    ft = final_third_control(match, tracking, {"Home": "1", "Away": "1"},
                             make_grid(PITCH, n_x=30), step=1)
    assert len(ft) == 1
    row = ft.iloc[0]
    assert 0 <= row.home_final_third <= 1 and 0 <= row.away_final_third <= 1
    assert row.home_final_third > row.away_final_third


def test_pass_control_progression_and_outcome():
    match, tracking = _match()
    pc = pass_control(match, tracking, {"Home": "1", "Away": "1"})
    completed, failed = pc[pc.completed].iloc[0], pc[~pc.completed].iloc[0]
    assert completed.progression == pytest.approx(10.0)
    assert completed.target_control > 0.9            # free team-mate at the target
    assert failed.target_control < 0.5               # defender at the interception point
