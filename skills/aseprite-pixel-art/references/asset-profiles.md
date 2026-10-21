# Asset profiles and game-readability rules

Pick the profile before drawing. The numbers are starting budgets, not laws; the readability
tests are the law.

## Quick selection table

| Asset | Canvas | Colours | Outline | Typical animation | Primary read |
|---|---|---|---|---|---|
| Inventory icon / potion | 16×16 (24/32 for complex) | 4–12 | 1 px | none | silhouette + one focal colour |
| Weapon / tool | 24×32 or 32×32 | 4–10 | 1 px | none / 2-frame glint | direction + grip + blade shape |
| Character | 24/32/48×32/48/64 | 6–12 | 1 px | idle 2–4, walk 4–6, attack 3–5 | silhouette + face + weapon |
| Enemy | 16/32/48 | 5–12 | 1 px | idle 2–4, move 4–6, attack 3–5 | silhouette unique from allies |
| Boss | 48/64/96 | 10–20 | 1–2 px | 6–10 per action | large masses + telegraph |
| Terrain tile | 16×16 or 32×32 | shared 12–24 | optional 1 px | water 4–8 | seamless material read |
| Prop / building | 16/32/48/64 | shared palette | 1 px (1–2 at 64+) | optional | footprint + entrance + scale |
| FX / projectile | 8–32 | 3–8 + core | none or selective | 3–6 | bright core + motion direction |
| UI icon / button | 16/24 | 3–8 | 1 px | 1–2 hover | shape at 1×, both themes |
| Sprite sheet | uniform cells | same set | same set | tags | cell alignment + pivot |

## Icons and items

- Design the silhouette first: a potion is a bottle, a sword is a blade + guard + grip, a key
  is a bow + shaft + bit. If the silhouette needs a label to be understood, simplify it.
- Use one focal colour. For a health potion the red liquid is the focal colour; the cork and
  glass are supporting values. Do not make the cork as saturated as the liquid.
- A 16×16 icon should fill roughly 35–65% of the canvas and leave a 1 px margin. Too small
  reads as a dot in a hotbar; too large touches the frame.
- Use a 1 px dark outline; at 24–32 px you may use a selective lighter outline on the lit side.
- Check on both a dark and a light UI background. Avoid relying on a white background.
- Do not put text on an icon.

## Characters

- **Silhouette identity:** one unique feature (hat, crest, cape, weapon, body proportion) that
  survives at 1× and in every direction. A humanoid with no silhouette feature is a generic
  pawn.
- **Proportions:** decide head-to-body ratio before drawing (chibi 1:2–1:3, heroic 1:4–1:6).
  Keep it consistent across the set.
- **Face:** eyes are the strongest read. At 32×32 use 2–3 px eye shapes with one glint; at
  16×16 use 1–2 px eyes. Mouth is a 2–5 px shape; do not add a nose unless the view needs it.
- **Hands/feet:** simplify to mitts/boots. Fingers at 32×32 are usually noise.
- **Outline:** 1 px outer contour; inner overlaps use a darker body colour, not black.
- **Layers:** keep at least `Body` and `FX`/`Weapon` if the game may recolour or swap parts.
  Use `add_layer` / `set_layer` early and keep the 1-based indices fixed for the build.
- **Anchor:** feet baseline at a fixed row; record the pivot (bottom centre) for the engine.

## Enemies

- The silhouette must be distinguishable from allies at a glance. Use a different body
  topology (blob, quadruped, floating, insect), not just a recolour.
- Give the player a telegraph: a wind-up pose, a colour accent, or a shape change before the
  attack. The telegraph frame is part of the gameplay read.
- Keep the weak point/focal area high contrast. Do not hide it under effects.
- Enemy palettes can be more saturated than environment palettes, but must share the world's
  light and outline weight.

## Weapons and tools

- Read the **direction** first: blade/head at one end, grip at the other. A diagonal composition
  is more dynamic than a horizontal bar, but align the grip to the character's hand.
- The grip is darker and less saturated; the blade/head gets the brightest value.
- Metal: hard value bands + one specular; wood: grain along the length; bone: warm off-white
  with dark cracks.
- Do not mirror a weapon carelessly: a sword's guard and blade asymmetry can flip the read.
- For a glint animation, use 1–2 frames and a 1 px highlight travelling along the edge.

## Terrain, props, and buildings

- **Perspective:** choose one (top-down, 3/4, side) and keep it across the set. A top-down
  floor tile must not show a side face; a 3/4 wall shows a top and a front.
- **Scale:** a door is a gameplay-scale reference. A character must fit through it; a crate
  must be carryable-looking. Do not mix scales between props.
- **Footprint and collision:** make the walkable/collidable area visually obvious. A building
  entrance should be a clear dark opening, not a texture patch.
- **Contact:** add a 1 px dark base/contact shadow where a prop meets the ground; do not use a
  soft blob unless the engine draws shadows separately.
- **Palette:** props should borrow colours from the terrain (moss, dirt, wood) so they belong
  to the same world. Avoid a new closed ramp for every prop.

## Tilesets

- Use a 16×16 or 32×32 grid. All tiles share the same cell size and palette; no exceptions.
- **Seamless edges:** the outer 1–2 px of a tile must continue the material of its neighbour.
  For a 47-blob autotile set, the bitmask layout is a contract; generate it from a model, not
  by hand-placing tiles.
- **Material continuity:** same-terrain neighbours must agree on every pixel of the middle of
  their shared border. Check a composed scene, not just the sheet.
- **Border jitter:** a perfectly straight edge looks machine-cut. Add a 1 px material jitter
  every few tiles, but keep the collision/edge logic intact.
- **Dominant tone:** a terrain has one dominant value; variants (cracks, pebbles, moss) are
  accents. A sheet where every tile has equal contrast reads as noise.
- **Transitions:** a terrain overlay (road, sand, water, stone) needs a complete transition
  matrix for the masks the game uses. Ship a manifest mapping slot → block/bitmask.
- **Water:** animate 4–8 frames, loop seamlessly in time and tile space; check both axes.
- **Sheet export:** uniform grid, no trim, 1–2 px padding if the engine filters; a manifest
  with cell size/columns is part of the deliverable. The MCP `export` op gives the sheet but no
  metadata; generate the manifest from the model.
- The MCP has no tilemap/autotile op; use ordinary grid cels and an external manifest.

## Effects and projectiles

- Effects are read by **value and motion**, not detail. Start with the brightest, largest shape
  on the impact frame, then decay.
- Use a bright core, a mid colour, and a dark edge. Do not outline an explosion with black
  unless the style uses black outlines everywhere.
- 3–6 frames is often enough: birth → peak → dissipate. A looping aura needs 4–8 frames.
- Anchor the effect at its origin (muzzle, hand, ground). The game may place it independently;
  keep the origin at the canvas centre or document the pivot.
- GIF transparency is binary. If the effect uses semi-alpha, verify the exported GIF; the
  engine may need a PNG sequence instead.
- Avoid additive-looking white cores on a light UI background; check the actual game context.

## UI icons and 9-slice

- Design at 16/24 px with a 1 px margin; test at 1× on both themes.
- Use 3–8 colours; the icon must read as a shape before its internal detail.
- For 9-slice panels, keep the corners fixed and the edges tileable; the MCP has no 9-slice
  export, so author the full panel and document the slice guides.
- Do not use anti-aliased text or tiny glyphs inside a pixel icon.

## Sprite sheets and engine handoff

- Fix the cell size and pivot before generating frames. Every frame is the same size; do not
  trim individual frames into inconsistent cells.
- Export `format="frames"` for per-frame checks and `format="sheet"` for the atlas. The sheet
  is a uniform grid; `columns` controls the layout. Use `padding` if the engine bleeds.
- For a 2D engine, set point/nearest filtering, disable mipmaps, and use integer scaling. Those
  are engine settings, not MCP settings; state them in the handoff.
- Ship the `.ase` source with named layers/tags and the exported PNG/GIF/sheet plus a manifest
  (cell size, columns, frame durations, tag ranges, pivot).
- Alpha: 0 or 255 only for pixel art. If the engine premultiplies alpha, test the edge; a
  semi-transparent fringe will look dirty.
