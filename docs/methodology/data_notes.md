# Metrica sample data: what is actually in the files

Notes from inspecting the raw files before writing any loaders.
Source: https://github.com/metrica-sports/sample-data

## Common to all three games
- **Frame rate:** 25 Hz (every row is 0.04 s apart, no gaps).
- **Coordinates:** normalised to [0, 1] in both directions, with (0, 0) at the
  top-left corner of the pitch. Values slightly outside [0, 1] occur
  (min -0.05, max 1.06), because players and the ball can be off the pitch.
- **Ball:** missing (NaN) in 32–41% of frames, mostly when the ball is out of play.
- **Pitch size:** only Game 3 states it (105 x 68 m in the metadata). Games 1 and 2
  give no dimensions.
- **Playing direction:** this is different in each game, so it can't be hard-coded.
  - Game 1: the Home goalkeeper's mean x in the 1st half is 0.12, so Home attacks
    left→right in the 1st half.
  - Game 2: the Home goalkeeper's mean x in the 1st half is 0.87, so Home attacks
    right→left in the 1st half.
  - Game 3: the metadata says Team A attacks right→left in the 1st half.

  In every game the direction flips at half-time, as you would expect.

## Games 1 and 2 (CSV)
- Each team has its own tracking file with a 3-line header: team name, shirt
  numbers, then `Period, Frame, Time [s], Player11, (blank), Player1, ...`. Each
  player has an x column followed by an unnamed y column, and the ball's two
  columns come last.
- The Home and Away files have the same frames and can be joined on `Frame`.
- **Substitutions:** a player is NaN before coming on and after going off. The
  player coming on and the player going off overlap at exactly one frame. For
  example, in Game 1 Home `Player1` is present for frames 1–46706 and `Player12`
  for frames 46706–145006, so that substitution happens in the 1st half.
- **A naming quirk:** Game 2 Away has the header `Player 26` (with a space), while
  every other column is written `PlayerNN`. The loader has to normalise this.
- **Events:** a CSV with `Team, Type, Subtype, Period, Start/End Frame, Start/End
  Time, From, To, Start/End X/Y`, in the same normalised coordinates.

| | Frames (P1 / P2) | Events | Goals (Home–Away) |
|---|---|---|---|
| Game 1 | 71,268 / 73,738 | 1,745 | 3–0 |
| Game 2 | 67,941 / 73,215 | 1,935 | 3–2 |

## Game 3 (FIFA EPTS format)
- **Tracking:** a `.txt` file with one line per frame, in the form
  `frame:x1,y1;x2,y2;...;x22,y22:ballx,bally`. The lines don't contain player IDs.
- **Metadata (XML):** the frame rate, the period boundaries (P1 is frames
  1–69661, P2 is 69662–143761), the pitch size, and a list of players.
- **The player order changes during the match.** The metadata has 11
  `DataSpec` segments, each covering a frame range. Each segment says which
  player is in which of the 22 positions in the line, and the order changes
  after substitutions.
- **Watch the channel names:** the channel `player1` is *not* "Player 1". It
  maps to player ID `P3578`, which is the player named "Player 11". So you have
  to look up the player ID from the channel.
- **Events:** JSON with nested team, type, subtype, start and end fields. Unlike
  Games 1 and 2, it also has `CARRY` events (1,395 of them). The final score is
  0–2.
