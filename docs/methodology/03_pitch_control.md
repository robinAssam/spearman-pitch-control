# 3. Pitch-control model (Spearman, 2018)

Code: [`model.py`](../../src/pitch_control/model.py). Parameters: `PitchControlConfig` in [`config.py`](../../src/pitch_control/config.py).
Figure: `python scripts/plot_pitch_control_frame.py`.

**The question:** if the ball were played to location *r* right now, what is the
probability that each team would end up controlling it there? Answering that
for every point on a grid gives the pitch-control surface.

![Pitch control, one frame](../../outputs/figures/pitch_control_frame.png)

*Game 2, 49th minute: Home 8 (on the ball) passes to Home 9, who heads in a goal
one second later. Blue = Home would win the ball there, orange = Away would.*

## The model in four pieces
1. **Ball travel time:** the distance to *r* ÷ 15 m/s.
2. **Time to intercept:** a player can't turn instantly. For 0.7 s (the
   reaction time) they keep moving at their current velocity, then run straight
   at *r* at 5 m/s. This gives each player an expected arrival time τ.
3. **Arrival uncertainty:** real players are faster or slower than that, so the
   probability that a player *has arrived by time T* is an S-shaped curve
   around τ (σ = 0.45 s) rather than a hard on/off switch.
4. **Control:** once the ball is at *r*, every player who has arrived gains
   control at rate λ = 4.3 per second (about 0.23 s on average), but only of
   the probability that nobody has claimed yet:

   > d control_j / dT = (1 − total control so far) × P(j has arrived by T) × λ_j

   This is integrated over time from the moment the ball arrives until 99% of
   the probability is assigned. Adding up each team's players gives that
   team's control.

## Choices and where the values come from
| Setting | Value | Source |
|---|---|---|
| Reaction time, max speed, σ, λ | 0.7 s, 5 m/s, 0.45 s, 4.3 /s | Spearman (2018), as used in the reference code. The 0.7 s and 5 m/s are confirmed by a second source. |
| Ball speed | constant 15 m/s | Reference-code simplification |
| Defender advantage κ | 1 (none) | The paper uses 1.72; the reference code uses 1. Configurable. |
| Goalkeeper control rate | 3 × λ | Reference-code choice (goalkeepers can use their hands) |
| Offside players | excluded | Reference-code choice: they can't legally receive the ball |
| Grid | 50 × 32 cells (configurable) | Detail vs speed trade-off: about 25 ms per frame |

## Implementation
- **Vectorised:** arrival times for all grid points × all players are computed
  at once with NumPy. Only the time loop is explicit.
- **Exact time steps:** within each 0.04 s step the control rates are treated
  as constant, and that step is solved exactly (exponential decay of the
  unclaimed probability). Unlike the reference code's simpler (Euler) step,
  this can never assign more than 100%. The Euler step is still available for
  comparison.

## Checks (tests)
- The arrival-time curve really has standard deviation σ.
- Both teams' control adds up to between 99% and 100% at every point.
- A player standing on the ball controls it (over 95%).
- Mirror-image teams give mirror-image surfaces.
- Two identical players split control 50/50, and a goalkeeper against an outfield player splits 75/25.
- Offside attackers are excluded, in both attacking directions.
