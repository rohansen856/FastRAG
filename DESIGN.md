---
name: FastRAG
description: Cited or silent. A voice-enabled, multilingual RAG that shows its sources.
colors:
  paper: "oklch(0.985 0.002 90)"
  ink: "oklch(0.12 0.01 60)"
  graphite: "oklch(0.45 0.02 60)"
  vellum: "oklch(0.94 0.005 90)"
  rule: "oklch(0.88 0.01 90)"
  hairline: "color-mix(in oklch, oklch(0.12 0.01 60) 10%, transparent)"
  sheet: "oklch(1 0 0)"
  answered: "oklch(59.6% 0.145 163.225)"
  answered-ink: "oklch(43.2% 0.095 166.913)"
  abstained: "oklch(76.9% 0.188 70.08)"
  abstained-ink: "oklch(47.3% 0.137 46.201)"
  refused: "oklch(58.6% 0.253 17.585)"
  refused-ink: "oklch(51.4% 0.222 16.935)"
typography:
  display:
    fontFamily: "Outfit, sans-serif"
    fontSize: "clamp(3rem, 12vw, 10rem)"
    fontWeight: 400
    lineHeight: 0.9
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Outfit, sans-serif"
    fontSize: "3.75rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Outfit, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  lead:
    fontFamily: "Outfit, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 400
    lineHeight: 1.625
  body:
    fontFamily: "Outfit, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Outfit, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.43
  caption:
    fontFamily: "Outfit, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.1em"
rounded:
  hairline: "2px"
  sm: "0.25rem"
  panel: "1rem"
  pill: "9999px"
spacing:
  gutter: "1.5rem"
  gutter-lg: "3rem"
  section: "6rem"
  section-lg: "8rem"
  container: "1400px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "8px 16px"
  input-ask:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "44px"
  input-ask-large:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "56px"
  input-field:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    height: "36px"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.graphite}"
    typography: "{typography.label}"
    padding: "10px 12px"
  tab-selected:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "10px 12px"
  outcome-dot:
    backgroundColor: "{colors.answered}"
    rounded: "{rounded.pill}"
    size: "8px"
---

# Design System: FastRAG

## Overview

**Creative North Star: "The Proof Sheet"**

The website is a printer's proof: black ink set on warm paper, every claim laid down beside
its source. Nothing is decorated for its own sake. Structure comes from 1px rules, figure
captions and corner marks, the marks of a page someone means to check. The product's promise
is "cited or silent", and the surface keeps the same discipline: if something is shown, its
evidence is a click away, and when there is nothing to show the page says so plainly.

It is quiet and typographic. A single typeface carries everything from the ten-rem hero to
the eleven-pixel caption, so hierarchy comes from size, color weight and space rather than
from font changes. Pages are generous on the landing site and denser on working surfaces
(`/query`, `/docs`), but both share the same paper, ink and rules. Motion is reserved for a
few moments: the hero word that cycles through Indian scripts, sections rising into view, a
playhead moving along a chapter rail.

What it is not: the bento dashboard of soft-shadowed rounded cards that `/query` used to be,
and the dark slate-and-sky look of the internal `web/` console, which this system does not
cover.

**Key Characteristics:**
- Warm off-white paper and near-black ink; no brand accent.
- Green, amber and red appear only as answered, abstained and refused.
- One typeface (Outfit) for everything, with tabular figures for data.
- Flat surfaces divided by hairline rules; shadows only on things that float.
- Pills for things you press or type into; square or near-square edges for content.
- Figure-style framing: captions, corner ticks, faint grids.

## Colors

Ink on paper, with color held back for meaning.

### Primary
- **Proof Ink** (`ink`): text, primary buttons, selected tabs, score bars and timing bars.
  Pressing a primary button inverts it to paper-on-ink.

### Neutral
- **Warm Paper** (`paper`): the page background everywhere, and the fill of inputs.
- **Graphite** (`graphite`): secondary text, captions, metadata, inactive tabs. It is the only
  grey for text; never use a lighter grey for anything a visitor must read.
- **Vellum** (`vellum`): muted fills such as skeleton bars and track backgrounds.
- **Rule** (`rule`): the default border color for form controls and dividers drawn by
  component primitives.
- **Hairline** (`hairline`, ink at 10%): the 1px rules that divide sections, list rows and
  figure frames. Inner row rules drop to ink at 6%; emphasised outlines rise to 15–20%.
- **Sheet** (`sheet`): pure white, only for popovers and floating menus that sit above paper.

### Status
- **Answered Green** (`answered`, text in `answered-ink`): answered outcomes, cited tags.
- **Abstained Amber** (`abstained`, text in `abstained-ink`): abstentions and overrides.
- **Refused Red** (`refused`, text in `refused-ink`): refusals, blocked stages, errors.

### Named Rules
**The Status-Only Rule.** Color carries one meaning: how a run ended. Green, amber and red
never appear as decoration, section accents, link colors or illustration fills. If a hue does
not answer "what happened?", it is ink or graphite. Two established exceptions: the mic button
turns red while recording (a live state), and attachment icons use the conventional file-type
colors (red PDF, blue text, green data, violet markup) so a file is recognisable at a
glance.

**The Paper Rule.** The page is always Warm Paper. Sections do not switch to tinted or dark
bands to create rhythm; rules and space do that. (The one inverted band, How it works on the
landing page, is the exception rather than a pattern to repeat.)

## Typography

**Display Font:** Outfit (with sans-serif)
**Body Font:** Outfit (with sans-serif)
**Label/Mono Font:** Outfit; the `font-mono` and `font-display` utilities both resolve to it

**Character:** One geometric sans in a single regular weight, carrying everything. Scale and
the ink/graphite contrast do the work that a second face would do elsewhere.

### Hierarchy
- **Display** (400, `clamp(3rem, 12vw, 10rem)`, line-height 0.9): the landing hero only, "Ask
  anything in …", with the cycling script word set in bold.
- **Headline** (400, 2.25rem rising to 3.75rem from the `lg` breakpoint, line-height 1): section
  headings, often two lines with the second in graphite ("Query to Context / retrieved - not
  invented."). Page titles on working surfaces use 1.875rem to 3rem.
- **Title** (400, 1.25rem): headings of bands inside a working page (Answer, Timing, Evidence).
- **Lead** (400, 1.125rem, line-height 1.625): verdicts, answers and section introductions,
  held to 52–68ch.
- **Body** (400, 1rem, line-height 1.5): running text and list rows.
- **Label** (400, 0.875rem): navigation, buttons, tabs, metadata rows.
- **Caption** (400, 0.6875rem, letter-spacing 0.1em, uppercase): figure captions such as
  "FIG. 01 — LAUNCH FILM". Lowercase 11–12px captions label axes and ticks.

### Named Rules
**The One Face Rule.** Outfit is the only typeface. Hierarchy changes size, color or spacing,
never family, and headings stay at weight 400; only the hero's script word and status labels
use a heavier weight.

**The Tabular Rule.** Every number that can be compared (timings, scores, counts, ids) is set
with tabular figures (`tabular-nums`) so columns line up.

**The Whole-Word Rule.** Indic scripts are animated and broken by whole word only; splitting a
word by code unit breaks conjuncts and matras into dotted circles.

## Layout

Content sits in a centred container up to 1400px wide, with 1.5rem side padding that grows
to 3rem from the `lg` breakpoint. Landing sections breathe at 6rem of vertical padding (8rem
from `lg`); working pages use tighter bands of 1.5rem above and 2.5rem below each rule.

Section headers pair a heading on the left with a short paragraph or control on the right
at `lg`, bottom-aligned. Working pages use a main column plus a 22rem side column from `xl`
(1280px), collapsing to one column below it, with the most important side panel repeated in
the main flow on narrow screens rather than pushed to the bottom.

Prose is held to 65–75ch. Data views (waterfalls, chunk lists) run the full column width.
Horizontally scrolling rails replace grids for long sequences on phones, and no page may
scroll sideways at any width.

**The Measure Rule.** Text a visitor reads in full stays under 68ch, however wide the column.

## Elevation & Depth

The system is flat. Depth comes from rules, from the ink/graphite contrast and from space,
not from shadow. Content never sits on a raised card. Three things float, and only those
carry a shadow: the navigation bar once the page scrolls (it becomes a blurred, translucent
pill panel), popovers and menus, and the ask field, which takes a faint lift so it reads as
the place to start.

A 3% fractal-noise grain covers landing pages to give the paper a tooth. The hero and figure
frames add a faint grid at ink 5–10%, faded at the edges.

### Shadow Vocabulary
- **Float** (Tailwind `shadow-lg`): the scrolled navigation panel and popovers.
- **Lift** (Tailwind `shadow-sm`): the ask field and the play button over the demo poster.

### Named Rules
**The Flat Paper Rule.** If it does not float above the page, it has no shadow. Group content
with a rule and a heading, not a box.

## Shapes

Two shapes, with a clear split. Things you press or type into are pills: buttons, the ask
field, filter chips, the outcome dot, the citation markers in an answer. Content is square or
nearly so: figure frames, the timing bars and gate scale (2px corners), list rows, the demo
stage. Form fields from the component kit keep their small 0.25rem radius, and the floating
navigation panel uses 1rem.

Figures are framed by a single hairline with small L-shaped corner ticks, as on a proof.

**The Pill-or-Square Rule.** A rounded rectangle between 4px and 1rem is not a container
shape here. Interactive is a pill; content is square or 2px.

## Components

### Buttons
- **Shape:** full pill (`9999px`).
- **Primary:** ink fill, paper text, 8px × 16px. The navigation's call to action is 32px tall
  with 24px sides, tightening to 16px sides and an 11px label once the bar floats.
- **Hover / Focus:** primary fades to 90% ink; disabled drops to 35–50% opacity. Focus shows
  the ink ring.
- **Outline:** transparent with an ink 20% border that darkens to ink on hover. Used for
  secondary actions such as "Back to original".
- **Text links in prose:** ink with a 25% underline offset 4px, turning full ink on hover.

### Chips
- **Style:** pill, 1px border, 11–12px label. Neutral chips use ink 15–20%; status chips use
  the status color at 40% for the border and its ink shade for text ("cited 1").
- **Citation markers:** 20px circles with the number in tabular figures, inverting to ink on
  hover; they link to the numbered source list.

### Cards / Containers
- **Corner Style:** none. Bands are separated by a 1px hairline rule above a 1.25rem title.
- **Background:** the page paper; never a white or tinted panel.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Figure frame:** hairline border, corner ticks, a caption bar in Caption style, a faint
  edge-faded grid inside.

### Inputs / Fields
- **Ask field:** a 44px pill (56px on start screens) on paper at 80%, ink 15% border, a faint
  lift. The submit control is an ink circle with an arrow; while working it shows a spinner.
  Focus darkens the border to ink 40%.
- **Form fields:** the component kit's 36px fields with a `rule` border and 0.25rem radius;
  focus adds the ink ring.
- **Sliders:** native range inputs tinted ink (`accent-color`).

### Navigation
- **Style:** a full-width bar at rest that becomes a 1200px floating pill panel on scroll:
  paper at 80% with backdrop blur, hairline border, Float shadow, height dropping from 80px
  to 56px.
- **Links:** label size in ink 70%, going to ink on hover with an ink underline drawing in
  from the left.
- **Mobile:** a menu button opening a full panel of large links.

### Tabs (funnel steps)
- Label-size text in graphite, with the count beside it. The selected tab turns ink with a
  2px ink underline sitting on the row's hairline.

### Outcome verdict (signature)
- An 8px status dot, the outcome word in its status ink and weight 500, then one plain
  sentence in graphite: "Answered. 2 sources cited, in 4.87 s." It is the only place status
  color meets prose.

### Measured figures (signature)
- Timing waterfalls, score bars and the decision gate scale are drawn in ink on vellum
  tracks, with thresholds marked as 1px ink ticks and values in tabular figures. They show
  real measurements; nothing is plotted for ornament.

## Do's and Don'ts

### Do:
- **Do** divide content with 1px hairlines at ink 10% (6% for rows inside a list).
- **Do** set every comparable number in tabular figures, with its unit.
- **Do** reserve green, amber and red for answered, abstained and refused.
- **Do** frame showcase media as a figure: hairline frame, corner ticks, an uppercase caption.
- **Do** keep pills for controls and square or 2px edges for content.
- **Do** keep read-in-full text under 68ch.
- **Do** say plainly when there is nothing to show (no sources, a stage that did not run).

### Don't:
- **Don't** put content on soft-shadowed rounded cards or build bento grids of them.
- **Don't** introduce a second typeface, bold headings, or gradient text.
- **Don't** use status colors, or any other hue, as decoration or as a brand accent.
- **Don't** add colored side borders to callouts, list items or alerts.
- **Don't** animate Indic text letter by letter.
- **Don't** plot or display figures that are not real measurements from the product.
- **Don't** let any page scroll sideways on a phone.
