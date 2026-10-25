"""Pitch drawing and pitch-control plots (matplotlib)."""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Arc, Circle, Rectangle

from .config import PitchDimensions

HOME_COLOR = "#2a78d6"
AWAY_COLOR = "#eb6834"
NEUTRAL = "#f0efec"
LINE_COLOR = "#8a8984"
INK = "#0b0b0b"
MUTED = "#52514e"

# Diverging: Away colour at 0, neutral at 0.5 (contested), Home colour at 1.
CONTROL_CMAP = LinearSegmentedColormap.from_list("home_control", [AWAY_COLOR, NEUTRAL, HOME_COLOR])


def draw_pitch(ax, pitch: PitchDimensions = PitchDimensions()):
    """Draw pitch markings (in metres, origin at the centre spot)."""
    L, W = pitch.length / 2, pitch.width / 2
    style = dict(color=LINE_COLOR, lw=1, fill=False, zorder=2)
    ax.add_patch(Rectangle((-L, -W), pitch.length, pitch.width, **style))
    ax.plot([0, 0], [-W, W], color=LINE_COLOR, lw=1, zorder=2)
    ax.add_patch(Circle((0, 0), 9.15, **style))
    for side in (-1, 1):
        x_line = side * L
        # Penalty area (16.5 m deep, 40.32 m wide) and goal area (5.5 m, 18.32 m).
        ax.add_patch(Rectangle((x_line - side * 16.5 if side > 0 else x_line, -20.16),
                               16.5, 40.32, **style))
        ax.add_patch(Rectangle((x_line - side * 5.5 if side > 0 else x_line, -9.16),
                               5.5, 18.32, **style))
        ax.add_patch(Arc((side * (L - 11), 0), 18.3, 18.3,
                         theta1=127 if side > 0 else -53, theta2=233 if side > 0 else 53, **style))
        ax.plot([x_line, x_line], [-3.66, 3.66], color=INK, lw=3, zorder=3)  # goal
    ax.set_xlim(-L - 3, L + 3)
    ax.set_ylim(-W - 3, W + 3)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def plot_players(ax, row, team: str, color: str, velocities: bool = True):
    xs = [c for c in row.index if c.startswith(team + "_") and c.endswith("_x")]
    for xc in xs:
        prefix = xc[:-2]
        x, y = row[xc], row[prefix + "_y"]
        if np.isnan(x):
            continue
        ax.scatter(x, y, s=70, color=color, edgecolor="white", linewidth=1.5, zorder=5)
        ax.text(x, y, prefix.split("_")[1], color="white", fontsize=5.5,
                ha="center", va="center", zorder=6, fontweight="bold")
        if velocities and prefix + "_vx" in row.index:
            ax.arrow(x, y, row[prefix + "_vx"], row[prefix + "_vy"], color=color,
                     width=0.15, head_width=0.8, length_includes_head=True, zorder=4)


def plot_pitch_control(surface, row, pitch: PitchDimensions, ax=None, title: str | None = None):
    """Pitch-control surface coloured by Home control (blue) vs Away control (orange)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 6.8))
    home = surface.attack if surface.attacking_team == "Home" else surface.defence
    away = surface.defence if surface.attacking_team == "Home" else surface.attack
    # Show Home's share of the assigned probability (attack + defence is >= 0.99, not exactly 1).
    home_share = home / (home + away)
    L, W = pitch.length / 2, pitch.width / 2
    image = ax.imshow(home_share, extent=(-L, L, -W, W), origin="lower", cmap=CONTROL_CMAP,
                      vmin=0, vmax=1, alpha=0.75, interpolation="bilinear", zorder=1)
    draw_pitch(ax, pitch)
    plot_players(ax, row, "Home", HOME_COLOR)
    plot_players(ax, row, "Away", AWAY_COLOR)
    if not np.isnan(row["ball_x"]):
        ax.scatter(row["ball_x"], row["ball_y"], s=35, color=INK, edgecolor="white", zorder=7)
    if title:
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    return ax, image
