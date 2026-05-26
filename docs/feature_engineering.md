# Feature Engineering

NullCS is primarily a feature-engineering and representation-learning project. The goal is to describe behavioral process around engagements, not to rely on a single scoreboard statistic.

## Aim Behavior

Aim features describe how the crosshair moves relative to targets and fight context. They include aim error, aim convergence, aim stability, and how quickly the aim path changes near acquisition. These features are meant to capture whether the player reaches useful aim positions in an ordinary mechanical way or through an unusual process.

## Target Acquisition

Target acquisition features focus on the transition from not being aligned to being aligned. They include timing from visibility to shot, acquisition lag, aim dwell, and the shape of the final correction before firing. This family is important because suspicious and legitimate play can have similar outcomes while reaching those outcomes differently.

## Mouse Movement And Usercmd-Derived Signals

Usercmd-derived features describe the control path behind the view-angle movement. Instead of looking only at where the crosshair ended, these features study input bursts, input stability, mouse delta patterns, and how manual correction appears over time.

These features are meant to separate ordinary human correction from unusually efficient or unusually stable control paths.

## View-Angle Deltas, Velocity, And Jerk

View-angle features track per-tick angular movement:

- delta yaw and pitch
- angular velocity
- angular acceleration
- angular jerk
- snap velocity
- abrupt direction changes

Jerk and snap-like features are useful because very abrupt transitions may not be visible in aggregate aim accuracy. They also help distinguish smooth tracking, correction, and sudden acquisition behavior.

## Recoil Correction And Settling

Recoil-related features look at how aim behaves after shots begin. They include post-shot correction, settling after acquisition, and stability during weapon fire. The goal is not to label recoil assistance directly, but to measure whether the correction process looks unusual relative to encounter difficulty and player context.

## Movement Context

Movement features describe the player state around the engagement:

- walking or running
- airborne state
- crouch or movement pressure where available
- scoped state
- flashed state
- movement change near engagement

These features matter because timing and precision mean different things when a player is scoped, flashed, airborne, fully stopped, or moving through contact.

## Visibility Timing

Visibility features measure when an opponent becomes visible and how quickly the player reacts:

- first visible tick
- visible ticks before shot
- visible ticks before kill
- visibility-to-shot timing
- low-visibility and occlusion context

This family is important for analyst triage because unusually strong timing under limited visibility may deserve review, but visibility alone is not a verdict.

## Engagement Context

Engagement context features describe the fight itself:

- weapon
- distance
- damage timing
- shot timing
- headshot outcome
- round number
- opponent and victim context where available

These variables help avoid comparing unlike situations. A close-range pistol fight and a long-range rifle fight should not be interpreted the same way.

## Temporal Spacing

Temporal spacing features such as `ticks_since_last` and `ticks_to_next` describe sequencing. They help represent whether events occur in isolated moments, clustered bursts, or unusually tight chains. Timing distance can also provide context for whether a behavior is a repeated pattern or a one-off event.

## Low-Visibility Precision

Low-visibility precision features focus on performance when the target is obstructed, partially visible, or visible for a short interval. The goal is not to directly label information assistance. The goal is to measure whether precision remains unusually strong in contexts where ordinary visual information should be weaker.

## Difficulty-Conditioned Precision

Difficulty-conditioned precision asks whether the player remains unusually precise when the encounter is harder. Difficulty can include timing pressure, distance, motion, visibility, weapon context, and target acquisition burden.

This is important because high skill should raise baseline expectations. The model needs to distinguish strong ordinary precision from precision that remains unusually clean under difficult conditions.

## Collapse Rate And Collapse Ratio

Collapse features describe how quickly aim error collapses toward a useful target alignment. Collapse rate and collapse ratio are meant to capture the shape of convergence, not just the final aim state. Fast convergence can be legitimate, but it becomes more informative when combined with visibility, movement, input, and difficulty context.

## Input Burst And Input Stability

Input burst features capture concentrated mouse/control activity. Input stability features capture how steady or quiet the control path becomes after acquisition. Together they help describe whether the encounter involved ordinary manual adjustment, noisy correction, abrupt acquisition, or unusually stable post-acquire behavior.

## Aggregation Features

Per-encounter features are aggregated to the player-demo level using:

- counts
- rates
- means and medians
- quantiles
- top-k summaries
- spread and concentration measures
- support indicators

Aggregation is necessary because one moment should not dominate the read. The final player profile should reflect both signal strength and evidence support.
