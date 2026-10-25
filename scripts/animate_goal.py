"""Animation: pitch control during an attack that ends in a goal.

The attack starts at the earliest event in the unbroken run of events by the
scoring team before the goal (i.e. just after the opponent last had the ball).

Usage:
    python scripts/animate_goal.py [--game 2] [--goal 2] [--grid 60] [--fps 8]
    --goal is the goal's number in the match (1 = first goal).
Writes outputs/animations/game<g>_goal<n>.gif
"""
import argparse
import time
from pathlib import Path

from pitch_control.loaders import load_match
from pitch_control.model import make_grid, pitch_control_at_frame
from pitch_control.plotting import animate
from pitch_control.velocities import add_velocities

OUT_DIR = Path(__file__).resolve().parents[1] / "outputs" / "animations"
LEAD_IN, LEAD_OUT = 1.0, 1.5   # seconds shown before the attack starts and after the shot


def attack_events(events, goal_index):
    """Events of the scoring team's possession that ends in the goal."""
    team = events.loc[goal_index, "team"]
    start = goal_index
    while start - 1 in events.index and events.loc[start - 1, "team"] == team:
        start -= 1
    return events.loc[start:goal_index]


def caption(event) -> str:
    who = f"{event.team} {event['from']}"
    if event.type == "PASS":
        kind = "cross" if event.subtype == "CROSS" else "pass"
        return f"{who} {kind} → {event.to}"
    if event.type == "SHOT":
        return f"{who} scores!"
    return f"{who}: {event.type.lower()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, default=2)
    # Goal 2 of Game 2: Away intercepts on the halfway line and scores 14 s later.
    parser.add_argument("--goal", type=int, default=2)
    parser.add_argument("--grid", type=int, default=60, help="grid cells along the pitch")
    parser.add_argument("--fps", type=float, default=8, help="target frame rate; rounded so playback is real time (data is 25 Hz)")
    args = parser.parse_args()

    match = load_match(args.game)
    tracking = add_velocities(match.tracking, match.fps)
    goalkeepers = {team: match.goalkeeper(team) for team in ("Home", "Away")}
    events = match.events
    goals = events[(events.type == "SHOT") & events.subtype.str.contains("-GOAL", na=False)]
    goal = goals.iloc[args.goal - 1]
    attack = attack_events(events, goal.name)
    team = goal.team

    # Use every `step`-th tracking frame and play at the matching rate, so the
    # animation runs in real time (25 Hz / 3 = 8.3 frames per second).
    step = max(1, round(match.fps / args.fps))
    playback_fps = match.fps / step
    first = int(attack.start_frame.min() - LEAD_IN * match.fps)
    last = int(goal.start_frame + LEAD_OUT * match.fps)
    frames = list(range(first, last + 1, step))
    grid = make_grid(match.pitch, n_x=args.grid)

    t0 = time.perf_counter()
    surfaces = [pitch_control_at_frame(tracking, f, team, goalkeepers, grid) for f in frames]
    print(f"{len(frames)} frames of pitch control in {time.perf_counter() - t0:.1f} s")

    captions = {int(e.start_frame): caption(e) for _, e in attack.iterrows()
                if e.type in ("PASS", "SHOT", "RECOVERY")}
    minute = int(goal.start_time // 60) + 1
    title = (f"Game {args.game}, {minute}': {team} goal by {team} {goal['from']} "
             f"({len(attack[attack.type == 'PASS'])} passes, "
             f"{goal.start_time - attack.start_time.min():.0f} s), {team} attacking "
             f"{'→' if team == 'Home' else '←'}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"game{args.game}_goal{args.goal}.gif"
    t0 = time.perf_counter()
    animate(tracking, frames, surfaces, match.pitch, out, fps=playback_fps, title=title,
            captions=captions)
    print(f"saved {out} ({out.stat().st_size / 1e6:.1f} MB) in {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
