"""Load Metrica sample games into one common structure.

Every game, whatever its source format, becomes a `Match` with:

* `tracking`: one row per frame (index = frame number), columns
  `Period`, `Time [s]`, `Home_<n>_x`, `Home_<n>_y`, ..., `Away_<n>_x`, ...,
  `ball_x`, `ball_y`. Positions are in metres, origin on the centre spot,
  +y upwards. A player's columns are NaN while they are not on the pitch.
* `events`: one row per event with the same columns for every game.

Both are standardised so that Home attacks towards +x in both halves.
"""
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

from .config import FPS, PitchDimensions
from .coordinates import flip_periods, periods_to_flip, to_metres

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

EVENT_COLUMNS = [
    "team", "type", "subtype", "period",
    "start_frame", "start_time", "end_frame", "end_time",
    "from", "to", "start_x", "start_y", "end_x", "end_y",
]


@dataclass
class Match:
    game: int
    tracking: pd.DataFrame
    events: pd.DataFrame
    pitch: PitchDimensions
    fps: int = FPS
    flipped_periods: list[int] = field(default_factory=list)

    def players(self, team: str) -> list[str]:
        """Player ids (shirt numbers as strings) of `team` ('Home' or 'Away')."""
        return [c.split("_")[1] for c in self.tracking.columns
                if c.startswith(team + "_") and c.endswith("_x")]

    def xy_columns(self, team: str) -> tuple[list[str], list[str]]:
        ids = self.players(team)
        return [f"{team}_{p}_x" for p in ids], [f"{team}_{p}_y" for p in ids]

    def goalkeeper(self, team: str) -> str:
        """Id of `team`'s goalkeeper: the player who is, on average, closest to
        their own goal (Home defends -x, Away defends +x after standardising)."""
        xs, _ = self.xy_columns(team)
        mean_x = self.tracking[xs].mean()
        column = mean_x.idxmin() if team == "Home" else mean_x.idxmax()
        return column.split("_")[1]


def load_match(game: int, data_dir: Path = DEFAULT_DATA_DIR,
               pitch: PitchDimensions = PitchDimensions()) -> Match:
    """Load sample game 1, 2 or 3 in metres, with Home attacking towards +x."""
    game_dir = Path(data_dir) / f"Sample_Game_{game}"
    if game in (1, 2):
        tracking, events = _load_csv_game(game_dir, game)
        fps = FPS
    elif game == 3:
        tracking, events, fps = _load_epts_game(game_dir)
    else:
        raise ValueError(f"Unknown sample game: {game}")
    return _standardise(game, tracking, events, pitch, fps)


# ---------------------------------------------------------------------------
# Games 1 and 2: CSV, one tracking file per team
# ---------------------------------------------------------------------------

def _shirt_number(name) -> str | float:
    """'Player11', 'Player 26' -> '11', '26'. Leaves NaN untouched."""
    if pd.isna(name):
        return np.nan
    match = re.search(r"\d+", str(name))
    return match.group() if match else np.nan


def _read_csv_tracking(path: Path, team: str) -> pd.DataFrame:
    # Row 3 of the file holds the column names; each player name is followed
    # by an unnamed column that holds the player's y coordinate.
    header = pd.read_csv(path, skiprows=2, nrows=0).columns
    names = []
    for col in header:
        if col in ("Period", "Frame", "Time [s]"):
            names.append(col)
        elif col.startswith("Unnamed"):
            names.append(names[-1][:-2] + "_y")
        elif col == "Ball":
            names.append("ball_x")
        else:
            names.append(f"{team}_{_shirt_number(col)}_x")
    return pd.read_csv(path, skiprows=3, names=names).set_index("Frame")


def _load_csv_game(game_dir: Path, game: int):
    home = _read_csv_tracking(game_dir / f"Sample_Game_{game}_RawTrackingData_Home_Team.csv", "Home")
    away = _read_csv_tracking(game_dir / f"Sample_Game_{game}_RawTrackingData_Away_Team.csv", "Away")
    # Both files contain the ball and the period/time; keep one copy.
    away = away.drop(columns=["Period", "Time [s]", "ball_x", "ball_y"])
    tracking = home.join(away)
    tracking = tracking[[c for c in tracking.columns if not c.startswith("ball")]
                        + ["ball_x", "ball_y"]]

    raw = pd.read_csv(game_dir / f"Sample_Game_{game}_RawEventsData.csv")
    events = pd.DataFrame({
        "team": raw["Team"],
        "type": raw["Type"],
        "subtype": raw["Subtype"],
        "period": raw["Period"],
        "start_frame": raw["Start Frame"],
        "start_time": raw["Start Time [s]"],
        "end_frame": raw["End Frame"],
        "end_time": raw["End Time [s]"],
        "from": raw["From"].map(_shirt_number),
        "to": raw["To"].map(_shirt_number),
        "start_x": raw["Start X"], "start_y": raw["Start Y"],
        "end_x": raw["End X"], "end_y": raw["End Y"],
    })
    return tracking, events


# ---------------------------------------------------------------------------
# Game 3: FIFA EPTS (tracking .txt + metadata .xml) and JSON events
# ---------------------------------------------------------------------------

def _parse_epts_metadata(path: Path) -> dict:
    root = ET.parse(path).getroot()
    params = {p.findtext("Name"): p.findtext("Value") for p in root.iter("ProviderParameter")}

    score = root.find(".//Score")
    team_label = {score.get("idLocalTeam"): "Home", score.get("idVisitingTeam"): "Away"}

    players = {}  # player id -> column prefix, e.g. 'P3578' -> 'Home_11'
    for p in root.iter("Player"):
        players[p.get("id")] = f"{team_label[p.get('teamId')]}_{p.findtext('ShirtNumber')}"

    # Channel ids ('player1_x') are not player names: look up the player id.
    channel_to_player = {c.get("id"): c.get("playerId") for c in root.iter("PlayerChannel")}

    # Each segment lists, in order, which player occupies each slot in a line.
    segments = []
    for spec in root.find(".//DataFormatSpecifications"):
        refs = [r.get("playerChannelId") for r in spec.iter("PlayerChannelRef")]
        slot_players = [players[channel_to_player[r]] for r in refs if r.endswith("_x")]
        segments.append((int(spec.get("startFrame")), int(spec.get("endFrame")), slot_players))

    periods = [(1, int(params["first_half_start"]), int(params["first_half_end"])),
               (2, int(params["second_half_start"]), int(params["second_half_end"]))]
    return {
        "fps": int(root.findtext(".//FrameRate")),
        "team_label": team_label,
        "players": players,
        "segments": segments,
        "periods": periods,
    }


def _load_epts_game(game_dir: Path):
    meta = _parse_epts_metadata(game_dir / "Sample_Game_3_metadata.xml")

    # Line format: frame:x1,y1;...;x22,y22:ball_x,ball_y -> 1 + 44 + 2 numbers.
    text = (game_dir / "Sample_Game_3_tracking.txt").read_text()
    text = text.replace(":", ",").replace(";", ",")
    raw = pd.read_csv(StringIO(text), header=None).to_numpy()
    frames = raw[:, 0].astype(int)
    slots = raw[:, 1:45].reshape(len(raw), 22, 2)

    prefixes = list(dict.fromkeys(meta["players"].values()))
    column_of = {p: i for i, p in enumerate(prefixes)}
    xy = np.full((len(raw), len(prefixes), 2), np.nan)
    for start, end, slot_players in meta["segments"]:
        rows = (frames >= start) & (frames <= end)
        cols = [column_of[p] for p in slot_players]
        xy[np.ix_(rows, cols)] = slots[rows]

    tracking = pd.DataFrame(index=pd.Index(frames, name="Frame"))
    tracking["Period"] = 0
    for period, start, end in meta["periods"]:
        tracking.loc[(frames >= start) & (frames <= end), "Period"] = period
    tracking["Time [s]"] = frames / meta["fps"]
    for team in ("Home", "Away"):
        for prefix in prefixes:
            if not prefix.startswith(team):
                continue
            i = column_of[prefix]
            if np.isnan(xy[:, i, 0]).all():
                continue  # unused substitute
            tracking[prefix + "_x"] = xy[:, i, 0]
            tracking[prefix + "_y"] = xy[:, i, 1]
    tracking["ball_x"] = raw[:, 45]
    tracking["ball_y"] = raw[:, 46]

    with open(game_dir / "Sample_Game_3_events.json") as f:
        raw_events = json.load(f)["data"]

    def player(entry):
        return meta["players"][entry["id"]].split("_")[1] if entry else np.nan

    def subtype(entry):
        # Subtypes are null, a single {name, id} or a list of them; join the
        # names with '-' to match the Game 1/2 format (e.g. 'ON TARGET-GOAL').
        if entry is None:
            return np.nan
        entries = entry if isinstance(entry, list) else [entry]
        return "-".join(e["name"] for e in entries)

    def coord(value):
        return np.nan if value is None else value

    events = pd.DataFrame([{
        "team": meta["team_label"][e["team"]["id"]],
        "type": e["type"]["name"],
        "subtype": subtype(e["subtypes"]),
        "period": e["period"],
        "start_frame": e["start"]["frame"],
        "start_time": e["start"]["time"],
        "end_frame": e["end"]["frame"],
        "end_time": e["end"]["time"],
        "from": player(e["from"]),
        "to": player(e["to"]),
        "start_x": coord(e["start"]["x"]), "start_y": coord(e["start"]["y"]),
        "end_x": coord(e["end"]["x"]), "end_y": coord(e["end"]["y"]),
    } for e in raw_events])
    return tracking, events, meta["fps"]


# ---------------------------------------------------------------------------
# Shared: metres and playing direction
# ---------------------------------------------------------------------------

def _standardise(game, tracking, events, pitch, fps) -> Match:
    tracking = tracking.copy()
    x_cols = [c for c in tracking.columns if c.endswith("_x")]
    y_cols = [c[:-2] + "_y" for c in x_cols]
    for xc, yc in zip(x_cols, y_cols):
        tracking[xc], tracking[yc] = to_metres(tracking[xc], tracking[yc], pitch)

    events = events[EVENT_COLUMNS].copy()
    for pos in ("start", "end"):
        events[f"{pos}_x"], events[f"{pos}_y"] = to_metres(events[f"{pos}_x"], events[f"{pos}_y"], pitch)

    home_x = [c for c in x_cols if c.startswith("Home_")]
    away_x = [c for c in x_cols if c.startswith("Away_")]
    flips = periods_to_flip(tracking, home_x, away_x)
    tracking = flip_periods(tracking, flips, x_cols, y_cols)

    events = events.rename(columns={"period": "Period"})
    events = flip_periods(events, flips, ["start_x", "end_x"], ["start_y", "end_y"])
    events = events.rename(columns={"Period": "period"})

    return Match(game=game, tracking=tracking, events=events, pitch=pitch,
                 fps=fps, flipped_periods=flips)
