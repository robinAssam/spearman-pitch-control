"""Match analysis for Game 2: final-third control over time, and pass destinations.

Usage:
    python scripts/analyse_match.py [--recompute]
Results are cached in outputs/analysis/*.csv (about 90 s to compute);
--recompute ignores the cache.
Writes outputs/figures/final_third_control.png and outputs/figures/pass_control.png
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from pitch_control.analysis import final_third_control, pass_control
from pitch_control.loaders import load_match
from pitch_control.model import make_grid
from pitch_control.plotting import AWAY_COLOR, HOME_COLOR, INK, MUTED
from pitch_control.velocities import add_velocities

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "outputs" / "analysis"
FIGURES = ROOT / "outputs" / "figures"
GAME = 2
GRID_COLOR, AXIS_COLOR, BAR_COLOR = "#e4e3df", "#c3c2b7", "#6b6a65"


def style(ax):
    ax.grid(axis="y", color=GRID_COLOR, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS_COLOR)
    ax.tick_params(colors=MUTED)


def goals_table(events):
    goals = events[(events.type == "SHOT") & events.subtype.str.contains("-GOAL", na=False)]
    home = (goals.team == "Home").cumsum()
    away = (goals.team == "Away").cumsum()
    return goals.assign(score=[f"{h}–{a}" for h, a in zip(home, away)])[["team", "start_time", "score"]]


def score_state(time, goals):
    """Home lead (+), level (0) or Home behind (-) at each time."""
    diff = np.zeros(len(time))
    for g in goals.itertuples():
        diff += np.where(time >= g.start_time, 1 if g.team == "Home" else -1, 0)
    return diff


def plot_final_third(ft, goals):
    fig, (ax, bar_ax) = plt.subplots(1, 2, figsize=(13, 4.8), layout="constrained",
                                     gridspec_kw={"width_ratios": [4.2, 1]})
    # Shade the periods when Home was ahead.
    lead_starts = [g.start_time for g in goals.itertuples()]
    lead_ends = lead_starts[1:] + [ft.time.max()]
    for g, start, end in zip(goals.itertuples(), lead_starts, lead_ends):
        home, away = map(int, g.score.split("–"))
        if home > away:
            ax.axvspan(start / 60, end / 60, color="#f0efec", zorder=0)
    for period, half in ft.groupby("period"):
        half = half.set_index(pd.to_timedelta(half.time, unit="s"))
        smooth = half[["home_final_third", "away_final_third"]].rolling("300s", min_periods=60).mean()
        minutes = half.time / 60
        ax.plot(minutes, smooth.home_final_third * 100, color=HOME_COLOR, lw=2,
                label="Home" if period == 1 else None)
        ax.plot(minutes, smooth.away_final_third * 100, color=AWAY_COLOR, lw=2,
                label="Away" if period == 1 else None)
    ymax = 35
    for k, g in enumerate(goals.itertuples()):
        minute = g.start_time / 60
        ax.axvline(minute, color=MUTED, lw=0.8, ls=":")
        # Alternate label heights so goals close together don't overlap.
        ax.text(minute, ymax + (3.5 if k % 2 else 0), f"{g.team} {g.score}", ha="center",
                va="bottom", fontsize=8, color=INK)
    half_time = ft[ft.period == 2].time.min() / 60
    ax.axvline(half_time, color=AXIS_COLOR, lw=1)
    ax.text(half_time + 0.5, 1, "half-time", color=MUTED, fontsize=8)
    ax.text(62, 31.5, "shaded: Home ahead", color=MUTED, fontsize=8, ha="center")
    ax.set_ylim(0, ymax)
    ax.set_xlim(0, ft.time.max() / 60)
    ax.set_xlabel("Match time (minutes)", color=MUTED)
    ax.set_ylabel("Attacking third controlled (%)", color=MUTED)
    ax.legend(frameon=False, loc="upper left", labelcolor=MUTED)
    style(ax)

    # Summary: average by score state.
    state = score_state(ft.time.to_numpy(), goals)
    states = [("Level", state == 0), ("Home\nahead", state > 0)]
    x = np.arange(len(states))
    for offset, column, color in ((-0.18, "home_final_third", HOME_COLOR),
                                  (0.18, "away_final_third", AWAY_COLOR)):
        values = [ft.loc[mask, column].mean() * 100 for _, mask in states]
        ax_bars = bar_ax.bar(x + offset, values, width=0.34, color=color)
        for bar, v in zip(ax_bars, values):
            bar_ax.text(bar.get_x() + bar.get_width() / 2, v + 0.5, f"{v:.0f}%", ha="center",
                        fontsize=9, color=INK)
    bar_ax.set_xticks(x, [label for label, _ in states])
    bar_ax.set_ylim(0, ymax)
    bar_ax.set_title("Average by score", loc="left", fontsize=10, color=INK)
    style(bar_ax)

    fig.suptitle("Game 2: when level, Home controlled twice as much of its attacking third as Away. "
                 "When ahead, the reverse.", x=0.01, ha="left", fontsize=11, color=INK)
    fig.text(0.01, -0.02, "Share of each team's attacking third it would win the ball in, every second "
             "with the ball in play; lines are 5-minute rolling averages.", fontsize=8, color=MUTED)
    fig.savefig(FIGURES / "final_third_control.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_passes(pc):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), layout="constrained",
                             gridspec_kw={"width_ratios": [2, 1.2]})
    bins = [0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0001]
    labels = ["0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–0.95", "0.95–1"]
    panels = [
        (axes[0], pc, bins, labels, "All passes"),
        (axes[1], pc[pc.progression >= 10], [0, 0.5, 0.8, 1.0001], ["< 0.5", "0.5–0.8", "≥ 0.8"],
         "Forward passes (≥ 10 m towards goal)"),
    ]
    for ax, data, b, lab, title in panels:
        grouped = data.groupby(pd.cut(data.target_control, b, labels=lab), observed=False).completed
        rate, n = grouped.mean() * 100, grouped.size()
        x = np.arange(len(lab))
        ax.bar(x, rate, color=BAR_COLOR, width=0.7)
        for xi, r in zip(x, rate):
            ax.text(xi, r + 1.5, f"{r:.0f}%", ha="center", fontsize=9, color=INK)
        ax.set_xticks(x, [f"{label}\nn={k}" for label, k in zip(lab, n)])
        ax.set_ylim(0, 110)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        ax.set_xlabel("Passing team's control at the pass destination", color=MUTED)
        style(ax)
    axes[0].set_ylabel("Passes completed (%)", color=MUTED)
    fig.suptitle("Game 2: passes into space the model says the team controls almost always arrive",
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.savefig(FIGURES / "pass_control.png", dpi=150)
    plt.close(fig)


def summary(ft, pc, goals):
    state = score_state(ft.time.to_numpy(), goals)
    print("Final-third control by score state (mean share of attacking third):")
    for label, mask in (("level", state == 0), ("Home ahead", state > 0), ("Home behind", state < 0)):
        if mask.any():
            part = ft[mask]
            print(f"  {label:12s} n={mask.sum():5d}  Home {part.home_final_third.mean():.3f}  "
                  f"Away {part.away_final_third.mean():.3f}  Home possession {(part.possession == 'Home').mean():.2f}")
    c, f = pc[pc.completed].target_control.to_numpy(), pc[~pc.completed].target_control.to_numpy()
    auc = np.mean(c[:, None] > f[None, :]) + 0.5 * np.mean(c[:, None] == f[None, :])
    print(f"Passes: {len(pc)} ({len(c)} completed, {len(f)} intercepted), "
          f"median control completed {np.median(c):.2f} vs intercepted {np.median(f):.2f}, AUC {auc:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()

    match = load_match(GAME)
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    ft_path = ANALYSIS / f"game{GAME}_final_third_control.csv"
    pc_path = ANALYSIS / f"game{GAME}_pass_control.csv"
    if args.recompute or not (ft_path.exists() and pc_path.exists()):
        tracking = add_velocities(match.tracking, match.fps)
        goalkeepers = {t: match.goalkeeper(t) for t in ("Home", "Away")}
        final_third_control(match, tracking, goalkeepers, make_grid(match.pitch, 50)).to_csv(ft_path, index=False)
        pass_control(match, tracking, goalkeepers).to_csv(pc_path)
    ft = pd.read_csv(ft_path)
    pc = pd.read_csv(pc_path, index_col=0)

    goals = goals_table(match.events)
    plot_final_third(ft, goals)
    plot_passes(pc)
    summary(ft, pc, goals)
    print(f"saved figures to {FIGURES}")


if __name__ == "__main__":
    main()
