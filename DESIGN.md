---
name: Astana Walk
description: A pocket garden guide for a walk through Astana.
colors:
  ground: "#f3f6f3"
  surface: "#fff"
  text: "#25352f"
  muted: "#637068"
  accent: "#1b6e66"
  accent-hover: "#155b55"
  border: "#dfe6df"
  field-border: "#cbd6cd"
  hover: "#e4ebe5"
  selected-border: "#7ba497"
  map-ground: "#e9efe8"
  map-pin: "#4b6159"
  water-edge: "#a4c7c9"
  water-fill: "#c2dedf"
  park-edge: "#c7d9c0"
  park-fill: "#dce7d4"
typography:
  display:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "30px"
    fontWeight: 650
    lineHeight: 1.3
    letterSpacing: "-1px"
  headline:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "16px"
    fontWeight: 700
  title:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "16px"
    fontWeight: 650
    lineHeight: 1.45
  body:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "14px"
    fontWeight: 400
  body-card:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.75
  label:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "13px"
    fontWeight: 650
  metadata:
    fontFamily: "Manrope Variable, sans-serif"
    fontSize: "11px"
    fontWeight: 400
rounded:
  small: "6px"
  tooltip: "8px"
  location: "10px"
  field: "12px"
  summary: "16px"
  card: "22px"
  pill: "999px"
  circle: "50%"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  card: "20px"
  planner: "22px"
  workspace: "24px"
  page: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "48px"
    width: "100%"
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-text:
    backgroundColor: "transparent"
    textColor: "{colors.accent}"
    padding: "3px 0"
  preferences-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.field}"
    padding: "12px 13px"
    width: "100%"
  scenario-chip:
    backgroundColor: "transparent"
    textColor: "#627067"
    rounded: "{rounded.pill}"
    padding: "7px 8px"
  scenario-chip-selected:
    backgroundColor: "#eaf0eb"
    textColor: "{colors.text}"
  place-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.card}"
    padding: "20px"
  mobile-navigation:
    backgroundColor: "#e7ece6"
    rounded: "{rounded.pill}"
    padding: "4px"
  map-pin:
    backgroundColor: "{colors.map-pin}"
    textColor: "{colors.surface}"
    rounded: "50% 50% 50% 6px"
    size: "36px"
  map-pin-selected:
    backgroundColor: "{colors.accent}"
    size: "40px"
---

# Design System: Astana Walk

## Overview

**Creative North Star: "A pocket garden guide"**

Astana Walk is a calm botanical field guide for an urban walk. A light sage ground, white surfaces and restrained deep teal make the map and nearby places easy to read outdoors. Real map geometry and numbered recommendations are the visual material; familiar controls and progressive disclosure keep the interface approachable.

The Russian-first identity uses self-hosted Manrope with Cyrillic and Latin coverage. The original A/walking-path SVG and one Lucide outline icon family support the same quiet voice. Motion provides feedback through presses, disclosure and changed result positions; it does not stage a page entrance.

**Key Characteristics:**
- Sage ground, white panels and a limited teal accent.
- Readable Cyrillic typography with compact metadata.
- Real geography linked to numbered recommendation cards.
- Flat surfaces with small shadows only on map markers and overlays.

### Direction provenance

Taste Skill: `editorial-greeting`, seed `701388013`. Retain the centered content, tonal panels and restrained chromatic budget. The compact sans title replaces the optional 48px serif treatment. Manrope replaces Instrument Sans because Russian-first content needs Cyrillic. A real map supplies the product's visual material in place of the seed's generic chart and KPI rows.

Impeccable: code-led Operate, seed `2268e9889a738122`. Grounded directions considered were city walking guide, park wayfinding, museum directory, urban atlas, neighbourhood noticeboard, travel journal and botanical field guide. The seventh supplies sage ground, readable sans, low density and map-linked numbers. The type-specimen challenger contributed small-type legibility, not giant glyphs. The warm consumer-app challenger contributed touch-target considerations without replacing the botanical direction. Routine visual choices were delegated in the approved implementation scope.

### Source credits

- [Motion](https://github.com/motiondivision/motion), MIT; imported from `motion/react`.
- [Taste Skill](https://github.com/leonxlnx/taste-skill), MIT; app-screen direction and visual inspector.
- [Impeccable](https://github.com/pbakaus/impeccable), Apache-2.0; Operate mode, craft floor and finish review.
- [Manrope](https://github.com/sharanda/manrope), OFL-1.1; self-hosted through Fontsource.
- [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), ODbL 1.0; attributed on the map and in the footer.

## Colors

The palette is a pale garden ground with dark botanical ink and a deep teal action color. Frontmatter owns reusable values. Generated sidecar ramps are preview aids, not additional application tokens.

### Primary

**Deep Teal** (`accent`) identifies the primary action, active pin, selected card number, focus outline, links and positive schedule text. `accent-hover` darkens the primary action on hover.

### Secondary

**River Glass** (`water-edge`, `water-fill`) describes water geometry; **Park Sage** (`park-edge`, `park-fill`) describes park boundaries and fill. These are semantic map colors, not additional action accents.

### Neutral

**Garden Ground** (`ground`) and **White Surface** (`surface`) separate page and panels. **Botanical Ink** (`text`) and **Sage Ink** (`muted`) distinguish content and metadata. **Quiet Boundary** (`border`, `field-border`) supports dividers and editable fields. **Map Ground**, **Map Pin** and **Selected Edge** use their matching frontmatter keys. **Soft Hover** (`hover`) supplies shared button feedback except where a component overrides it.

**The Map Meaning Rule.** Water and park colors describe source geometry; teal identifies actions and selection.

## Typography

**Display and body font:** Manrope Variable with a generic sans-serif fallback, self-hosted with Cyrillic and Latin coverage. Weights in use range from regular to strong brand text (400–750).

### Hierarchy

- **Display:** `display` is the main heading. Tablet size becomes (27px); phone size (25px) with tracking (-0.8px).
- **Headline:** `headline` is the planner section title. Result titles use weight (650), reduce to (14px) on tablet and return to (16px) on phone.
- **Title:** `title` is the place name, wrapping long names.
- **Body:** `body` is the root and desktop intro role. Card reasons and activity prose use `body-card`; the final stylesheet override establishes (13px), superseding the earlier (12px) declaration.
- **Label:** field labels and time legends use `label`; filter controls, location select and checkbox rows also finish at (13px), with their own weights.
- **Metadata:** `metadata` covers categories, measurements, evidence and sources; supporting copy uses declared line-heights (1.6–1.8). Secondary controls also use (12px).
- **Brand:** wordmark (24px), weight (750), lighter word (450), tracking (-1px); phone size (22px).

**The Readable Numbers Rule.** Use tabular numerals for durations, distances, ranks and radius values. Keep compact metadata at the implemented minimum of 11px; do not shrink it to fit.

## Layout

Desktop uses a centered outer container (1164px) with horizontal padding (32px), leaving content up to (1100px). The workspace is a two-column grid with fractions (5:7), gap (24px), and top-aligned panels. It is not a literal twelve-column CSS grid. The map stays sticky (22px from the top) with default height (604px).

At viewport widths of at least (1600px), the outer container becomes (1264px), leaving content up to (1200px), and map height becomes (650px). At widths up to (1000px), side padding becomes (24px), columns (1:1.1), gap (16px), planner padding (18px), card padding (16px), and map height (570px).

At widths up to (700px), use a single column with side padding (18px), planner/card padding (20px), a list/map segmented switch, and a non-sticky map (480px high). The inactive result surface is hidden. Leaflet observes size changes and refits locations when shown. Header height reduces from (86px) to (70px); footer stacks vertically.

Use extracted spacing steps for repeated rhythm; local icon alignment includes optical offsets. Card content wraps rather than forcing horizontal overflow. Map footnotes are capped at (65ch); about text at (80ch).

## Elevation & Depth

Panels are flat, separated by sage/white tones and thin outlines. Depth is reserved for map pins and floating disclosures. Tooltips have no shadow. The map legend uses translucent white (`#ffffffee`) to preserve legibility.

### Shadow Vocabulary

- **Map pin:** `0 3px 8px #19362a20` anchors markers above geography.
- **Online-map disclosure:** `0 4px 12px #19362a15` lifts its expanded panel.
- **Coordinate popover:** `0 5px 18px #19362a18` separates the positioned editor.

**The Flat Panel Rule.** Main planner and recommendation cards stay shadow-free; shadows identify objects floating above the map or form.

## Shapes

Large panels use the card radius; fields and map overlays use the field radius. Summary panels use the summary radius. Actions, duration choices and chips use pills; utility buttons and numbered badges use circles. Keep outlines thin (1px); focus uses a visible teal outline (2px) with offset (4px).

The signature pin uses an asymmetric corner rotated (-45deg), with its number counter-rotated (45deg). Its white border (3px) remains legible over geography. Selection increases its size. The original A/walking-path SVG is the brand mark; no raster illustration or stock photography is used.

## Components

### Buttons

The primary search action is a full-width teal pill with a directional icon. Frontmatter specifies desktop; phone height is (50px). Hover darkens teal. Motion press scale is (0.985). Disabled controls have opacity (0.7) and waiting cursor; loading replaces the arrow with a white pulsing dot. Shared background/color transitions last (160ms). Text actions use accent text on transparent backgrounds. The place-heading button stays transparent on hover. All interactive controls retain the visible focus outline.

### Chips and duration selection

Scenario chips are outlined pills with pale selected fill and selected border (`#d1ddd4`). Scenario, interest and duration choices expose `aria-pressed`. Interests use pale idle pills and dark ink with white text when selected. Four duration choices sit in a sage pill track; selection is dark with white text. Duration buttons are (34px) high, increasing to (38px) on phone. Scenario chips have phone minimum height (36px).

### Cards and containers

Recommendation cards use a white surface, card radius and transparent (1px) border that becomes Selected Edge when active. Number badges are circles (28px), turning teal on selection. The heading button links to the map marker. Place name precedes category, estimated time, reason, a separately labeled activity idea and schedule status.

Evidence opens through a native disclosure with divider and plus/minus cue. Unknown facts, estimated durations and activity ideas stay labeled. Changed preferences show a visible stale-results notice and reduced result opacity (0.65). Empty states and loading skeletons reuse the same surfaces.

### Inputs and fields

The preference textarea is white with field border/radius, text (13px), line-height (1.6), minimum height (78px), maximum height (160px) and vertical resizing. Location uses a sage outlined row and native select. Coordinate fields open in a positioned white popover. Native checkboxes/ranges use teal accent color. All fields and disclosures retain visible focus.

### Navigation

The header carries the original wordmark, muted city label and about disclosure. The city label disappears on tablet. Phone navigation is a pill track with two equal list/map buttons; selected fill is white and minimum button height is (40px).

### Map and selected-place summary

Real OSM roads, parks and water frame numbered markers synchronized with cards, a start point and dashed search-radius circle. The circle is a search radius, not a computed walking route. Map attribution and online-map disclosure remain visible. White circular zoom/fit controls grow from (34px) to (40px) on phone. A white panel below the map summarizes the selected place.

### Motion and accessibility states

About/filter height and opacity animate over (200ms); cards animate position over (200ms). Selection pans only as needed to keep the marker inside the unobscured area, using top-left padding (50px, 85px) and bottom-right padding (60px, 170px). That pan lasts (250ms), disabled under reduced motion. Bounds fitting uses the same padding and is immediate. The loading dot pulses over (1s). `MotionConfig reducedMotion="user"` and the CSS reduced-motion query disable unnecessary motion; the query disables transitions and smooth scrolling as well. No page entrance sequence is used.

## Do's and Don'ts

### Do:

- **Do** preserve Cyrillic-capable, self-hosted Manrope and readable metadata.
- **Do** pair map ranks with the same numbered cards and expose selection in control semantics.
- **Do** retain source attribution and label uncertain facts, suggested activities and estimated times.
- **Do** keep focus visible and honor reduced-motion preferences.
- **Do** use the sage/white surface hierarchy and restrained teal actions.

### Don't:

- **Don't** turn the search-radius circle into an implied walking route.
- **Don't** introduce fabricated venues, decorative fake charts or confidence percentages.
- **Don't** add shadows to the main planner and recommendation cards.
- **Don't** replace the compact Cyrillic heading with a giant type specimen or Latin-only face.
- **Don't** hide stale results or missing-data states behind reassuring visual badges.
