"""Figure: pitch-control surface for one frame (Game 2, build-up to Home's second goal).

Usage:
    python scripts/plot_pitch_control_frame.py [--game 2] [--frame 73955] [--attacking Home]
Writes outputs/figures/pitch_control_frame.png
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt

from pitch_control.loaders import load_match
from pitch_control.model import make_grid, pitch_control_at_frame
from pitch_control.plotting import MUTED, plot_pitch_control
from pitch_control.velocities import add_velocities

OUT = Path(__file__).resolve().parents[1] / "outputs" / "figures" / "pitch_control_frame.png"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, default=2)
    # Frame 73955: Home 8 passes to Home 9, who heads in Home's second goal 1 s later.
    parser.add_argument("--frame", type=int, default=73955)
    parser.add_argument("--attacking", default="Home")
    args = parser.parse_args()

    match = load_match(args.game)
    tracking = add_velocities(match.tracking, match.fps)
    goalkeepers = {team: match.goalkeeper(team) for team in ("Home", "Away")}
    surface = pitch_control_at_frame(tracking, args.frame, args.attacking, goalkeepers,
                                     make_grid(match.pitch, n_x=100))

    fig, ax = plt.subplots(figsize=(10, 7))
    row = tracking.loc[args.frame]
    title = (f"Game {args.game}, frame {args.frame} ({row['Time [s]'] / 60:.0f}'), "
             f"{args.attacking} in possession, attacking {'right' if args.attacking == 'Home' else 'left'}")
    _, image = plot_pitch_control(surface, row, match.pitch, ax=ax, title=title)
    cbar = fig.colorbar(image, ax=ax, orientation="horizontal", fraction=0.04, pad=0.02,
                        ticks=[0, 0.5, 1])
    cbar.ax.set_xticklabels(["Away controls", "contested", "Home controls"], color=MUTED)
    cbar.outline.set_visible(False)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
