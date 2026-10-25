import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image  # noqa: E402

from pitch_control.config import PitchDimensions  # noqa: E402
from pitch_control.model import make_grid, pitch_control_at_frame  # noqa: E402
from pitch_control.plotting import FrameArtists, animate, home_share  # noqa: E402

PITCH = PitchDimensions(105, 68)


def _tracking():
    # Two frames; Away_2 is substituted off in frame 2 and the ball goes out of play.
    rows = []
    for frame, (ball, away2) in enumerate([((0.0, 0.0), (20.0, 5.0)),
                                           ((np.nan, np.nan), (np.nan, np.nan))], start=1):
        row = {"Period": 1, "Time [s]": frame * 0.04, "ball_x": ball[0], "ball_y": ball[1]}
        for team, players in (("Home", [(-40.0, 0.0), (-5.0, 3.0)]),
                              ("Away", [(45.0, 0.0), away2])):
            for i, (x, y) in enumerate(players, start=1):
                row.update({f"{team}_{i}_x": x, f"{team}_{i}_y": y,
                            f"{team}_{i}_vx": 1.0, f"{team}_{i}_vy": 0.0})
        rows.append(row)
    return pd.DataFrame(rows, index=pd.Index([1, 2], name="Frame"))


def _surfaces(tracking, team="Home"):
    grid = make_grid(PITCH, n_x=20)
    return [pitch_control_at_frame(tracking, f, team, {"Home": "1", "Away": "1"}, grid)
            for f in tracking.index]


def test_home_share_is_team_based_not_possession_based():
    tracking = _tracking()
    home_attacking = _surfaces(tracking, "Home")[0]
    away_attacking = _surfaces(tracking, "Away")[0]
    # Blue always means Home: the picture barely depends on who is "attacking"
    # (only offside and the goalkeeper bonus differ).
    assert np.abs(home_share(home_attacking) - home_share(away_attacking)).mean() < 0.1


def test_frame_artists_handle_substitution_and_missing_ball():
    tracking = _tracking()
    surfaces = _surfaces(tracking)
    fig, ax = plt.subplots()
    artists = FrameArtists(ax, tracking.loc[1], surfaces[0], PITCH)
    assert len(artists.teams["Away"][1].get_offsets()) == 2
    artists.update(tracking.loc[2], surfaces[1])
    assert len(artists.teams["Away"][1].get_offsets()) == 1   # substituted player hidden
    assert len(artists.ball.get_offsets()) == 0                # no ball drawn
    plt.close(fig)


def test_animate_writes_gif(tmp_path):
    tracking = _tracking()
    out = tmp_path / "test.gif"
    animate(tracking, [1, 2], _surfaces(tracking), PITCH, out, fps=8.33, title="test",
            captions={1: "kick-off"})
    gif = Image.open(out)
    assert gif.n_frames == 2
    assert gif.info["duration"] == 120
