# Frame animation for pixel art

Animation is not “many drawings”. It is a small number of readable poses, spaced in time, with
one identity that survives the deformation. Design the poses, then the timing, then paint.

## 1. The five decisions before frame 1

1. **Action name and gameplay job** — idle, walk, run, attack, hit, death, cast, water loop.
2. **Loop or one-shot** — if it loops, decide the first/last relationship now.
3. **Frame count and cadence** — 4/6/8 frames, then per-frame seconds.
4. **Anchor** — feet, ground contact, projectile origin, or effect centre. This is the pivot the
   game uses; it must not drift between frames.
5. **Identity** — palette, light direction, face/features, secondary motion. Lock them.

## 2. Timing, spacing, and holds

- **Timing** is how long a pose is held; **spacing** is how far it moves between poses. Both
  matter. A fast action is not automatically a short frame duration; it is often a longer hold
  on the anticipation and a very short transition.
- Pixel-art games often run 8–12 fps for characters; 6–8 fps for heavy creatures; 12–15 fps
  for effects. Do not assume 24/30 fps; test at the game's real cadence.
- Hold the extreme poses. A contact, a hit, or an apex usually benefits from a longer duration
  than the in-between that leads to it.
- Use **per-frame durations**, not one rate for the whole action. The MCP `set_durations` op
  takes seconds; `add_frames` also takes seconds. `inspect.meta.frames` reads them back.
- A 2-frame idle at 0.4 s/frame can read better than 8 frames at 0.05 s. Fewer, stronger poses
  beat many weak ones.

Starting cadences (tune at game speed):

| Action | Frames | Typical duration per frame |
|---|---|---|
| Idle / breathing | 2–4 | 0.30–0.50 s |
| Walk | 6 (or 4) | 0.10–0.14 s |
| Run | 6–8 | 0.07–0.10 s |
| Attack | 3–5 | anticipation 0.07–0.10, hit 0.12–0.18, recovery 0.08–0.12 |
| Hit reaction | 1–2 | 0.08–0.12 |
| Death | 4–6 | 0.10–0.16, longer on the final hold |
| Cast / charge | 4–6 | build 0.10–0.20, release 0.06–0.10 |
| Water / ambient loop | 4–8 | 0.12–0.25 |
| Small FX | 3–6 | 0.04–0.10 |

The MCP `aseprite://timing/presets` resource gives basic suggestions; the table above is a
starting point, not a law. Validate in motion.

## 3. Key poses and the animation principles

- **Anticipation** — a small move opposite the action before it happens (crouch before a jump,
  pull back before a slash). It tells the player what is coming.
- **Squash and stretch** — volume changes with force. A slime squashes on contact, stretches in
  the air; a character compresses on landing. Keep the mass roughly constant; the silhouette
  can change a lot.
- **Follow-through and overlapping action** — the main mass stops first; cloth, hair, leaves,
  tails, and weapons continue and settle a frame or two later.
- **Arcs** — limbs and projectiles travel on curves, not straight lines. In pixel art, a 1–2 px
  arc offset is enough.
- **Slow in / slow out** — use holds and closer spacing near the extremes; a constant pixel
  step reads mechanical.
- **Exaggeration** — a 1 px motion at 32×32 may vanish at game scale. Exaggerate the key
  change (2–4 px for limbs, 1–2 px for a face) while keeping the anchor fixed.
- **Staging** — the action must be readable in silhouette. If the sword crosses the body or the
  arm merges with the torso, change the pose, not the shading.
- **Secondary action** — one secondary element (leaf, cape, droplet, dust) makes the motion
  feel alive; three make it noisy.

## 4. Loop design

A loop is not “frame N is close to frame 1”. It is a cycle whose last frame leads back into the
first.

- **Do not duplicate the first frame at the end** unless the hold is intentional. An 8-frame
  loop has 8 distinct poses; frame 8 → frame 1 is one step, not a repeat.
- **Loop closure check:** the last→first pixel diff should be in the same range as the other
  adjacent diffs, not zero and not a jump. `pixelqa.py frames --loop` reports it.
- **Baseline lock:** grounded loops (idle, walk) keep the contact foot on the same row. A
  1-pixel vertical bob is intentional; a 3-pixel drift is a foot-slide bug.
- **Phase symmetry:** a two-step walk is symmetric: left contact and right contact should have
  equal volume (or exact mirrored alpha if the view is mirrored). Check the numbers.
- **Loop-friendly secondary motion:** the leaf/cloth must complete its own cycle. If it ends
  leaning right and starts leaning left, the loop pops.
- **No dead frames:** avoid two identical adjacent frames. If a hold is needed, keep the pose
  and set a longer duration instead.

## 5. Walk / run cycle

The canonical 4-pose cycle, doubled for a 2-step loop:

1. **Contact** — front heel touches, back foot pushes off; arms opposite the legs.
2. **Down** — body sinks 1 px, weight on the front foot.
3. **Passing** — back leg passes under the body; body rises.
4. **Up** — push-off, highest point, front leg extends.

Then repeat with the other leg. A 6-frame cycle is contact/down/passing/contact/down/passing;
an 8-frame cycle adds one in-between on each step. Keep the foot plant: between contact and
down, the foot must not slide horizontally.

- In a side view, the far arm/leg is darker or partially hidden; do not draw both legs with the
  same value.
- In a front view, the legs alternate but the body bob is the main read.
- A robe/ghost can replace legs with a travelling hem wave and alternating feet; the same
  contact/down/passing structure still applies.

## 6. Idle

- 2–4 frames, 0.3–0.5 s each. Breathe with 1 px of chest/shoulder movement, a small head lag,
  and one secondary element.
- Keep the feet planted and the silhouette width stable. An idle that pulses in size looks like
  a broken scale animation.
- For a slime/blob, squash the body by 1–2 px and let the face move with it; the leaf/sprout
  lags by one frame.

## 7. Attack

Use at least anticipation → hit → recovery:

1. **Wind-up** — pull back, compress, or raise the weapon; 1–2 frames, short.
2. **Strike** — the largest pose change; 1 frame, often with a smear or a stretched weapon.
3. **Impact / hit** — hold the extreme; the hit frame is usually the longest.
4. **Recovery** — settle back to idle; 1–2 frames.

- The hitbox frame is a gameplay decision; name the tag/pose so the game can align the hit event.
- Do not animate the whole body evenly; the striking limb moves most, the head/torso follow.
- A weapon should translate/rotate as a whole shape; do not stretch only the guard.
- If the attack is a projectile, animate the origin flash separately; the projectile is its own
  asset.

## 8. Hit, death, and FX

- **Hit:** 1–2 frames. Flash the palette to a lighter value or offset the body 1 px; keep the
  anchor. The hit reaction should not look like a second idle.
- **Death:** 4–6 frames. Collapse under gravity, then hold the final pose. The silhouette
  should become clearly “dead” (flattened, slumped, dissolved), not just a dimmer idle.
- **FX:** 3–6 frames. Start at the strongest read (impact/ignition), then decay; use a bright
  core and a darker edge. Particles can have 1–2 px of AA or semi-alpha if the engine supports
  it, but GIF export quantises transparency; check the actual file.
- **Water/ambient loops:** 4–8 frames, tileable time phase. If the tile edges must match, the
  loop's first and last frames must connect seamlessly on both axes.

## 9. Direction handling

- Build each direction from the same body model, not by redrawing a different creature. The
  palette, proportions, face features, and outline weight must match.
- **Mirroring a whole frame flips the light.** If the light is fixed top-left in the world,
  the right-facing frame must keep the light on its top-left (screen space) rather than
  mirroring the shading. In practice: mirror the mask/geometry, then re-shade with the fixed
  light. A mirrored finished frame will differ by dozens of shading pixels; that is expected,
  and it is not a bug if the light is world-fixed.
- For a true mirror (light follows the character), mirror the whole frame and keep the
  silhouette alpha exact. Decide which convention the game uses and state it.
- Check left/right volume equality and bbox width; a one-pixel asymmetry is often a hand-mirror
  mistake.

## 10. Frame consistency gates

Run these before delivery:

- **Size:** every frame is the declared canvas size; every frame has alpha only 0/255.
- **Anchor:** grounded frames share the contact baseline; airborne frames follow a deliberate
  arc. The pivot does not drift.
- **Mass curve:** opaque pixel counts follow the action (squash → smaller, stretch → larger),
  with no accidental spikes. For idle/walk, max/min ≤1.35; for squash/stretch actions, ≤1.6.
- **Silhouette:** key poses are distinguishable in black; the identity features (ears, leaf,
  weapon, face) are present every frame.
- **Palette:** no new colours between frames except deliberate action colours (open mouth,
  flash, magic). A palette key cannot map to two different hex values.
- **Face:** eyes/mouth move together; no frame where a feature disappears because it fell
  outside the outline.
- **Secondary motion:** leaf/cloth/weapon has 1-frame lag and settles, not random jitter.
- **Loop:** last→first diff is non-zero and comparable to adjacent diffs. No duplicate adjacent
  frames.
- **Export:** GIF frame count and per-frame durations match `meta.frames`; sheet cells match
  the exported frame PNGs exactly.

## 11. Animation repair routing

| Defect | Likely cause | Repair |
|---|---|---|
| Foot slide | contact foot moves horizontally | pin the baseline; move only the free leg |
| Jitter | features/parts move independently | anchor the torso/head; use one model with phase offsets |
| Size pulsing | each frame normalized independently | normalize the group to a common body scale, then deform |
| Popping loop | last frame does not lead to first | match phase/leaf tilt; adjust last hold |
| Floaty jump | no crouch/landing, constant spacing | add anticipation and contact, use ease-in/out |
| Stiff attack | all body parts move together | add anticipation, follow-through, one-frame smear |
| Muddy motion | too many small changes | cut frames; hold extremes; move 2–4 px in key poses |
| Face morph | features redrawn per frame | place features relative to the deformed body; keep sizes constant |
| Wrong light on right view | whole frame mirrored | re-shade with the fixed light direction |
| GIF looks different | semi-alpha or disposal/quantisation | export at 1×, check frame count/durations, use 0/255 alpha |
