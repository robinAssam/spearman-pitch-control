"""Figure: how velocity cleaning treats a real sprint vs a tracking artefact.

Usage:
    python scripts/plot_velocity_cleaning.py
Writes outputs/figures/velocity_cleaning.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from pitch_control.config import VelocityConfig
from pitch_control.loaders import load_match
from pitch_control.velocities import add_velocities

OUT = Path(__file__).resolve().parents[1] / "outputs" / "figures" / "velocity_cleaning.png"

# Both examples are from Game 3, found by inspecting the data:
#   a genuine sprint, where the acceleration limit changes nothing, and
#   a goalkeeper "slide" artefact (0 -> 11.9 m/s in one frame).
EXAMPLES = [
    ("Home_12", 128387, "Genuine sprint (Home 12): kept"),
    ("Home_11", 98373, "Tracking artefact (Home goalkeeper): removed"),
]
HALF_WINDOW = 50  # frames either side = 2 s

RAW, STANDARD, FINAL = "#a3a29c", "#eb6834", "#2a78d6"
INK, MUTED = "#0b0b0b", "#52514e"


def main() -> None:
    match = load_match(3)
    final = add_velocities(match.tracking, match.fps)
    standard = add_velocities(match.tracking, match.fps, VelocityConfig(max_acceleration=None))
    tr = match.tracking

    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, (player, frame, title) in zip(axes, EXAMPLES):
        frames = np.arange(frame - HALF_WINDOW, frame + HALF_WINDOW + 1)
        t = (frames - frame) / match.fps
        x, y = tr.loc[frames, player + "_x"], tr.loc[frames, player + "_y"]
        raw = np.hypot(x.diff(), y.diff()) * match.fps

        ax.plot(t, raw, color=RAW, lw=1, label="Raw (frame-to-frame)")
        ax.plot(t, standard.loc[frames, player + "_speed"], color=STANDARD, lw=2,
                label="Standard: 12 m/s cap + smoothing")
        ax.plot(t, final.loc[frames, player + "_speed"], color=FINAL, lw=2,
                label="Final: + 10 m/s² acceleration limit")
        ax.axhline(12, color=MUTED, lw=1, ls="--")
        ax.text(t[0], 12.2, "12 m/s speed cap", color=MUTED, fontsize=8, va="bottom")

        ax.set_title(title, loc="left", fontsize=11, color=INK)
        ax.set_xlabel("Time relative to peak (s)", color=MUTED)
        ax.set_ylim(0, 14)
        ax.grid(axis="y", color="#e4e3df", lw=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#c3c2b7")
        ax.tick_params(colors=MUTED)

    axes[0].text(0.3, 10, "Standard and final lines overlap:\nthe limit changes nothing here",
                 color=MUTED, fontsize=8)
    axes[0].set_ylabel("Speed (m/s)", color=MUTED)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("Velocity cleaning keeps real sprints and removes physically impossible jumps",
                 x=0.06, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0.08, 1, 0.95))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
