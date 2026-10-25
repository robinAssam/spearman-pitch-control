"""Pitch drawing, pitch-control frames and animations (matplotlib).

`FrameArtists` draws one moment (control surface, players, velocities, ball)
and can be updated in place, so the same code makes still images and
animations.
"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Arc, Circle, Rectangle
from PIL import Image

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
        goal_line = side * L
        inward = -side  # direction from this goal line into the pitch
        # Penalty area (16.5 m deep, 40.32 m wide) and goal area (5.5 m deep, 18.32 m wide).
        ax.add_patch(Rectangle((min(goal_line, goal_line + inward * 16.5), -20.16), 16.5, 40.32, **style))
        ax.add_patch(Rectangle((min(goal_line, goal_line + inward * 5.5), -9.16), 5.5, 18.32, **style))
        # Penalty arc: the part of the 9.15 m circle around the spot outside the area.
        ax.add_patch(Arc((goal_line + inward * 11, 0), 18.3, 18.3,
                         theta1=127 if side > 0 else -53, theta2=233 if side > 0 else 53, **style))
        ax.plot([goal_line, goal_line], [-3.66, 3.66], color=INK, lw=3, zorder=3)
    ax.set_xlim(-L - 2, L + 2)
    ax.set_ylim(-W - 2, W + 2)
    ax.set_aspect("equal")
    ax.axis("off")
    return ax


def home_share(surface) -> np.ndarray:
    """Home's share of the assigned control (blue = Home, orange = Away) on any surface."""
    home = surface.attack if surface.attacking_team == "Home" else surface.defence
    away = surface.defence if surface.attacking_team == "Home" else surface.attack
    return home / (home + away)


class FrameArtists:
    """Everything drawn for one moment, updatable in place for animation."""

    def __init__(self, ax, row, surface, pitch: PitchDimensions, show_numbers: bool = True):
        L, W = pitch.length / 2, pitch.width / 2
        self.image = ax.imshow(home_share(surface), extent=(-L, L, -W, W), origin="lower",
                               cmap=CONTROL_CMAP, vmin=0, vmax=1, alpha=0.8,
                               interpolation="bilinear", zorder=1)
        draw_pitch(ax, pitch)
        self.teams = {}
        for team, color in (("Home", HOME_COLOR), ("Away", AWAY_COLOR)):
            prefixes = [c[:-2] for c in row.index if c.startswith(team + "_") and c.endswith("_x")]
            scatter = ax.scatter([], [], s=90, color=color, edgecolor="white", linewidth=1.5, zorder=5)
            # One arrow per player (quiver cannot change its number of arrows);
            # players not on the pitch are masked out in update().
            zeros = np.zeros(len(prefixes))
            arrows = ax.quiver(zeros, zeros, zeros, zeros, color=color, angles="xy",
                               scale_units="xy", scale=1, width=0.003, headwidth=4,
                               headlength=4, zorder=4)
            labels = [ax.text(0, 0, p.split("_")[1], color="white", fontsize=6, fontweight="bold",
                              ha="center", va="center", zorder=6, visible=False) if show_numbers else None
                      for p in prefixes]
            self.teams[team] = (prefixes, scatter, arrows, labels)
        # The ball is drawn as a ring so it never hides the number of the player on it.
        self.ball = ax.scatter([], [], s=230, facecolor="none", edgecolor=INK, linewidth=1.6, zorder=7)
        self.update(row, surface)

    def update(self, row, surface):
        self.image.set_data(home_share(surface))
        for prefixes, scatter, arrows, labels in self.teams.values():
            xy = np.array([[row[p + "_x"], row[p + "_y"]] for p in prefixes])
            on = ~np.isnan(xy[:, 0])
            scatter.set_offsets(xy[on])
            arrows.set_offsets(np.nan_to_num(xy))
            if prefixes and prefixes[0] + "_vx" in row.index:
                v = np.array([[row[p + "_vx"], row[p + "_vy"]] for p in prefixes])
                hide = ~on | np.isnan(v[:, 0])
                arrows.set_UVC(np.ma.masked_where(hide, v[:, 0]), np.ma.masked_where(hide, v[:, 1]))
            else:
                arrows.set_visible(False)
            for label, (x, y), visible in zip(labels, xy, on):
                if label is not None:
                    label.set_visible(bool(visible))
                    if visible:
                        label.set_position((x, y))
        ball = np.array([[row["ball_x"], row["ball_y"]]])
        self.ball.set_offsets(ball if not np.isnan(ball).any() else np.empty((0, 2)))


def legend_handles():
    dot = dict(marker="o", linestyle="", markeredgecolor="white", markersize=8)
    return [Line2D([], [], color=HOME_COLOR, label="Home", **dot),
            Line2D([], [], color=AWAY_COLOR, label="Away", **dot),
            Line2D([], [], color=INK, label="Ball", marker="o", linestyle="", markersize=11,
                   markerfacecolor="none", markeredgewidth=1.6),
            Line2D([], [], color=MUTED, label="Velocity (1 s ahead)", lw=1)]


def add_control_colorbar(fig, image, ax):
    cbar = fig.colorbar(image, ax=ax, orientation="horizontal", fraction=0.035, pad=0.02,
                        ticks=[0, 0.5, 1])
    cbar.ax.set_xticklabels(["Away would win the ball", "contested", "Home would win the ball"],
                            color=MUTED, fontsize=9)
    cbar.ax.tick_params(length=0)
    cbar.outline.set_visible(False)
    return cbar


def plot_pitch_control(surface, row, pitch: PitchDimensions, ax=None, title: str | None = None):
    """Single pitch-control frame. Returns (ax, image)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 6.8))
    artists = FrameArtists(ax, row, surface, pitch)
    if title:
        ax.set_title(title, loc="left", fontsize=11, color=INK)
    return ax, artists.image


def _save_small_gif(images, out_path, fps: float, colors: int):
    """Save RGB frames as a GIF with one shared, reduced colour palette.

    The control surface changes a little everywhere in every frame, so GIF's
    usual trick (only storing pixels that change) barely helps. A small shared
    palette without dithering keeps the file a few MB instead of ~20 MB.
    """
    sample = images[:: max(1, len(images) // 6)]
    montage = Image.new("RGB", (images[0].width * len(sample), images[0].height))
    for k, im in enumerate(sample):
        montage.paste(im, (k * im.width, 0))
    palette = montage.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
    frames = [im.quantize(palette=palette, dither=Image.Dither.NONE) for im in images]
    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=round(1000 / fps), loop=0, optimize=True)


def animate(tracking, frames, surfaces, pitch: PitchDimensions, out_path, fps: float,
            title: str, captions: dict | None = None, dpi: int = 72, colors: int = 48):
    """Write a GIF of pitch control over `frames` (one surface per frame).

    captions: optional {frame: text}; each caption stays up until the next.
    """
    fig, ax = plt.subplots(figsize=(9, 6.6), layout="constrained")
    fig.set_dpi(dpi)
    artists = FrameArtists(ax, tracking.loc[frames[0]], surfaces[0], pitch)
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    add_control_colorbar(fig, artists.image, ax)
    clock = ax.text(-pitch.length / 2, pitch.width / 2 + 0.5, "", fontsize=9, color=MUTED,
                    va="bottom")
    caption = ax.text(pitch.length / 2, pitch.width / 2 + 0.5, "", fontsize=9, color=INK,
                      ha="right", va="bottom")
    caption_frames = sorted(captions) if captions else []

    images = []
    for frame, surface in zip(frames, surfaces):
        row = tracking.loc[frame]
        artists.update(row, surface)
        seconds = row["Time [s]"]
        clock.set_text(f"{int(seconds // 60)}:{seconds % 60:04.1f}")
        current = [f for f in caption_frames if f <= frame]
        caption.set_text(captions[current[-1]] if current else "")
        fig.canvas.draw()
        images.append(Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB"))
    plt.close(fig)
    _save_small_gif(images, out_path, fps, colors)
