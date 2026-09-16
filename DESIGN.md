---
name: PCB Schematic Library
description: A dimensioned parts catalog drawn on the drill template that made the pedal
colors:
  sheet: "#f4f2ee"
  sheet-2: "#ebe8e2"
  sheet-3: "#dfdbd3"
  ink: "#1c1f22"
  ink-2: "#4a4f55"
  ink-3: "#7a8087"
  rule: "#c9c4ba"
  rule-strong: "#8f8a80"
  coat: "#2f6b5e"
  coat-ink: "#f4f2ee"
  coat-2: "#244f46"
  coat-tint: "#e2ece8"
  warn: "#a6431d"
  focus: "#2f6b5e"
typography:
  display:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(30px, 4.5vw, 48px)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "clamp(28px, 4vw, 40px)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0.01em"
  title:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "0.06em"
  body:
    fontFamily: "Barlow, system-ui, -apple-system, Segoe UI, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
    fontFeature: "'tnum' 1"
  label:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0.12em"
  label-nav:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.1em"
  label-button:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    letterSpacing: "0.08em"
  label-chip:
    fontFamily: "Barlow Condensed, Arial Narrow, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.06em"
  mono:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
  mono-display:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "clamp(30px, 4.5vw, 44px)"
    fontWeight: 600
    lineHeight: 1.05
    letterSpacing: "0"
rounded:
  none: "0"
  field: "4px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "8px"
  cell: "10px"
  lg: "12px"
  xl: "16px"
  2xl: "20px"
  3xl: "24px"
  section: "28px"
  4xl: "32px"
  page-end: "48px"
  gutter: "clamp(16px, 3vw, 40px)"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    typography: "{typography.label-button}"
    rounded: "{rounded.field}"
    padding: "8px 14px"
  button-primary-hover:
    backgroundColor: "{colors.coat}"
    textColor: "{colors.coat-ink}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label-button}"
    rounded: "{rounded.field}"
    padding: "8px 14px"
  button-ghost-hover:
    backgroundColor: "{colors.sheet-2}"
    textColor: "{colors.ink}"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.label-chip}"
    rounded: "{rounded.pill}"
    padding: "3px 10px"
  chip-selected:
    backgroundColor: "{colors.coat}"
    textColor: "{colors.coat-ink}"
  input-search:
    backgroundColor: "{colors.sheet-2}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.field}"
    padding: "0 12px"
    height: "40px"
  input-search-focus:
    backgroundColor: "{colors.sheet}"
  nav-link:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    typography: "{typography.label-nav}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
  nav-link-active:
    textColor: "{colors.ink}"
  table-header:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
  table-cell:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "6px 10px"
  table-row-hover:
    backgroundColor: "{colors.sheet-2}"
---

# Design System: PCB Schematic Library

## Overview

**Creative North Star: "The Faceplate and the Drill Template"**

Two physical objects supply the whole visual vocabulary. The first is the finished pedal enclosure: a powder-coated box with screen-printed condensed capitals and knob, LED and footswitch positions drilled into it. The second is the paper drill template that made it: hairline rules, mono dimensions, and drafting white under workshop light. The screen sits between them. Page backgrounds are the drafting sheet, text is ink, separation is a hairline, every heading below the page title is a screen-printed label, and the one color on the page is the enclosure's coat.

Density is the point. The build has no hero, no cards, no illustrations, no icons and no motion. Lists are dimensioned tables with sticky column headers; filters are screen-printed toggle chips; page headers are title blocks. The signature element is the faceplate glyph, an SVG drawn from each circuit's real enclosure footprint and control list, rendered at 30px in table rows and 250px in the circuit page header using the same drawing. It is the only place the accent appears as a fill rather than a hairline.

The world is fully in scope: every route in the app (index, circuit, parts index, part detail, originals) and the shared layout speak it. There is no legacy surface to reconcile. The direction contract in `app/src/app.html` asked for crosshair centers on the template; the build draws pointer ticks on knobs instead and no crosshairs anywhere. The build wins.

**Key Characteristics:**
- Drafting-white sheet, near-black ink, three neutral steps each, and one surf-green coat.
- Barlow Condensed caps for every label and heading; Barlow for prose; the system monospace for anything that came off a datasheet.
- Separation by 1px hairline only. No zebra striping, no filled panels, no shadows at rest.
- Sticky title block and sticky table headers on the same sheet color as the page.
- Light by default; dark follows `prefers-color-scheme` with every token remapped, nothing else changing.
- Instant state changes. No transitions or animations exist.

## Colors

Two neutral ramps (sheet and ink), two hairline weights, one powder-coat accent with its own ink, and one warning hue reserved for stock status.

### Primary
- **Surf Green Coat** (`coat`): the enclosure fill of the faceplate glyph, the selected chip background, the active nav underline, the button hover background, and the focused input border. It is the only chromatic accent. `coat-ink` is what gets printed on it (the sheet white in light mode, a near-black `#0f1a17` in dark mode). `coat-2` is the darker edge stroke around the glyph shell. `coat-tint` is a pale wash used only for the 3px focus halo on text inputs.

### Neutral
- **Drafting Sheet** (`sheet`, `sheet-2`, `sheet-3`): page background, sticky header background and table header background are all `sheet`; `sheet-2` is the resting search field, the hovered table row and the ghost button hover; `sheet-3` is the glyph shell fill when a circuit's controls are unknown.
- **Ink** (`ink`, `ink-2`, `ink-3`): body text and primary button fill are `ink`; labels, table headers, resting nav links, BOM notes and ref designators are `ink-2`; subtitles, counts, lede text, footer text and every `.dim` span are `ink-3`.
- **Hairline** (`rule`) and **Structural Hairline** (`rule-strong`): `rule` separates table rows, list items, the facet rail and the footer; `rule-strong` closes the title block, underlines table column headers, closes the circuit plate, underlines section headings on the parts index, and outlines chips, inputs and selects at rest.
- **Warn** (`warn`): a burnt orange used for one thing, out-of-stock text. It never fills a surface.
- **Focus** (`focus`): the 2px `:focus-visible` outline. Equal to `coat` in light mode and a brighter `#5fb3a0` in dark mode so it clears the dark sheet.

### Dark mode
Dark is a full remap under `@media (prefers-color-scheme: dark)`, opted out by a `[data-theme='light']` attribute on the root that nothing in the build currently sets. The `theme-color` meta is the dark sheet.

| token | light | dark |
|---|---|---|
| sheet / sheet-2 / sheet-3 | #f4f2ee / #ebe8e2 / #dfdbd3 | #1c1f22 / #23272b / #2c3136 |
| ink / ink-2 / ink-3 | #1c1f22 / #4a4f55 / #7a8087 | #eef0ee / #c3c8c5 / #8f979a |
| rule / rule-strong | #c9c4ba / #8f8a80 | #3a4046 / #5b636a |
| coat / coat-ink / coat-2 / coat-tint | #2f6b5e / #f4f2ee / #244f46 / #e2ece8 | #3f8a79 / #0f1a17 / #2f6b5e / #24352f |
| warn / focus | #a6431d / #2f6b5e | #e0764c / #5fb3a0 |

### Named Rules
**The One Coat Rule.** `coat` is the only saturated color on any screen and it marks exactly two things: the enclosure itself (glyph fill) and the current selection (pressed chip, active nav, hovered button, focused field). If a new element is neither an enclosure nor a selection, it is a neutral.

**The Hairline Rule.** Regions are separated by a 1px line, never by a filled panel or a tint. `rule` for rows and soft edges, `rule-strong` for structural edges (header, plate, column heads, section underlines). Table rows are never striped; the comment in `app.css` says "no zebra" and the build honors it.

**The Warn Is Text Rule.** `warn` colors a short uppercase label ("out", "out of stock") and nothing else. It is not a background, a border or an icon.

## Typography

**Display Font:** Barlow Condensed (with Arial Narrow), self-hosted at 500, 600 and 700
**Body Font:** Barlow (with system-ui), self-hosted at 400, 500 and 600
**Label/Mono Font:** the platform monospace stack (ui-monospace, SF Mono, Menlo, Consolas)

**Character:** Condensed capitals do the work that screen-printing does on an enclosure: short, tracked, and small. The wider Barlow carries prose at 15px. Mono is reserved for values that a builder would read off a sheet: enclosure codes, SKUs, prices, counts, ref designators, part values, document versions.

### Hierarchy
- **Display** (600, `clamp(30px, 4.5vw, 48px)`, 1.05, 0.01em): the circuit name in the circuit page title block. A subtitle rides inline at weight 500 in `ink-2` with a 0.3em gap. Uses `text-wrap: balance`.
- **Headline** (600, `clamp(28px, 4vw, 40px)`, 1.05): the h1 on the parts index and originals pages.
- **Mono Display** (mono, 600, `clamp(30px, 4.5vw, 44px)`, 0 tracking): the part value on a part detail page, because a part number is data, not a name.
- **Title** (700, 20px, 1.1, 0.06em, uppercase): the brand name in the title block. Drops to 17px under 860px.
- **Body** (400, 15px, 1.45, tabular numerals globally): all prose, table cells, spec values. Prose blocks cap at 70 to 72ch; the footer at 80ch; the empty state at 60ch.
- **Label** (600, 12px, 0.12em, uppercase, `ink-2`): every h2 on every page, every `dt`, the "Sort" and "Filter" prompts, the glyph caption. `.label.strong` switches the color to `ink`. This is the only heading style below h1.
- **Label Nav** (600, 14px, 0.1em, uppercase): section nav links. 13px under 860px.
- **Label Button** (600, 14px, 0.08em, uppercase): all buttons.
- **Label Chip** (600, 13px, 0.06em, uppercase, 1.3): facet chips and applied-filter chips.
- **Mono** (400, 13px): inline data values. Smaller mono sizes in use: 11px chip counts, 11px doc version, 11.5px actives list under a circuit name, 10px out-of-stock tag.
- **Column Header** (600, 12px, 0.1em, uppercase, `ink-2`): `th` in every table; BOM group headers use the same style at 13px.
- **Fine print** (12px to 12.5px, `ink-3`): brand subline, part counts, schematic captions, footer at 13px.

### Named Rules
**The Screen-Print Rule.** Below the page h1 there is no size hierarchy, only the 12px tracked-caps label. A section heading and a definition-list term are the same element. Do not introduce an intermediate 18px or 24px heading; the world does not print one.

**The Mono Is Data Rule.** Monospace marks a value that was read off a vendor sheet or a datasheet: enclosure code, SKU, price, count, designator, part value, version. Names, categories, vendors and prose are never mono. The part detail page sets its h1 in mono for exactly this reason.

**The Tabular Rule.** `font-feature-settings: 'tnum' 1` is set on `body`; numeric columns are additionally right-aligned with `.n`. Numbers line up whether or not they are mono.

## Layout

The page is one full-bleed sheet with a horizontal gutter of `clamp(16px, 3vw, 40px)`. Content pages (circuit, parts, originals, part detail) pad `24px gutter 48px` and cap at 1180px, left-aligned, not centered. The index page has no cap: it is a two-column grid of a 260px facet rail and a fluid results column.

**Title block.** The sticky header (`top: 0`, `z-index: 5`, `sheet` background, `rule-strong` bottom edge) is a three-area grid, `brand | search | nav`, padded `12px gutter`, with the search form centered and capped at 720px. Under 860px it reflows to two rows, `brand nav` over a full-width `search`, drops the brand subline and the search button, and tightens to `10px 16px`.

**Facet rail.** Sticky at `top: 65px` (the measured height of the title block; there is no shared token for it) with `max-height: calc(100dvh - 65px)` and its own scroll, a `rule` right edge, `20px` vertical rhythm between facet groups and `6px` chip gaps. Under 1000px it becomes a static wrapping row with a `rule` bottom edge and `8px 24px` gaps.

**Circuit plate.** The circuit header is an `auto 1fr` grid, glyph left and title right, `32px gutter` gap, closed by a `rule-strong` line. Under 760px it stacks to one column and the glyph turns into a horizontal row with its caption.

**Tables.** `.sheet-table` is `border-collapse`, 100% wide, wrapped in an `overflow-x: auto` div; the circuit table sets `min-width: 720px` and scrolls rather than wrapping. Column headers are sticky at `top: 0` on the `sheet` background at `z-index: 1`. Cells pad `6px 10px`, headers `8px 10px`. Numeric columns are right-aligned. Category and BOM columns hide under 860px; on the circuit BOM the Normalized and Notes columns hide under 760px; the originals category column hides under 700px.

**Grids of items.** Sibling circuits use `repeat(auto-fill, minmax(280px, 1fr))` with `6px 24px` gaps; the parts index uses `minmax(240px, 1fr)` with `0 24px`; the circuit spec list uses `repeat(auto-fit, minmax(150px, max-content))` with `12px 32px`. Items in these grids are hairline-separated rows, not tiles.

**Rhythm.** Observed steps: 4, 6, 8, 10, 12, 16, 20, 24, 28, 32, 48. Sections start with `margin-top: 28px`; section headings sit `10px` above their content (8px on the index facets, 6px on the parts index). Buttons and chips gap at 8px and 6px respectively.

**Breakpoints in use** (there is no shared scale): 1000px (facet rail collapses), 860px (title block reflow, circuit table columns), 760px (circuit plate stacks, BOM columns), 700px (originals category column).

## Elevation & Depth

Flat. The build ships exactly one `box-shadow`, the `0 0 0 3px var(--coat-tint)` halo on a focused text input, and it is a ring, not a lift. `app.css` declares a `--shadow` token in both modes but no rule consumes it, so it is not part of the system. Depth is conveyed by stickiness and hairlines: the title block and table headers stay on the same `sheet` color as the page and are distinguished only by the `rule-strong` line beneath them. Row hover is a tint to `sheet-2`, not a raise. The faceplate glyph gets its depth from a darker `coat-2` stroke around the `coat` fill.

### Named Rules
**The Flat Sheet Rule.** Nothing lifts off the page. If a new surface needs to be distinguished from the sheet, give it a hairline, a `sheet-2` tint, or make it sticky; never a shadow.

**The Focus Ring Rule.** Keyboard focus is a 2px `focus` outline offset 2px on everything except text inputs, which swap the outline for a `coat` border plus the 3px `coat-tint` halo and brighten from `sheet-2` to `sheet`.

## Shapes

Square by default. Tables, sections, the title block, list rows and the footer have no radius. Fields, buttons and the sort select share a single small radius (`4px`, `--radius`). Chips are full pills (`999px`), the one round shape, so that a toggle reads as a printed label rather than a button. The faceplate glyph's shell corner is proportional to the enclosure, `rx = width × 0.06` in the SVG's mm coordinate space, so a 1590A and a 1590BB round differently at the same pixel size.

Borders are always 1px. Chips, inputs and selects use `rule-strong`; buttons use their own fill color as the border so primary and ghost share an outline. Links have no underline at rest and gain one on hover at a 2px offset; the exception is normalized part values in a BOM, which are underlined at rest in `rule-strong` with a 3px offset to mark them as cross-reference links.

## Components

### Buttons
Two variants, both condensed caps, both `8px 14px`, both `4px` radius, both instant on hover.
- **Primary** (`.btn`): `ink` fill and border, `sheet` text. Hover inverts to `coat` fill and border with `coat-ink` text. Used for Search and "Buy the PCB at [vendor]".
- **Ghost** (`.btn.ghost`): transparent fill, `ink` text and border. Hover fills `sheet-2`. Used for build document links, extra docs, Copy as TSV and "Show N more".
- **Disabled**: opacity 0.45, `not-allowed` cursor.
- **Link-as-button** (`.linkish`): a reset `<button>` that looks like inline text and underlines on hover, used for the "Based on" cell so it can set a filter instead of navigating.

### Chips
Screen-printed toggle labels.
- **Style:** transparent, `1px solid rule-strong`, `999px` pill, `3px 10px`, Label Chip type, `6px` gap to an optional mono count at 11px and 0.8 opacity.
- **Hover:** border darkens to `ink`. No fill change.
- **Selected** (`[aria-pressed='true']` or `.on`): `coat` fill and border, `coat-ink` text. Facet chips are `<button aria-pressed>`; the "In stock only" chip is a `<label>` wrapping a visually hidden checkbox and uses `.on`.
- **Applied filters** render as selected chips with a trailing ×; "Clear all" is an unselected chip.

### Tables
The dimensioned sheet (`.sheet-table`) is the primary list component and appears on the index, part detail, originals and circuit BOM.
- **Header:** Column Header type, `rule-strong` bottom edge, sticky, `sheet` background, `nowrap`.
- **Cells:** `6px 10px`, `rule` bottom edge, middle-aligned. Whole row tints to `sheet-2` on hover.
- **Numeric** (`.n`): right-aligned, tabular; usually also `.mono`.
- **Circuit row anatomy:** 30px faceplate glyph in a 40px column with no right padding, then name at weight 600 with an `ink-3` subtitle inline and an 11.5px mono list of active parts beneath, then Based on (max 26ch), Category, Vendor, Box (mono), Knobs, Price (with a 10px `warn` "out" tag when out of stock), BOM count. Missing values print an `ink-3` em dash.
- **BOM grouping:** each part category is its own `<tbody>` led by a `th[scope=rowgroup]` group row at 13px caps with a `rule-strong` edge and `14px 10px 6px` padding, explicitly `position: static` so it scrolls under the sticky column header. Ref column is 7ch in `ink-2`; Value is weight 600; Notes are `ink-2`.
- **Paging:** the circuit table shows 100 rows and a ghost button that appends 200 more.
- **Empty state:** an `ink-2` paragraph inside the table wrap, `32px 10px`, max 60ch.

### Inputs / Fields
- **Style:** `sheet-2` fill, `1px solid rule-strong`, `4px` radius, `0 12px` padding, 40px tall in the title block and 38px on page-level filters. Inherit body font.
- **Focus:** outline removed; border to `coat`, fill to `sheet`, `0 0 0 3px coat-tint` halo.
- **Select:** the sort control matches the input border and radius at `4px 8px` on `sheet`, and is disabled while a text query is active.

### Navigation
Three section links in the title block set in Label Nav, `8px 10px`, `ink-2` at rest with a transparent 2px bottom border. Hover goes to `ink` with no underline. The current section (`aria-current="page"`) is `ink` with a `coat` bottom border. "Circuits" is current on both the index and any circuit page.

### Faceplate Glyph
The signature component (`Faceplate.svelte`). An SVG whose `viewBox` is the enclosure's real footprint in millimetres (a table of twelve Hammond sizes; unknown codes fall back to 60 × 112, the 1590B), so proportions are true across sizes. Knobs are laid out in rows the way builders drill them (1 to 3 in one row, 4 as 2+2, 5 as 3+2, 6 as 3+3, 7 as 4+3, 8 as 4+4, then rows of four), the top 16% and bottom 42% of the height are reserved, an LED sits at 66% and the footswitch at 84%. Every stroke is scaled by `--sc = 1/scale` so hairlines stay 1px to 1.2px on screen regardless of rendered size.
- **Sizes in use:** 30px in the circuit table, 26px in the sibling list, 250px in the circuit page header (with `labels` on, which prints each control name under its knob in condensed caps, sized to fit the knob's cell and never below 4.2 user units).
- **Color:** `coat` shell with a `coat-2` stroke; knobs, pointers, LED, footswitch and printed labels in `coat-ink`. When the controls list is empty the shell is `sheet-3` with a `rule-strong` stroke and a single horizontal `rule-strong` dash, so "unknown" reads as a blank template rather than an empty pedal.
- **Accessibility:** `role="img"` with an `aria-label` naming the enclosure and control count, or the passed title.
- **Rule:** the glyph is information, not ornament. Do not decorate it, color knobs individually, or render it at sizes where the pointer ticks cannot resolve.

### Title Block (page header)
Content pages open with an h1 preceded by a Label line (breadcrumb or vendor · SKU) and followed by an `ink-2` lede capped at 70ch, then optionally a 460px-wide filter field. The circuit page's title block is the plate described in Layout, with a `dl.specs` grid of Label terms over body values and a wrapping row of buttons.

### Schematic image
Redrawn KiCad SVGs and cached vendor schematic pages render inside a `rule` hairline on a literal `white` background regardless of theme, capped at 80dvh. This is the one non-token color in the build and is deliberate: the schematic is a foreign document, not a surface of this world.

## Do's and Don'ts

### Do:
- **Do** set every heading below the page h1 as a 12px tracked-caps `.label` (`.label.strong` for `ink`); there is no other subheading style.
- **Do** separate rows, sections and rails with a 1px `rule` and structural edges with `rule-strong`; never with a fill.
- **Do** put any value that came off a datasheet or vendor sheet in `.mono`, and right-align numbers with `.n`.
- **Do** build any new list as a `.sheet-table` with sticky column headers, or as a hairline-separated `auto-fill` grid; reuse the title-block header pattern above it.
- **Do** render the faceplate glyph from real `enclosure` and `controls` data at 26 to 30px in rows and 250px in a header; pass `labels` only at the large size.
- **Do** use `coat` for selection and enclosure fill only, and pull every color from the custom properties so dark mode follows for free.
- **Do** keep hover and state changes instant; the build has no transitions and the reduced-motion block is already in place.
- **Do** use `4px` on fields and buttons and `999px` on chips; leave everything else square.

### Don't:
- **Don't** add hero sections, cards, tiles, or bordered panels; the world has none and the sheet is the only surface.
- **Don't** stripe table rows or tint alternate rows; hover tint to `sheet-2` is the only row state.
- **Don't** add shadows. The declared `--shadow` token is unused and should stay unused; the only ring is the input focus halo.
- **Don't** introduce a second accent, gradients, or colored category badges; `warn` is text-only and reserved for stock status.
- **Don't** add icons, glyph fonts, or decorative SVG. The faceplate is data; nothing else is drawn.
- **Don't** hardcode `white`, `black` or hex values in components (the schematic image background is the one deliberate exception).
- **Don't** invent an intermediate heading size, a serif, or a system display face; the type system is Barlow Condensed caps, Barlow body, platform mono.
- **Don't** shrink the circuit table below its `720px` minimum to avoid horizontal scroll; hide columns at 860px as the build does instead.
