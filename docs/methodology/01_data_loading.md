# 1. Data loading

Code: [`loaders.py`](../../src/pitch_control/loaders.py), [`coordinates.py`](../../src/pitch_control/coordinates.py).
Details of the raw files: [data_notes.md](data_notes.md).

## The data
Metrica Sports published three anonymised full matches: the position of every
player and the ball 25 times per second (tracking), plus a log of on-ball actions
such as passes and shots (events). Games 1 and 2 are in Metrica's CSV format. Game 3
is in FIFA's EPTS format, which is standardised but more awkward to read.

## One structure for every game
`load_match(game)` returns the same `Match` object for all three games:

- **Tracking:** one row per frame, with columns `Home_11_x`, `Home_11_y`, …, `ball_x`, `ball_y`.
- **Events:** one row per event, with the same columns for every game.

All the later code (velocities, the model, plots) only has to handle this one format.

## Design choices
| Choice | Why |
|---|---|
| **Metres, origin on the centre spot, +y up** | The model works with distances and speeds, which only mean something in metres. A centred origin makes the pitch symmetric. |
| **Pitch size 105 × 68 m (configurable)** | This is FIFA's recommended size and the only size Metrica states. It's set to 106 × 68 m when comparing with the reference code. |
| **Home always attacks towards +x** | Teams change ends at half-time. Fixing one direction means the "final third" is the same area all match. |
| **Direction found from player positions** | It differs from game to game, so it can't be hard-coded. The team that is further left on average is defending the left goal. This was checked against Game 3's metadata. |
| **Rotate 180°, don't mirror** | Negating both x and y keeps each team's left wing on its left. |

## Data quirks handled
- **Substitutions:** a player is NaN before coming on and after going off.
- **Game 2 naming:** the away file has the header `Player 26`, with a space.
- **Game 3 channel names:** the tracking file lists players by position in the line, and the order changes in 11 segments. The channel `player1` is actually "Player 11", so each channel has to be looked up by player ID.

## Checks (tests)
- Frames are continuous at 25 Hz, and each team has 11 players on the pitch.
- Every Home goal is scored at +x and every Away goal at −x, in both halves.
- The goal events give the correct final scores (3–0, 3–2 and 0–2).
