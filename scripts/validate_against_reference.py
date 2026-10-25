"""Compare this implementation with the Friends of Tracking reference code.

Both implementations get identical inputs (same frames, positions, velocities,
ball position, 106 x 68 m pitch, 50-cell grid), so any difference comes from
the model code alone.

The reference code takes two shortcuts to save time: it skips the integration
where one team arrives far earlier (returning exactly 1 or 0), and it ignores
players who arrive much later than their fastest team-mate. We therefore run
it twice, as published and with the shortcuts switched off, and compare:

  1. this code (euler)       vs reference without shortcuts -> same equations?
  2. this code (exponential) vs reference without shortcuts -> effect of the exact time step
  3. reference as published  vs reference without shortcuts -> effect of the shortcuts
  4. this code (exponential) vs reference as published      -> overall difference

The reference file is downloaded (pinned commit) into data/reference/, which
is git-ignored; it is not part of this repository.

Usage:
    python scripts/validate_against_reference.py [--frames 30]
Writes outputs/validation/reference_comparison.csv and
       outputs/figures/reference_comparison.png
"""
import argparse
import importlib.util
import time
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

from pitch_control.config import PitchControlConfig, PitchDimensions
from pitch_control.loaders import load_match
from pitch_control.model import make_grid, pitch_control_at_frame
from pitch_control.plotting import (AWAY_COLOR, CONTROL_CMAP, HOME_COLOR, INK, MUTED, NEUTRAL,
                                    draw_pitch)
from pitch_control.velocities import add_velocities

ROOT = Path(__file__).resolve().parents[1]
REF_COMMIT = "7ed3ff857940d3f4611be55f3c08c79525c32171"
REF_URL = ("https://raw.githubusercontent.com/Friends-of-Tracking-Data-FoTD/LaurieOnTracking/"
           f"{REF_COMMIT}/Metrica_PitchControl.py")
REF_PATH = ROOT / "data" / "reference" / "Metrica_PitchControl.py"
PITCH = PitchDimensions(106, 68)   # the reference code's pitch size
N_X = 50
DIFF_CMAP = LinearSegmentedColormap.from_list("diff", [AWAY_COLOR, NEUTRAL, HOME_COLOR])


def load_reference():
    if not REF_PATH.exists():
        REF_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading reference code ({REF_COMMIT[:7]})")
        urllib.request.urlretrieve(REF_URL, REF_PATH)
    spec = importlib.util.spec_from_file_location("reference_pitch_control", REF_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_surface(ref, row, attacking, goalkeepers, grid, shortcuts=True):
    """Attacking-team control on `grid`, computed point by point with the reference code.

    Mirrors the reference's generate_pitch_control_for_event, but takes the
    ball position from the tracking frame (as this implementation does) rather
    than from an event, so both get exactly the same inputs. With
    shortcuts=False the 'time_to_control' thresholds are set so high that no
    point is skipped and no player is ignored.
    """
    params = ref.default_model_params()
    if not shortcuts:
        params["time_to_control_att"] = params["time_to_control_def"] = np.inf
    defending = "Away" if attacking == "Home" else "Home"
    att = ref.initialise_players(row, attacking, params, goalkeepers[attacking])
    dfd = ref.initialise_players(row, defending, params, goalkeepers[defending])
    ball = np.array([row["ball_x"], row["ball_y"]])
    gk_tuple = (goalkeepers["Home"], goalkeepers["Away"])
    att = ref.check_offsides(att, dfd, ball, gk_tuple)
    out = np.zeros(grid.shape)
    for i, y in enumerate(grid.y):
        for j, x in enumerate(grid.x):
            out[i, j], _ = ref.calculate_pitch_control_at_target(np.array([x, y]), att, dfd, ball, params)
    return out


def pick_frames(match, tracking, n):
    """Start frames of `n` passes spread evenly over the match, ball in play."""
    passes = match.events[match.events.type == "PASS"]
    passes = passes[tracking.loc[passes.start_frame, "ball_x"].notna().to_numpy()]
    idx = np.linspace(0, len(passes) - 1, n).astype(int)
    return passes.iloc[idx][["start_frame", "team"]].itertuples(index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", type=int, default=2)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args()

    ref = load_reference()
    match = load_match(args.game, pitch=PITCH)
    tracking = add_velocities(match.tracking, match.fps)
    goalkeepers = {t: match.goalkeeper(t) for t in ("Home", "Away")}
    grid = make_grid(PITCH, N_X)
    configs = {"euler": PitchControlConfig(integration="euler"),
               "exponential": PitchControlConfig(integration="exponential")}

    comparisons = {
        "1_euler_vs_exact_ref": ("euler", "ref_exact"),
        "2_exponential_vs_exact_ref": ("exponential", "ref_exact"),
        "3_published_ref_vs_exact_ref": ("ref_published", "ref_exact"),
        "4_exponential_vs_published_ref": ("exponential", "ref_published"),
    }
    rows, example = [], None
    for frame, team in pick_frames(match, tracking, args.frames):
        row = tracking.loc[frame]
        surfaces, result = {}, {"frame": frame, "attacking": team}
        t0 = time.perf_counter()
        surfaces["ref_published"] = reference_surface(ref, row, team, goalkeepers, grid)
        result["ref_published_seconds"] = time.perf_counter() - t0
        surfaces["ref_exact"] = reference_surface(ref, row, team, goalkeepers, grid, shortcuts=False)
        for name, cfg in configs.items():
            t0 = time.perf_counter()
            s = pitch_control_at_frame(tracking, frame, team, goalkeepers, grid, cfg)
            result[f"{name}_seconds"] = time.perf_counter() - t0
            result[f"{name}_min_sum"] = (s.attack + s.defence).min()
            surfaces[name] = s.attack
        for label, (a, b) in comparisons.items():
            diff = np.abs(surfaces[a] - surfaces[b])
            result[f"{label}_max"] = diff.max()
            result[f"{label}_mean"] = diff.mean()
        worst = result["4_exponential_vs_published_ref_max"]
        if example is None or worst > example[3]:
            example = (frame, team, surfaces["ref_published"], worst, surfaces["exponential"])
        rows.append(result)
        print(f"frame {frame:6d} {team:4s}  " + "  ".join(
            f"{label[0]}: {result[label + '_max']:.4f}" for label in comparisons))

    results = pd.DataFrame(rows)
    out_csv = ROOT / "outputs" / "validation" / "reference_comparison.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_csv, index=False, float_format="%.8f")

    print(f"\nSummary over {len(results)} frames (max and mean absolute difference in attacking control)")
    for label in comparisons:
        print(f"  {label:32s} max {results[label + '_max'].max():.6f}   "
              f"mean {results[label + '_mean'].mean():.6f}")
    for name in configs:
        print(f"  {name:12s} min(attack+defence) {results[name + '_min_sum'].min():.4f}   "
              f"time/frame {results[name + '_seconds'].mean() * 1000:.0f} ms")
    print(f"  reference (published) time/frame {results['ref_published_seconds'].mean() * 1000:.0f} ms")

    plot_example(example, tracking, grid)


def plot_example(example, tracking, grid):
    """Reference vs this implementation vs difference, for the frame with the largest difference."""
    frame, team, reference, _, mine = example
    L, W = PITCH.length / 2, PITCH.width / 2
    extent = (-L, L, -W, W)

    def home_view(surface):  # colour by Home control so blue = Home everywhere
        return surface if team == "Home" else 1 - surface

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), layout="constrained")
    panels = [(home_view(reference), "Reference code (Shaw), Home control", CONTROL_CMAP, (0, 1)),
              (home_view(mine), "This implementation, Home control", CONTROL_CMAP, (0, 1)),
              (mine - reference, "Difference (this − reference)", DIFF_CMAP, (-0.1, 0.1))]
    row = tracking.loc[frame]
    for ax, (data, title, cmap, (vmin, vmax)) in zip(axes, panels):
        image = ax.imshow(data, extent=extent, origin="lower", cmap=cmap, vmin=vmin, vmax=vmax,
                          interpolation="nearest", alpha=0.85)
        draw_pitch(ax, PITCH)
        for t, color in (("Home", HOME_COLOR), ("Away", AWAY_COLOR)):
            xs = [c for c in row.index if c.startswith(t + "_") and c.endswith("_x")]
            ax.scatter(row[xs], row[[c[:-2] + "_y" for c in xs]], s=18, color=color,
                       edgecolor="white", linewidth=0.8, zorder=5)
        ax.scatter(row["ball_x"], row["ball_y"], s=14, color=INK, zorder=6)
        ax.set_title(title, loc="left", fontsize=10, color=INK)
        cbar = fig.colorbar(image, ax=ax, orientation="horizontal", fraction=0.05, pad=0.03,
                            ticks=[vmin, (vmin + vmax) / 2, vmax])
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(colors=MUTED, labelsize=8)
    i, j = np.unravel_index(np.abs(mine - reference).argmax(), reference.shape)
    axes[2].annotate("largest difference", xy=(grid.x[j], grid.y[i]),
                     xytext=(-48, 24), fontsize=8, color=MUTED,
                     arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8))
    fig.suptitle(f"Largest difference among 30 sampled frames: Game 2, frame {frame}, {team} in possession",
                 x=0.01, ha="left", fontsize=11, color=INK)
    out = ROOT / "outputs" / "figures" / "reference_comparison.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
