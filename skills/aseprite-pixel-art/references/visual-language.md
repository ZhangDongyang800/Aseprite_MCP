# Pixel-art visual language

Use this when you are making the art itself, not when you are choosing MCP calls. The
execution contract is in [mcp-playbook.md](mcp-playbook.md); the gates are in
[qa-and-repair.md](qa-and-repair.md).

## 1. Read order: silhouette → value → colour → detail

At game scale the player reads the shape first, then the light/dark structure, then the
colour, and only then any detail. Design in that order and audit in that order.

- **1× is the real test.** Judge the PNG at its native size. A 32×32 sprite that only works
  in an 8× preview is not finished.
- **Use integer previews** (4×, 8×) and nearest-neighbour. Fractional scaling invents pixels
  that the game will never show.
- **Silhouette test:** fill every visible pixel black and look again. If you cannot tell a
  potion from a lantern, no amount of shading will save it. `inspect` supports this with
  `view="silhouette"`.
- **One idea per asset.** A health potion needs a bottle silhouette and a red liquid read; a
  cork, a highlight, and a bubble are enough. Adding a skull, a label, and a chain to a 16×16
  icon destroys the read.

## 2. Canvas and detail budget

| Canvas | What survives | What does not |
|---|---|---|
| 8×8 | one silhouette, 2–4 colours, 1-pixel features | faces, fingers, text, separate limbs |
| 16×16 | icon detail, 2–3 value steps, small face, one accent | readable text, complex cloth folds, thin accessories |
| 24×24 | face + prop, 3–5 value steps, short animation | fine chain mail, hair strands |
| 32×32 | character anatomy, 3–5 value steps, secondary motion | individually modelled fingers, tiny facial features |
| 48×48+ | material texture, cloth folds, facial expression | still not an excuse for noise or over-rendering |

Choose the smallest canvas that carries the gameplay read, then design at that size. Do not
draw at 96×96 and downscale: resampling destroys authored pixels, thins lines, and introduces
semi-transparency. If the game needs a larger sprite, redesign at the larger size with the same
silhouette and palette.

Keep a **1 px transparent margin** around icons and characters unless the art intentionally
bleeds (an effect or a tile). The margin protects the sprite from cell edges and filtering.

## 3. Silhouette and shape language

- **Unique outer contour.** A character/enemy must be identifiable from the black shape alone.
  Use asymmetry, a prop, a crest, a weapon, a distinctive hat, or a body proportion.
- **Big shapes first.** Build the silhouette from 2–5 large masses. If the outline is a bag of
  bumps, simplify before shading.
- **Negative space is a shape.** The gap between an arm and the torso, inside a handle, or
  under a cape should be deliberate; it helps the eye parse the form.
- **Avoid tangents.** A line that just touches another shape creates an ambiguous read. Give
  it a clean gap or an overlap with a clear dark separation.
- **Favour 45° stair-steps.** A diagonal should step evenly (for example 1-1-1 or 1-2-2-1),
  not alternate 1-3-1. Clean steps are what separate “pixel art” from “low-res drawing”.
- **Anchor the mass.** Characters sit on a baseline; props sit on a ground line or have a
  clear pivot. A floating object needs a deliberate shadow or motion cue.

## 4. Value structure and light

Establish one dominant light direction and keep it for the whole asset set.

- **Three to five value groups** is typical: deep shadow, shadow, base, light, highlight.
  More groups do not automatically create more volume; they create mud.
- **Group the shadows.** Light falls on planes, not around every edge. Decide which planes
  face the light, then place 1–2-pixel shadow shapes. Do not trace the outline with a darker
  colour.
- **No pillow shading.** A concentric dark rim with a light centre reads as a pillow. The
  shadow must have a direction and a shape.
- **Cast shadows and contact.** A small dark shape under a foot, a handle, or a jaw gives
  contact. Do not put a soft airbrushed blob under a 16×16 icon; use a compact 1–2 px shape if
  the game does not handle shadows separately.
- **Highlights are earned.** Put a specular only on a shiny material or a wet surface, and
  keep it to one cluster. A white pixel on every bump reads as noise.
- **Hue-shift the ramp.** Shadows tend toward cooler/darker colours (blue, violet, deep
  green); highlights toward warmer/lighter colours (yellow, cream, warm grey). A ramp of the
  same hue with only brightness changed looks plastic. RGB×0.7 is a starting point, not a
  substitute for choosing a ramp.

## 5. Palette construction

- **Budget:** 4–8 colours for icons and small props; 6–12 for characters and enemies; 12–24
  for a shared tileset or a full scene. More colours are allowed only when each one has a
  job.
- **One palette per asset set.** Write it down before drawing. A new colour is a design
  decision, not a convenience.
- **Ramp shape:** 3–4 steps per material is enough. A metal ramp can be 3 steps plus a
  specular; a slime can be 4 steps plus a highlight; cloth can be 3 steps plus an accent.
- **Avoid pure black and pure white as general colours.** Use a dark hue-shifted outline and a
  warm/cool near-white highlight. Reserve true black/white for a deliberate accent (an eye
  pupil, a gem glint) if the style allows it.
- **Keep saturation controlled.** Large areas at maximum saturation vibrate; reserve the most
  saturated colour for the focal point (liquid, eye, gem, warning light).
- **Near-duplicates are waste.** If two colours differ by ≤8 in every RGB channel, they will
  read as one and the larger palette only adds noise. `inspect.metrics.near_duplicate_colors`
  and `pixelqa.py` flag this.
- **Background-independent icons.** Check the icon on both a dark and a light background.
  A design that only reads on one is not ready for a game UI.

Starter ramps:

```text
Moss slime   #24523B  #2F7A52  #4FAE68  #8BD97A  #D6F5A0   (outline #1E1A2E)
Potion glass #4B3B57  #8A7895  #CFC2D2  #FFF1DA
Potion red   #6E2233  #B93A4A  #ED6A5A
Cork         #5A3524  #A9683C  #D79A5B
```

Those are the actual ramps used by the examples, not theoretical swatches.

## 6. Clusters, edges, and noise

- **A cluster is a group of same-colour pixels with a readable shape.** Draw clusters, not
  individual pixels. A 1-pixel-wide snake of colour is usually noise.
- **No orphan pixels.** A visible pixel with no orthogonal visible neighbour is a defect
  unless it is a deliberate sparkle/star and documented. `isolated_pixels` counts them.
- **Avoid banding.** A gradient made of 1-pixel-wide bands following the outline looks like a
  topographic map. Use larger value shapes and a clear light side.
- **Break straight lines deliberately.** Perfectly straight, mechanical edges read as vector
  art. A 1-pixel jitter every few pixels can suggest stone or cloth, but keep the overall
  edge clean.
- **Do not dither at small sizes.** Dithering a 16×16 icon turns into noise at 1×. Reserve
  ordered dithering for large surfaces, skies, or a deliberate retro style.
- **Keep the fill solid.** Holes and accidental transparent pixels inside a shape are bugs;
  `paint_grid`'s `.` means “skip”, so a typo in a row is a hole.

## 7. Outlines

There is no outline op. The outline is authored into the grid.

- **Outer contour:** a continuous 1-pixel line around the silhouette. Use a dark,
  hue-shifted colour from the palette, not necessarily pure black.
- **Inner contours:** use a darkened base colour (not the outer-outline colour) to separate
  overlapping parts (arm over torso, lid over bottle). Too many black inner lines make the
  sprite look like a stained-glass window.
- **Selective outline:** on a lit edge, the outline can be replaced by a lighter body colour
  to suggest light wrapping around the form. Use this sparingly; a broken outline can also
  break the silhouette read at 1×.
- **Consistent weight:** 1 px at 16–32 px. Do not mix 1 px and 3 px contours unless the style
  is explicitly chunky. An outline that thins to 0 px at a corner is a bug, not a style.
- **No coloured halo.** Anti-aliasing an outline into transparency leaves semi-transparent
  pixels; at game scale they read as a dirty fringe and break GIF/alpha expectations.

## 8. Anti-aliasing: default none

For low-resolution game art, hard edges are usually correct.

- Use AA only on a **large, smooth curve** where the stair-step is visually distracting.
- Place AA **between two solid colours**, not between a colour and transparency. AA into
  transparency produces a halo on every background.
- One intermediate pixel is enough. More shades create a blurry edge that fights the pixel
  grid.
- Never AA every edge. A hard 45° edge is a feature of the medium.
- If a shape needs AA to read, the shape is probably too complex for the canvas size.

`paint_grid` writes alpha 255 only, so it naturally enforces hard edges. If `run_lua` adds
semi-transparent pixels, verify them explicitly; many game pipelines and GIF do not want them.

## 9. Materials

| Material | Value structure | Highlight | Common mistake |
|---|---|---|---|
| Metal | hard bands, strong light/dark split | 1–2 px specular, often cool/white | soft gradients, no reflected light |
| Cloth | broad folds, 2–3 steps | broad soft light, no sharp specular | drawing every fold as a black line |
| Wood | long grain along the form | small warm highlight on the edge | grain crossing the form randomly |
| Stone | chunky planes, chipped corners | cool top light, dark crevices | noisy speckle instead of planes |
| Foliage | clustered clumps, 2–3 greens | warm top-left light | individual leaves at 16 px |
| Glass/liquid | transparent body, distinct surface line | one sharp specular + a meniscus | shading glass like opaque metal |
| Slime/flesh | rounded mass, soft shadow edge | one large glossy highlight | pillow shading, outline traced with shadow |

Borrow colours between materials in a set (the moss on stone, the wood in a handle) so the
palette feels like one world.

## 10. Detail budget and focal hierarchy

- Pick **one focal point** per asset: the liquid, the eye, the blade, the gem, the mouth.
  Spend the brightest value and the sharpest contrast there.
- Secondary details should be one value step away from the surrounding area, not a new colour.
- At 16×16, a single-pixel feature is a commitment. At 32×32, use 2-pixel features for the
  face and 1-pixel features only for accents.
- Remove one accessory before calling it done. The silhouette should still work.

## 11. AI failure modes and their visual signature

| Symptom | Usual cause | Fix |
|---|---|---|
| Soup / speckle | per-pixel random shading, dithering, no clusters | rebuild from a design model; group values; remove orphan pixels |
| Pillow shading | shade follows the outline | choose one light direction; shape shadows by planes |
| Plastic look | single-hue ramps, white specular everywhere | hue-shift shadows/highlights; one specular |
| Muddy palette | too many near-duplicate colours | cut to 4–12; enforce ≥9-channel separation; reuse ramps |
| Broken silhouette | detail added before the shape | black-fill test; simplify to 2–5 masses |
| Jaggies | uneven diagonal steps | re-cluster the edge to 45° steps |
| Halos | AA into transparency | remove AA; keep alpha 0/255 |
| Inconsistent set | each asset grew its own palette/light | lock palette and light direction before the batch |
| Flat icon | no value grouping | add 1–2 shadow planes and one highlight cluster |
| Noisy face | eyes/mouth too small, too many features | enlarge the face features; remove nostril/brow detail |

## 12. Polish pass

Before delivery, do this in order:

1. Look at 1× on a dark background and a light background.
2. Fill the silhouette black; is the asset still identifiable?
3. Count the colours; remove any colour that is not doing a job.
4. Find every isolated pixel; remove it unless it is an intentional accent.
5. Check the outline at every corner; no gaps, no 3-pixel blobs.
6. Check the focal point has the highest contrast.
7. Compare against the rest of the set: same light, same palette, same outline weight, same
   scale and baseline.
8. Only then export and run the gates in [qa-and-repair.md](qa-and-repair.md).
