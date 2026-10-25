"""Match analyses built on the pitch-control model.

1. `final_third_control`: how much of its attacking third each team controls,
   sampled through the match.
2. `pass_control`: for every pass, how strongly the passing team controlled
   the spot where the ball ended up, at the moment the pass was played.
"""
import numpy as np
import pandas as pd

from .config import PitchControlConfig
from .model import Grid, pitch_control_at_frame, pitch_control_at_points

# Events that show which team has the ball. A BALL LOST event means the other
# team has it next.
_POSSESSION_EVENTS = {"PASS", "SET PIECE", "RECOVERY", "SHOT", "CARRY"}
# Failed passes: the ball was intercepted. Their end point is where the
# interception happened, not where the passer aimed.
_FAILED_PASS_SUBTYPES = ("INTERCEPTION", "HEAD-INTERCEPTION", "CROSS-INTERCEPTION",
                         "GOAL KICK-INTERCEPTION")


def other(team: str) -> str:
    return "Away" if team == "Home" else "Home"


def possession_at_frames(events: pd.DataFrame, frames) -> pd.Series:
    """Team in possession at each frame: the team of the latest possession event."""
    ev = events[events.type.isin(_POSSESSION_EVENTS | {"BALL LOST"})].copy()
    ev["possession"] = np.where(ev.type == "BALL LOST", ev.team.map(other), ev.team)
    ev = ev.sort_values("start_frame")[["start_frame", "possession"]]
    lookup = pd.DataFrame({"frame": np.asarray(frames)})
    out = pd.merge_asof(lookup, ev, left_on="frame", right_on="start_frame", direction="backward")
    return pd.Series(out["possession"].to_numpy(), index=lookup["frame"])


def final_third_control(match, tracking: pd.DataFrame, goalkeepers: dict, grid: Grid,
                        step: int = 25, config: PitchControlConfig = PitchControlConfig()) -> pd.DataFrame:
    """Share of each team's attacking third that it controls, every `step` frames.

    Only frames with the ball in play are used. Home attacks towards +x, so
    Home's attacking third is x > L/6 and Away's is x < -L/6. The share is the
    average control probability over the cells in that third (1 = the team
    would win the ball anywhere in it).
    """
    frames = tracking.index[::step]
    frames = frames[tracking.loc[frames, "ball_x"].notna().to_numpy()]
    possession = possession_at_frames(match.events, frames)
    home_third = grid.x > match.pitch.length / 6
    away_third = grid.x < -match.pitch.length / 6

    rows = []
    for frame in frames:
        team = possession.loc[frame]
        if not isinstance(team, str):
            continue  # before the first event
        s = pitch_control_at_frame(tracking, frame, team, goalkeepers, grid, config)
        home = s.attack if team == "Home" else s.defence
        away = s.defence if team == "Home" else s.attack
        rows.append({
            "frame": frame,
            "period": tracking.at[frame, "Period"],
            "time": tracking.at[frame, "Time [s]"],
            "possession": team,
            "home_final_third": home[:, home_third].mean(),
            "away_final_third": away[:, away_third].mean(),
        })
    return pd.DataFrame(rows)


def pass_control(match, tracking: pd.DataFrame, goalkeepers: dict,
                 config: PitchControlConfig = PitchControlConfig()) -> pd.DataFrame:
    """Control of the passing team at each pass's end point, at the moment of the pass.

    Includes completed passes and intercepted (failed) passes. Passes played
    while the ball is not tracked (mostly restarts) are skipped, because the
    model then cannot compute the ball's travel time.
    """
    ev = match.events
    completed = ev[(ev.type == "PASS") & ev.end_x.notna()].assign(completed=True)
    failed = ev[(ev.type == "BALL LOST") & ev.subtype.isin(_FAILED_PASS_SUBTYPES)
                & ev.end_x.notna()].assign(completed=False)
    passes = pd.concat([completed, failed]).sort_index()
    passes = passes[tracking.loc[passes.start_frame, "ball_x"].notna().to_numpy()]

    controls = []
    for _, p in passes.iterrows():
        result = pitch_control_at_points(tracking, int(p.start_frame), p.team, goalkeepers,
                                         np.array([[p.end_x, p.end_y]]), config)
        controls.append(result.attack[0])
    direction = np.where(passes.team == "Home", 1.0, -1.0)
    return passes.assign(
        target_control=controls,
        # Metres gained towards the opponent's goal (negative = backwards).
        progression=direction * (passes.end_x - passes.start_x),
        length=np.hypot(passes.end_x - passes.start_x, passes.end_y - passes.start_y),
    )
