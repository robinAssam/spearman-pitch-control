"""Figure: pitch-control surface for one frame (Game 2, the pass before Home's second goal).

Usage:
    python scripts/plot_pitch_control_frame.py [--game 2] [--event 1116]
Writes outputs/figures/pitch_control_frame.png
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from pitch_control.loaders import load_match
from pitch_control.model import make_grid, pitch_control_at_frame
from pitch_control.plotting import (INK, MUTED, add_control_colorbar, legend_handles,
                                    plot_pitch_control)
from pitch_control.velocities import add_velocities

OUT = Path(__file__).resolve().parents[1] / "outputs" / "figures" / "pitch_control_frame.png"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, default=2)
    # Event 1116: Home 8 crosses to Home 9, who heads in Home's second goal one second later.
    parser.add_argument("--event", type=int, default=1116)
    args = parser.parse_args()

    match = load_match(args.game)
    tracking = add_velocities(match.tracking, match.fps)
    goalkeepers = {team: match.goalkeeper(team) for team in ("Home", "Away")}
    event = match.events.loc[args.event]
    frame, team = int(event.start_frame), event.team
    surface = pitch_control_at_frame(tracking, frame, team, goalkeepers,
                                     make_grid(match.pitch, n_x=100))

    fig, ax = plt.subplots(figsize=(10, 7.4), layout="constrained")
    row = tracking.loc[frame]
    minute = int(row["Time [s]"] // 60) + 1
    action = "crosses" if event.subtype == "CROSS" else "passes"
    title = (f"Game {args.game}, {minute}': {team} {event['from']} {action} to "
             f"{team} {event.to}, who heads in a goal one second later")
    fig.suptitle(title, x=0.02, ha="left", fontsize=12, color=INK)
    _, image = plot_pitch_control(surface, row, match.pitch, ax=ax)

    # The pass, from the event data.
    ax.annotate("", xy=(event.end_x, event.end_y), xytext=(event.start_x, event.start_y),
                arrowprops=dict(arrowstyle="-|>", color=INK, lw=1.2, linestyle="--",
                                shrinkA=4, shrinkB=6), zorder=8)
    ax.legend(handles=legend_handles(), loc="upper left", bbox_to_anchor=(0, -0.01), ncol=4,
              frameon=False, fontsize=9, labelcolor=MUTED)
    add_control_colorbar(fig, image, ax)
    ax.text(-match.pitch.length / 2, match.pitch.width / 2 + 0.8,
            f"{team} attacks →" if team == "Home" else f"← {team} attacks",
            color=MUTED, fontsize=9, va="bottom")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
