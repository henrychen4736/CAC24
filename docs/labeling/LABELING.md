# Labelling guide: tennis technique

This is the labelling system for building a technique model from video. It
defines what to label for every stroke, how to label it consistently, and how the
labels are stored. The machine-readable definition is
[`schema.json`](schema.json); the checkpoint tables below are generated from it,
so change the schema first.

## 1. Principles

**Label observable checkpoints, not "good or bad technique".** A single
good/bad label mixes many faults into one answer. A model trained on it can't
say *what* is wrong, and in practice it learns very little: the multi-task study
in arXiv 2606.15992 labelled 1,281 strokes "good / bad posture" and its model
scored 62.6% against a 63.4% "always good" baseline. Instead, every label here is:

- **one thing** (shoulder turn, spacing, toss arm, ...),
- **at one moment** (end of backswing, contact, finish, ...),
- **with 2-4 answers** that each have a written definition.

**"Can't tell" is a real answer.** Many checkpoints can't be judged from some
camera angles (contact depth from directly behind, toss front/back from
behind). Use `cant_tell` rather than guessing; a confident wrong label does more
damage than a missing one. Use `not_applicable` when the checkpoint doesn't apply
to this ball (no opponent swing to split-step to).

**Descriptors are not faults.** Some checkpoints describe the stroke (stance,
contact height, serve stance) so the model can interpret the rest. Only the
values marked ⚠ are faults.

**Label the stroke, not the camera.** Technique is a property of the swing. When
several cameras filmed the same swing (`sync_group`), label it once using the
clearest view(s); those labels then apply to every view of that swing.

## 2. What gets labelled

Three levels, plus timestamps:

1. **Clip**: once per video file (camera, player, conditions).
2. **Stroke**: once per swing: type, usability, context, overall quality, main fault.
3. **Checkpoints**: per swing, the checklist for its stroke type.
4. **Events**: frame numbers of key moments. Only `contact` is required.

Checklist size per stroke type (label **core** first; add **extended** once core
labels are reliable):

| Stroke | Core | Extended |
|---|---|---|
| FH | 14 | 6 |
| 1HBH | 13 | 6 |
| 2HBH | 13 | 6 |
| FH slice | 14 | 6 |
| BH slice | 13 | 6 |
| FH volley | 10 | 5 |
| BH volley | 10 | 5 |
| serve | 12 | 7 |
| smash | 7 | 4 |

### 2.1 Clip fields

| Field | Required | Values | Meaning |
|---|---|---|---|
| `clip_id` | yes |  | Unique id |
| `source` | yes |  | Dataset name (caltennis, tennis_player_actions, own, ...) |
| `license` | yes |  | Licence of the footage (e.g. CC BY-NC 4.0) |
| `video` | yes |  | Path or URL |
| `sync_group` | no |  | Same value for clips filmed at the same moment by different cameras |
| `fps` | yes |  |  |
| `resolution` | yes |  | e.g. 1920x1080 |
| `camera_view` | yes | `back`, `back_corner`, `side`, `front`, `elevated` | See the view definitions |
| `camera_height` | yes | `low_under_1m`, `chest_1_2m`, `raised_2_4m`, `high_over_4m` |  |
| `player_distance` | yes | `near_under_6m`, `mid_6_12m`, `far_over_12m` |  |
| `camera_motion` | yes | `static`, `handheld`, `panning_zooming` |  |
| `player_id` | yes |  | Stable id per person across clips (needed for player-level splits) |
| `handedness` | yes | `right`, `left` |  |
| `player_level` | no | `beginner`, `intermediate`, `advanced`, `college`, `pro`, `unknown` |  |
| `surface` | no | `hard`, `clay`, `grass`, `indoor_hard`, `carpet`, `other` |  |
| `lighting` | no | `day`, `night_lights`, `indoor`, `mixed` |  |

### 2.2 Camera views

| View | Definition |
|---|---|
| `back` | Behind the baseline, roughly centred, camera at 0.5-2 m: the app's target view |
| `back_corner` | Behind the baseline near a corner, looking diagonally (about 20-50 degrees off the court axis) |
| `side` | Level with the player, beside the court, looking across it |
| `front` | Facing the player (from the net or the far side) |
| `elevated` | Camera above 3 m (stands, broadcast, top-down); judge body checkpoints only when the player is large and clear |

In the checkpoint tables, the **Views** column says how judgeable each checkpoint
is from each view: B = back, C = back corner, S = side, F = front, E = elevated;
✓ = judge normally, ~ = only when obvious (otherwise `cant_tell`), ✗ = always
`cant_tell`.

### 2.3 Stroke fields

| Field | Required | Values | Meaning |
|---|---|---|---|
| `stroke_type` | yes | `forehand`, `backhand_1h`, `backhand_2h`, `forehand_slice`, `backhand_slice`, `forehand_volley`, `backhand_volley`, `serve`, `smash`, `other` | The stroke actually played (correct the detector's suggestion if needed). |
| `stroke_variant` | no | `none`, `return`, `approach`, `lob`, `drop_shot`, `half_volley`, `swinging_volley`, `flat_serve`, `slice_serve`, `kick_serve`, `second_serve`, `defensive`, `other` | Optional refinement of the stroke type. |
| `context` | yes | `rally`, `feed`, `serve_practice`, `match_point_play`, `shadow` | How the ball arrived; 'shadow' = no ball. |
| `usable` | yes | `yes`, `partial`, `no` | yes = whole body visible through the stroke; partial = some joints hidden/cut off or blurred; no = skip. |
| `occlusion` | no | `none`, `net`, `other_player`, `fence`, `frame_edge`, `motion_blur`, `self` | Main reason if usable != yes (multi-select). |
| `ball_visible` | yes | `yes`, `no` | Can you see the ball around contact? |
| `outcome` | no | `in`, `out`, `net`, `unknown` | Where the shot went. |
| `direction` | no | `cross`, `middle`, `down_the_line`, `unknown` |  |
| `depth` | no | `deep`, `mid`, `short`, `unknown` | Bounce depth on the far side. |
| `overall_quality` | yes | `1`, `2`, `3`, `4`, `5` | 1 = breaks down (major faults); 2 = several clear faults; 3 = functional with one or two faults; 4 = solid, minor issues; 5 = textbook for this player's level of ball. |
| `skill_estimate` | yes | `beginner`, `intermediate`, `advanced`, `elite` | How good this stroke looks, ignoring who the player is. |
| `main_fault` | no | checkpoint id (or 'none') | If a coach could fix one thing, which checkpoint? Must be one marked as a fault on this stroke. |
| `second_fault` | no | checkpoint id (or 'none') | Optional. |
| `rater_confidence` | yes | `1`, `2`, `3` | 1 = guessing, 2 = fairly sure, 3 = certain. |
| `notes` | no | free text | Anything unusual. |

**`overall_quality` and `main_fault`** are the only holistic labels. They're
kept because they're what a coach gives, and they let us learn which faults
matter most (prioritisation). Don't train a model on `overall_quality` alone.

### 2.4 Events (timestamps)

| Stroke family | Event | Required | Definition |
|---|---|---|---|
| groundstroke | `prep_start` | no | First frame the shoulders/racket start turning back |
| groundstroke | `bounce` | no | Ball bounce on the player's side (if visible) |
| groundstroke | `backswing_end` | no | Racket furthest back, just before the forward swing |
| groundstroke | `contact` | yes | Frame of ball-racket contact (closest frame) |
| groundstroke | `finish` | no | Racket at the end of the follow-through |
| volley | `split_step` | no | Feet land from the split step |
| volley | `contact` | yes | Ball-racket contact |
| serve | `toss_release` | no | Ball leaves the tossing hand |
| serve | `trophy` | no | Tossing arm highest / racket up, knees most bent |
| serve | `racket_low` | no | Racket at its lowest point behind the back |
| serve | `contact` | yes | Ball-racket contact |
| serve | `landing` | no | First foot touches down |
| smash | `racket_low` | no | Racket at its lowest point behind the back |
| smash | `contact` | yes | Ball-racket contact |
| smash | `prep_start` | no | Player starts turning sideways |

Events let us check the pipeline's automatic key-frame detection and measure
timing (e.g. preparation before the bounce). Labelling `contact` on every
stroke and the other events on a 20% sample is enough.

## 3. Checkpoint reference

### Groundstrokes: forehand, one- and two-handed backhand

| Checkpoint | Look at | Question | Answers (⚠ = fault) | Views |
|---|---|---|---|---|
| `unit_turn_timing`<br>**core** | ball bounce on the player's side | When the ball bounces, have the shoulders and racket already turned back? Needs the ball. | `early`: Turn complete before the bounce<br>`on_time`: Turn finishing around the bounce<br>`late` ⚠: Still turning (or not started) after the bounce; rushed swing | B✓ C✓ S✓ F✓ E~ |
| `shoulder_turn`<br>**core** | end of backswing | How far have the shoulders turned away from the net at the end of the backswing? | `full`: Shoulder line at least perpendicular to the net (points at the net); back partly turned to the net<br>`partial`: Roughly halfway (about 45 degrees)<br>`minimal` ⚠: Chest still mostly facing the net; arm-only takeback | B✓ C✓ S~ F✓ E✓ |
| `non_hitting_arm`<br>**core** | end of backswing | Does the non-hitting arm extend across in front of the body during the turn? *(only FH)* | `extended`: Arm reaches across, roughly parallel to the baseline, helping the turn<br>`partial`: Arm lifts but stays bent close to the body<br>`tucked` ⚠: Arm hangs or stays tucked; does not take part in the turn | B✓ C✓ S✓ F✓ E~ |
| `racket_below_ball`<br>**core** | start of forward swing | Just before the forward swing, is the racket head below the height where contact happens? | `below`: Racket head clearly below contact height (sets up low-to-high)<br>`level`: About level with contact height<br>`above` ⚠: Racket stays above contact height and swings down or flat | B✓ C✓ S✓ F~ E~ |
| `knee_load`<br>**core** | end of backswing / just before contact for volleys | How bent are the legs while loading? | `bent`: Clear knee bend, hips lowered (an athletic 'sit')<br>`slight`: Small bend<br>`straight` ⚠: Legs nearly straight; standing tall | B✓ C✓ S✓ F✓ E~ |
| `split_step`<br>extended | as the opponent hits | Does the player do a small hop / split step as the opponent strikes the ball? Needs the ball. Skip (cant_tell) on fed balls where there is no opponent swing. | `yes`: Both feet leave or unweight the ground as the opponent hits<br>`late` ⚠: Split step happens clearly after the opponent's contact<br>`none` ⚠: No split step; flat-footed or already running | B✓ C✓ S✓ F✓ E✓ |
| `takeback_size`<br>extended | end of backswing | How big is the backswing? | `compact`: Racket goes back to around the back shoulder / side fence line<br>`big`: Racket goes clearly past the back shoulder<br>`excessive` ⚠: Racket wraps far behind the back; a long, late loop | B✓ C✓ S✓ F~ E✓ |
| `stance`<br>**core** | contact | What stance is the player in at contact? (Descriptive; not a fault by itself.) Descriptor: use it to interpret other checkpoints (e.g. rotation is expected to differ by stance). | `open`: Feet roughly parallel to the baseline<br>`semi_open`: Between open and neutral<br>`neutral`: Front foot stepped forward; feet roughly along the court<br>`closed`: Front foot stepped across beyond the back foot | B✓ C✓ S~ F✓ E✓ |
| `contact_depth`<br>**core** | contact | Along the direction of the court, where is the ball met relative to the body? From directly behind or in front this is a depth judgement; mark cant_tell unless it is obvious. | `in_front`: Ahead of the front hip (serve: ahead of the head/body, into the court)<br>`beside`: Level with the body<br>`late` ⚠: Behind the body (serve/smash: behind the head) | B~ C✓ S✓ F~ E✓ |
| `spacing`<br>**core** | contact | Sideways, how far from the body is the ball met? | `cramped` ⚠: Ball too close; elbow jammed against the body<br>`good`: Comfortable arm's-length space<br>`reaching` ⚠: Ball too far; lunging or reaching with a straight, stretched arm | B✓ C✓ S~ F✓ E✓ |
| `contact_height`<br>**core** | contact | At what height is the ball met? (Descriptive; the right height depends on the ball.) | `below_knee`: Below the knee<br>`knee_waist`: Knee to waist<br>`waist_chest`: Waist to chest (the comfortable zone)<br>`above_shoulder`: Above the shoulder | B✓ C✓ S✓ F✓ E✗ |
| `body_rotation`<br>**core** | contact to just after | Do the hips and shoulders rotate forward through contact? *(only FH, 2HBH)* One-handed backhands and slices use shoulders_stay_sideways instead. | `full`: Chest turns to face the net by or just after contact<br>`partial`: Some rotation, stops short<br>`arm_only` ⚠: Body stays still; the arm does the work | B✓ C✓ S~ F✓ E✓ |
| `shoulders_stay_sideways`<br>**core** | contact | Do the shoulders stay side-on (not opening up) through contact? *(only 1HBH)* | `yes`: Shoulders still roughly perpendicular to the net at contact<br>`opens_early` ⚠: Chest swings open to the net before contact | B✓ C✓ S~ F✓ E✓ |
| `balance_contact`<br>**core** | contact | Is the upper body balanced at contact? | `upright`: Trunk upright or leaning naturally into the shot<br>`leaning_back` ⚠: Falling or leaning away from the ball / backwards<br>`leaning_sideways` ⚠: Toppling sideways | B✓ C✓ S✓ F✓ E~ |
| `hitting_arm`<br>extended | contact | How is the hitting arm shaped at contact? *(only FH, 1HBH)* For one-handed backhands a straight arm is expected; mark 'bent' as a fault in analysis, not here. | `straight`: Nearly straight<br>`bent`: Clearly bent at the elbow but with space from the body<br>`jammed` ⚠: Elbow tucked into the body | B✓ C✓ S✓ F✓ E~ |
| `two_hands`<br>extended | contact | Do both hands stay on the racket through contact? *(only 2HBH)* | `yes`: Both hands on the grip until after contact<br>`releases_early` ⚠: Top hand comes off before or at contact | B✓ C✓ S✓ F✓ E~ |
| `head_still`<br>extended | contact | Does the head stay still and facing the contact zone through contact? | `still`: Head steady; still pointed at the contact zone just after contact<br>`moves` ⚠: Head jerks up or turns to look at the target before or at contact | B~ C✓ S✓ F✓ E~ |
| `weight_transfer`<br>extended | contact | Is the body weight moving forward into the ball? | `forward`: Weight moving forward / into the court<br>`neutral`: Stationary<br>`backward` ⚠: Moving away from the ball or back | B~ C✓ S✓ F~ E✓ |
| `swing_path`<br>**core** | contact to finish | What is the racket path through the ball? | `low_to_high`: Clearly rises through contact<br>`flat`: Mostly level<br>`high_to_low` ⚠: Comes down through the ball (unintended slice/chop) | B✓ C✓ S✓ F✓ E~ |
| `finish_position`<br>**core** | finish | Where does the racket finish? 'low_across' is a legitimate modern variation; only 'stops_short' is a fault. | `over_shoulder`: Over the opposite shoulder (two-hander: over the shoulder; one-hander: high, arm extended toward target)<br>`around_body`: Around the neck/body at shoulder height<br>`low_across`: Low across the body (windshield-wiper finish)<br>`stops_short` ⚠: Swing stops soon after contact | B✓ C✓ S✓ F✓ E✓ |
| `balance_finish`<br>**core** | about 0.5 s after contact | Is the player balanced after the shot? | `stable`: Holds the finish / recovers without stumbling<br>`steps_to_recover`: Needs an extra step to catch balance<br>`falls_off` ⚠: Clearly off balance | B✓ C✓ S✓ F✓ E~ |
| `recovery`<br>extended | after the finish | Does the player recover toward a ready position for the next ball? Needs the ball. | `recovers`: Moves back toward the middle / ready position<br>`watches` ⚠: Stays to watch the shot | B✓ C✓ S✓ F✓ E✓ |

### Slices: forehand and backhand slice

| Checkpoint | Look at | Question | Answers (⚠ = fault) | Views |
|---|---|---|---|---|
| `unit_turn_timing`<br>**core** | ball bounce on the player's side | When the ball bounces, have the shoulders and racket already turned back? Needs the ball. | `early`: Turn complete before the bounce<br>`on_time`: Turn finishing around the bounce<br>`late` ⚠: Still turning (or not started) after the bounce; rushed swing | B✓ C✓ S✓ F✓ E~ |
| `shoulder_turn`<br>**core** | end of backswing | How far have the shoulders turned away from the net at the end of the backswing? | `full`: Shoulder line at least perpendicular to the net (points at the net); back partly turned to the net<br>`partial`: Roughly halfway (about 45 degrees)<br>`minimal` ⚠: Chest still mostly facing the net; arm-only takeback | B✓ C✓ S~ F✓ E✓ |
| `non_hitting_arm`<br>**core** | end of backswing | Does the non-hitting arm extend across in front of the body during the turn? *(only FH slice)* | `extended`: Arm reaches across, roughly parallel to the baseline, helping the turn<br>`partial`: Arm lifts but stays bent close to the body<br>`tucked` ⚠: Arm hangs or stays tucked; does not take part in the turn | B✓ C✓ S✓ F✓ E~ |
| `knee_load`<br>**core** | end of backswing / just before contact for volleys | How bent are the legs while loading? | `bent`: Clear knee bend, hips lowered (an athletic 'sit')<br>`slight`: Small bend<br>`straight` ⚠: Legs nearly straight; standing tall | B✓ C✓ S✓ F✓ E~ |
| `slice_takeback_high`<br>**core** | end of backswing | Does the racket start above the height of contact? | `above`: Racket starts clearly above contact height<br>`level`: Starts about level<br>`below` ⚠: Starts below contact height | B✓ C✓ S✓ F✓ E~ |
| `split_step`<br>extended | as the opponent hits | Does the player do a small hop / split step as the opponent strikes the ball? Needs the ball. Skip (cant_tell) on fed balls where there is no opponent swing. | `yes`: Both feet leave or unweight the ground as the opponent hits<br>`late` ⚠: Split step happens clearly after the opponent's contact<br>`none` ⚠: No split step; flat-footed or already running | B✓ C✓ S✓ F✓ E✓ |
| `takeback_size`<br>extended | end of backswing | How big is the backswing? | `compact`: Racket goes back to around the back shoulder / side fence line<br>`big`: Racket goes clearly past the back shoulder<br>`excessive` ⚠: Racket wraps far behind the back; a long, late loop | B✓ C✓ S✓ F~ E✓ |
| `stance`<br>**core** | contact | What stance is the player in at contact? (Descriptive; not a fault by itself.) Descriptor: use it to interpret other checkpoints (e.g. rotation is expected to differ by stance). | `open`: Feet roughly parallel to the baseline<br>`semi_open`: Between open and neutral<br>`neutral`: Front foot stepped forward; feet roughly along the court<br>`closed`: Front foot stepped across beyond the back foot | B✓ C✓ S~ F✓ E✓ |
| `contact_depth`<br>**core** | contact | Along the direction of the court, where is the ball met relative to the body? From directly behind or in front this is a depth judgement; mark cant_tell unless it is obvious. | `in_front`: Ahead of the front hip (serve: ahead of the head/body, into the court)<br>`beside`: Level with the body<br>`late` ⚠: Behind the body (serve/smash: behind the head) | B~ C✓ S✓ F~ E✓ |
| `spacing`<br>**core** | contact | Sideways, how far from the body is the ball met? | `cramped` ⚠: Ball too close; elbow jammed against the body<br>`good`: Comfortable arm's-length space<br>`reaching` ⚠: Ball too far; lunging or reaching with a straight, stretched arm | B✓ C✓ S~ F✓ E✓ |
| `contact_height`<br>**core** | contact | At what height is the ball met? (Descriptive; the right height depends on the ball.) | `below_knee`: Below the knee<br>`knee_waist`: Knee to waist<br>`waist_chest`: Waist to chest (the comfortable zone)<br>`above_shoulder`: Above the shoulder | B✓ C✓ S✓ F✓ E✗ |
| `shoulders_stay_sideways`<br>**core** | contact | Do the shoulders stay side-on (not opening up) through contact? | `yes`: Shoulders still roughly perpendicular to the net at contact<br>`opens_early` ⚠: Chest swings open to the net before contact | B✓ C✓ S~ F✓ E✓ |
| `balance_contact`<br>**core** | contact | Is the upper body balanced at contact? | `upright`: Trunk upright or leaning naturally into the shot<br>`leaning_back` ⚠: Falling or leaning away from the ball / backwards<br>`leaning_sideways` ⚠: Toppling sideways | B✓ C✓ S✓ F✓ E~ |
| `slice_path`<br>**core** | contact | What is the racket path through the ball? | `high_to_low_forward`: Moves down and forward through the ball<br>`chop` ⚠: Steep downward chop with little forward movement<br>`flat_or_up` ⚠: Level or rising path | B✓ C✓ S✓ F✓ E~ |
| `head_still`<br>extended | contact | Does the head stay still and facing the contact zone through contact? | `still`: Head steady; still pointed at the contact zone just after contact<br>`moves` ⚠: Head jerks up or turns to look at the target before or at contact | B~ C✓ S✓ F✓ E~ |
| `weight_transfer`<br>extended | contact | Is the body weight moving forward into the ball? | `forward`: Weight moving forward / into the court<br>`neutral`: Stationary<br>`backward` ⚠: Moving away from the ball or back | B~ C✓ S✓ F~ E✓ |
| `slice_face`<br>extended | contact | Is the racket face open (tilted back) at contact? Needs a clear, close view of the racket; mark cant_tell otherwise. | `open`: Face tilted back slightly<br>`flat`: Face vertical<br>`very_open` ⚠: Face tilted far back (floats the ball) | B~ C~ S✓ F~ E✗ |
| `balance_finish`<br>**core** | about 0.5 s after contact | Is the player balanced after the shot? | `stable`: Holds the finish / recovers without stumbling<br>`steps_to_recover`: Needs an extra step to catch balance<br>`falls_off` ⚠: Clearly off balance | B✓ C✓ S✓ F✓ E~ |
| `slice_finish`<br>**core** | finish | Where does the racket finish? | `forward_extended`: Extends forward toward the target, arm long<br>`wraps` ⚠: Wraps around the body<br>`stops_short` ⚠: Stops right after contact | B✓ C✓ S✓ F✓ E~ |
| `recovery`<br>extended | after the finish | Does the player recover toward a ready position for the next ball? Needs the ball. | `recovers`: Moves back toward the middle / ready position<br>`watches` ⚠: Stays to watch the shot | B✓ C✓ S✓ F✓ E✓ |

### Volleys

| Checkpoint | Look at | Question | Answers (⚠ = fault) | Views |
|---|---|---|---|---|
| `knee_load`<br>**core** | end of backswing / just before contact for volleys | How bent are the legs while loading? | `bent`: Clear knee bend, hips lowered (an athletic 'sit')<br>`slight`: Small bend<br>`straight` ⚠: Legs nearly straight; standing tall | B✓ C✓ S✓ F✓ E~ |
| `volley_backswing`<br>**core** | just before contact | How big is the backswing? | `compact`: Racket stays in front of the body; little or no backswing<br>`small`: Small takeback to about the shoulder<br>`big` ⚠: Full swing | B✓ C✓ S✓ F✓ E✓ |
| `split_step`<br>extended | as the opponent hits | Does the player do a small hop / split step as the opponent strikes the ball? Needs the ball. Skip (cant_tell) on fed balls where there is no opponent swing. | `yes`: Both feet leave or unweight the ground as the opponent hits<br>`late` ⚠: Split step happens clearly after the opponent's contact<br>`none` ⚠: No split step; flat-footed or already running | B✓ C✓ S✓ F✓ E✓ |
| `stance`<br>**core** | contact | What stance is the player in at contact? (Descriptive; not a fault by itself.) Descriptor: use it to interpret other checkpoints (e.g. rotation is expected to differ by stance). | `open`: Feet roughly parallel to the baseline<br>`semi_open`: Between open and neutral<br>`neutral`: Front foot stepped forward; feet roughly along the court<br>`closed`: Front foot stepped across beyond the back foot | B✓ C✓ S~ F✓ E✓ |
| `contact_depth`<br>**core** | contact | Along the direction of the court, where is the ball met relative to the body? From directly behind or in front this is a depth judgement; mark cant_tell unless it is obvious. | `in_front`: Ahead of the front hip (serve: ahead of the head/body, into the court)<br>`beside`: Level with the body<br>`late` ⚠: Behind the body (serve/smash: behind the head) | B~ C✓ S✓ F~ E✓ |
| `spacing`<br>**core** | contact | Sideways, how far from the body is the ball met? | `cramped` ⚠: Ball too close; elbow jammed against the body<br>`good`: Comfortable arm's-length space<br>`reaching` ⚠: Ball too far; lunging or reaching with a straight, stretched arm | B✓ C✓ S~ F✓ E✓ |
| `contact_height`<br>**core** | contact | At what height is the ball met? (Descriptive; the right height depends on the ball.) | `below_knee`: Below the knee<br>`knee_waist`: Knee to waist<br>`waist_chest`: Waist to chest (the comfortable zone)<br>`above_shoulder`: Above the shoulder | B✓ C✓ S✓ F✓ E✗ |
| `balance_contact`<br>**core** | contact | Is the upper body balanced at contact? | `upright`: Trunk upright or leaning naturally into the shot<br>`leaning_back` ⚠: Falling or leaning away from the ball / backwards<br>`leaning_sideways` ⚠: Toppling sideways | B✓ C✓ S✓ F✓ E~ |
| `volley_step`<br>**core** | contact | Does the player step forward into the volley with the opposite foot? | `opposite_foot`: Steps forward with the foot opposite the hitting side<br>`same_foot`: Steps with the same-side foot<br>`no_step` ⚠: No forward step | B✓ C✓ S✓ F✓ E✓ |
| `head_still`<br>extended | contact | Does the head stay still and facing the contact zone through contact? | `still`: Head steady; still pointed at the contact zone just after contact<br>`moves` ⚠: Head jerks up or turns to look at the target before or at contact | B~ C✓ S✓ F✓ E~ |
| `weight_transfer`<br>extended | contact | Is the body weight moving forward into the ball? | `forward`: Weight moving forward / into the court<br>`neutral`: Stationary<br>`backward` ⚠: Moving away from the ball or back | B~ C✓ S✓ F~ E✓ |
| `volley_racket_head`<br>extended | contact | At contact, is the racket head above the wrist? | `above`: Racket head above the wrist<br>`level`: About level<br>`below` ⚠: Racket head drooping below the wrist (on a ball above the knee) | B~ C✓ S✓ F~ E✗ |
| `balance_finish`<br>**core** | about 0.5 s after contact | Is the player balanced after the shot? | `stable`: Holds the finish / recovers without stumbling<br>`steps_to_recover`: Needs an extra step to catch balance<br>`falls_off` ⚠: Clearly off balance | B✓ C✓ S✓ F✓ E~ |
| `volley_follow`<br>**core** | finish | How long is the follow-through? | `short_punch`: Short, firm punch toward the target<br>`long_swing` ⚠: Long swinging finish | B✓ C✓ S✓ F✓ E✓ |
| `recovery`<br>extended | after the finish | Does the player recover toward a ready position for the next ball? Needs the ball. | `recovers`: Moves back toward the middle / ready position<br>`watches` ⚠: Stays to watch the shot | B✓ C✓ S✓ F✓ E✓ |

### Serve

| Checkpoint | Look at | Question | Answers (⚠ = fault) | Views |
|---|---|---|---|---|
| `toss_arm`<br>**core** | toss release | Is the tossing arm straight as it releases the ball? | `straight`: Arm long and straight, lifting from the shoulder<br>`slightly_bent`: Some elbow bend<br>`bent` ⚠: Elbow clearly bent; flicked toss | B✓ C✓ S✓ F✓ E~ |
| `toss_placement`<br>**core** | top of the toss | Where is the toss relative to the body? Needs the ball. From behind you can judge left/right well but in front/behind poorly; from the side the reverse. | `in_front_hitting_side`: Slightly in front and toward the hitting side<br>`above_head`: Straight above the head<br>`behind` ⚠: Behind the head<br>`too_far_side` ⚠: Far out to either side | B~ C✓ S✓ F~ E✓ |
| `trophy_position`<br>**core** | trophy | At the trophy position: hitting elbow about shoulder height, racket up, tossing arm pointing up? | `full`: All three present<br>`partial`: One element missing (e.g. elbow low or tossing arm already dropped)<br>`missing` ⚠: No recognisable trophy position | B✓ C✓ S✓ F✓ E~ |
| `serve_knee_bend`<br>**core** | trophy | How much do the knees bend in the loading phase? | `deep`: Clear bend<br>`moderate`: Some bend<br>`none` ⚠: Legs straight | B✓ C✓ S✓ F✓ E~ |
| `shoulder_tilt`<br>**core** | trophy | Is the tossing shoulder higher than the hitting shoulder at the trophy? | `tilted`: Tossing shoulder clearly higher<br>`slight`: Slightly higher<br>`level` ⚠: Shoulders level | B✓ C✓ S~ F✓ E~ |
| `serve_stance`<br>extended | start | Which stance? (Descriptive.) | `platform`: Feet stay apart through the motion<br>`pinpoint`: Back foot slides up next to the front foot | B✓ C✓ S✓ F✓ E✓ |
| `toss_height`<br>extended | top of the toss | How high is the toss compared with the reach at contact? Needs the ball. | `too_low` ⚠: Player has to rush or hit with a bent arm<br>`ok`: Peaks around or a little above full reach<br>`too_high` ⚠: Ball falls well past the contact point; long wait | B✓ C✓ S✓ F✓ E~ |
| `racket_drop`<br>**core** | lowest racket position behind the back | Does the racket drop down behind the back before swinging up? | `full`: Racket head points toward the ground behind the back<br>`partial`: Racket drops to about shoulder level<br>`none` ⚠: Racket pushed forward from the trophy ('waiter's tray' / pushing) | B✓ C✓ S✓ F~ E~ |
| `leg_drive`<br>**core** | trophy to contact | Do the legs drive up into the ball? | `explosive`: Strong extension; feet leave the ground<br>`some`: Legs extend but stay grounded<br>`none` ⚠: No push from the legs | B✓ C✓ S✓ F✓ E~ |
| `serve_rhythm`<br>extended | whole motion | Is the motion continuous? | `smooth`: One continuous motion from toss to contact<br>`pause` ⚠: Clear pause (e.g. at the trophy) that breaks the chain<br>`rushed` ⚠: Hurried; toss and swing out of sync | B✓ C✓ S✓ F✓ E~ |
| `contact_depth`<br>**core** | contact | Along the direction of the court, where is the ball met relative to the body? From directly behind or in front this is a depth judgement; mark cant_tell unless it is obvious. | `in_front`: Ahead of the front hip (serve: ahead of the head/body, into the court)<br>`beside`: Level with the body<br>`late` ⚠: Behind the body (serve/smash: behind the head) | B~ C✓ S✓ F~ E✓ |
| `balance_contact`<br>**core** | contact | Is the upper body balanced at contact? | `upright`: Trunk upright or leaning naturally into the shot<br>`leaning_back` ⚠: Falling or leaning away from the ball / backwards<br>`leaning_sideways` ⚠: Toppling sideways | B✓ C✓ S✓ F✓ E~ |
| `contact_reach`<br>**core** | contact | Is the ball hit at full reach? | `full`: Hitting arm and body extended up; ball at the highest comfortable point<br>`slightly_low`: Arm a little bent or body a little crouched<br>`low` ⚠: Clearly below full reach | B✓ C✓ S✓ F✓ E~ |
| `head_still`<br>extended | contact | Does the head stay still and facing the contact zone through contact? | `still`: Head steady; still pointed at the contact zone just after contact<br>`moves` ⚠: Head jerks up or turns to look at the target before or at contact | B~ C✓ S✓ F✓ E~ |
| `tossing_arm_tuck`<br>extended | contact | Does the tossing arm pull down and in toward the body as the racket swings up? | `tucks`: Arm pulls down into the chest/stomach<br>`drops_early` ⚠: Arm falls well before the swing<br>`stays_up` ⚠: Arm stays up or flails out | B✓ C✓ S✓ F✓ E~ |
| `balance_finish`<br>**core** | about 0.5 s after contact | Is the player balanced after the shot? | `stable`: Holds the finish / recovers without stumbling<br>`steps_to_recover`: Needs an extra step to catch balance<br>`falls_off` ⚠: Clearly off balance | B✓ C✓ S✓ F✓ E~ |
| `serve_finish`<br>**core** | finish | Where does the racket finish? | `across_body`: Finishes past the body on the non-hitting side<br>`hitting_side`: Finishes on the hitting side<br>`stops_short` ⚠: Stops in front of the body | B✓ C✓ S✓ F✓ E✓ |
| `pronation`<br>extended | just after contact | Does the forearm rotate the racket face outward after contact (thumb turning down)? Needs 60 fps and a close view; usually cant_tell. | `yes`: Clear outward rotation<br>`no` ⚠: Racket face stays facing forward / wrist slaps down | B~ C~ S~ F~ E✗ |
| `serve_landing`<br>extended | landing | How does the player land? | `front_foot_forward`: Lands on the front foot, moving into the court<br>`both_feet_back`: Lands on both feet behind or at the baseline<br>`off_balance` ⚠: Stumbles or lands sideways | B✓ C✓ S✓ F✓ E✓ |

### Smash

| Checkpoint | Look at | Question | Answers (⚠ = fault) | Views |
|---|---|---|---|---|
| `smash_turn`<br>**core** | as the lob goes up | Does the player turn sideways early, hitting shoulder back? Needs the ball. | `early`: Turns as soon as the lob is recognised<br>`late` ⚠: Turns late<br>`none` ⚠: Stays facing the net | B✓ C✓ S✓ F✓ E✓ |
| `smash_pointing_arm`<br>**core** | before contact | Does the non-hitting arm point up at the ball? | `yes`: Arm up, tracking the ball<br>`no` ⚠: Arm down or not tracking | B✓ C✓ S✓ F✓ E~ |
| `split_step`<br>extended | as the opponent hits | Does the player do a small hop / split step as the opponent strikes the ball? Needs the ball. Skip (cant_tell) on fed balls where there is no opponent swing. | `yes`: Both feet leave or unweight the ground as the opponent hits<br>`late` ⚠: Split step happens clearly after the opponent's contact<br>`none` ⚠: No split step; flat-footed or already running | B✓ C✓ S✓ F✓ E✓ |
| `smash_footwork`<br>extended | before contact | How does the player move to the ball? Needs the ball. | `side_steps`: Side-steps or crossover steps, staying sideways<br>`backpedals` ⚠: Runs backwards facing the net<br>`no_move` ⚠: Does not adjust; reaches for the ball | B✓ C✓ S✓ F✓ E✓ |
| `contact_depth`<br>**core** | contact | Along the direction of the court, where is the ball met relative to the body? From directly behind or in front this is a depth judgement; mark cant_tell unless it is obvious. | `in_front`: Ahead of the front hip (serve: ahead of the head/body, into the court)<br>`beside`: Level with the body<br>`late` ⚠: Behind the body (serve/smash: behind the head) | B~ C✓ S✓ F~ E✓ |
| `balance_contact`<br>**core** | contact | Is the upper body balanced at contact? | `upright`: Trunk upright or leaning naturally into the shot<br>`leaning_back` ⚠: Falling or leaning away from the ball / backwards<br>`leaning_sideways` ⚠: Toppling sideways | B✓ C✓ S✓ F✓ E~ |
| `contact_reach`<br>**core** | contact | Is the ball hit at full reach? | `full`: Hitting arm and body extended up; ball at the highest comfortable point<br>`slightly_low`: Arm a little bent or body a little crouched<br>`low` ⚠: Clearly below full reach | B✓ C✓ S✓ F✓ E~ |
| `head_still`<br>extended | contact | Does the head stay still and facing the contact zone through contact? | `still`: Head steady; still pointed at the contact zone just after contact<br>`moves` ⚠: Head jerks up or turns to look at the target before or at contact | B~ C✓ S✓ F✓ E~ |
| `balance_finish`<br>**core** | about 0.5 s after contact | Is the player balanced after the shot? | `stable`: Holds the finish / recovers without stumbling<br>`steps_to_recover`: Needs an extra step to catch balance<br>`falls_off` ⚠: Clearly off balance | B✓ C✓ S✓ F✓ E~ |
| `serve_finish`<br>**core** | finish | Where does the racket finish? | `across_body`: Finishes past the body on the non-hitting side<br>`hitting_side`: Finishes on the hitting side<br>`stops_short` ⚠: Stops in front of the body | B✓ C✓ S✓ F✓ E✓ |
| `pronation`<br>extended | just after contact | Does the forearm rotate the racket face outward after contact (thumb turning down)? Needs 60 fps and a close view; usually cant_tell. | `yes`: Clear outward rotation<br>`no` ⚠: Racket face stays facing forward / wrist slaps down | B~ C~ S~ F~ E✗ |

## 4. Workflow

**Pass 0: calibrate the rubric (once, about 1 hour).**
Pick 20 strokes covering several players and every stroke type. Label them,
ideally next to a coach, and write down every disagreement or hesitation as a
clarifying sentence in the checkpoint's `notes`. Repeat with 20 new strokes
until you rarely hesitate.

**Pass 1: strokes (fast).** The pipeline proposes each swing with a contact
frame. For each one: confirm or reject it, set `stroke_type`, `usable`,
`context`, `ball_visible`, and correct the `contact` frame if needed. Skip
anything with `usable = no`.

**Pass 2: checkpoints.** Watch the swing at normal speed once, then step
through it frame by frame around each checkpoint's moment. Answer the core
checklist, then `overall_quality`, `skill_estimate`, `main_fault` and
`rater_confidence`. Budget about 45-60 s per stroke for the core list.

**Order of work.** Label one stroke type at a time (all forehands, then all
backhands, ...); switching checklists between every stroke causes mistakes.
Shuffle the strokes of that type across players and clips so drift over a
session doesn't line up with one player.

## 5. Quality control

- **Double-label 15-20%** of strokes (a second person, or yourself again after
  at least a week without looking at your first answers).
- **Measure agreement per checkpoint** with Cohen's kappa (weighted kappa for
  ordered answers like `full / partial / minimal`).
  - kappa ≥ 0.6: keep.
  - 0.4-0.6: rewrite the definitions, re-calibrate, re-label that checkpoint.
  - < 0.4 after a rewrite: retire it. If people can't agree, a model can't learn it.
- **Track `cant_tell` rates per view.** A checkpoint that is `cant_tell` most of
  the time from the back view is not one the product can promise.
- **Re-check old labels** when a definition changes (the schema has a `version`).

## 6. Sampling and amount

- **Players matter more than strokes.** 20 strokes each from 30 players beats
  200 from 3. Cap each player at about 30 strokes per stroke type.
- **Cover levels and conditions:** beginners through advanced, left-handers,
  different surfaces and light, and both near and far camera distances.
- **Starting target:** about 300 usable strokes per main stroke type (forehand,
  two-handed backhand, serve) from at least 20 players. At ~1 minute each, that
  is roughly 15 hours. Slices, volleys and smashes can come later.
- **Faults must exist in the data.** If 95% of strokes are `full` shoulder turn,
  the model learns nothing about it; deliberately include recreational players.

## 7. Splits (avoid leakage)

- Split train / validation / test **by player**, never by stroke.
- Every view in a `sync_group` goes into the **same** split: the same swing
  seen from another camera is not new data for evaluation.
- Keep a **back-view test set** (players never used for training) and report
  results on it separately; that's the number that matters for the product.

## 8. Training across camera angles

Labels are per stroke, so footage from any angle can be used for training as long
as each checkpoint is marked `cant_tell` where the view can't show it.

- **Synchronised multi-view footage (e.g. CalTennis) multiplies labels:** label
  a swing once, get 2-6 training examples, and the views must agree, which is a
  free consistency check.
- **Represent the body, not the image.** The pipeline already converts pose to a
  body-centred 3D frame (hip-centred, scaled by torso length, rotated to the
  player), so much of the camera angle cancels out. What doesn't cancel is
  *error*: depth is least reliable along the camera axis, and limbs hide behind
  the body differently from each angle. So also give the model the camera view
  (and per-joint confidence) as inputs.
- **Augment views:** rotate 3D poses about the vertical axis, and, where
  multi-view 3D is available, re-project it into virtual cameras at other
  angles, adding detector-like noise.
- **Evaluate on back view only**, with back-view players held out.
- **Elevated / broadcast footage:** use it for stroke type and timing, not body
  checkpoints, unless the player is large and clear.

## 9. File formats

Store labels under `backend/data/labels/` (git-ignored with the rest of `data/`).

`clips.csv`: one row per video, columns = clip fields.

`strokes.jsonl`: one JSON object per stroke:

```json
{
  "stroke_id": "cal_0918_n01_s007",
  "clip_id": "cal_0918_n01",
  "sync_group": "cal_0918_rally1",
  "labeler": "henry",
  "schema_version": 1,
  "events": {"contact": 1167, "backswing_end": 1139},
  "stroke": {
    "stroke_type": "forehand", "context": "rally", "usable": "yes", "ball_visible": "yes",
    "outcome": "in", "overall_quality": 3, "skill_estimate": "intermediate",
    "main_fault": "unit_turn_timing", "rater_confidence": 2
  },
  "checkpoints": {
    "unit_turn_timing": "late", "shoulder_turn": "partial", "non_hitting_arm": "extended",
    "racket_below_ball": "below", "knee_load": "slight", "stance": "semi_open",
    "contact_depth": "cant_tell", "spacing": "good", "contact_height": "waist_chest",
    "body_rotation": "full", "balance_contact": "upright", "swing_path": "low_to_high",
    "finish_position": "over_shoulder", "balance_finish": "stable"
  }
}
```

Frame numbers refer to the original video's frame index (0-based).
