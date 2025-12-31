# Extract Missing WIX Galleries

## Problem
WIX used "copy-of-" prefixes for sub-galleries, so our extraction script only grabbed top-level galleries. We're missing **18 galleries with ~330 images**.

---

## Missing Galleries

| WIX File | Gallery Name | Images | Parent Category |
|----------|--------------|--------|-----------------|
| `copy-of-new-page.html` | Brynilsen's Viking Village | 27 | Landscapes |
| `copy-of-other-landscapes.html` | Select Oils | 37 | Landscapes |
| `copy-of-cal-marching-band-1.html` | Cal Marching Band - Detail | 19 | Cal Marching Band |
| `copy-of-cal-marching-band.html` | Cal Marching Band - Drawings | 11 | Cal Marching Band |
| `copy-of-cal-men-s-rowing.html` | Cal Athletics - Rowing Drawings | 6 | Cal Rowing |
| `copy-of-rowing-drawings.html` | Rowing - Boathouse Drawings | 13 | Cal Rowing |
| `copy-of-rowing-drawings-1.html` | Rowing - Montlake Drawings | 18 | Cal Rowing |
| `copy-of-campus-paintings.html` | Oski Caricatures | 13 | UC Berkeley |
| `copy-of-figure-drawings.html` | Figure Drawings - Complete Figures | 27 | Human Figure |
| `copy-of-figure-drawings-complete-fi.html` | Figure Drawings - Anatomical Studies | 27 | Human Figure |
| `figures-figure-studies.html` | Figure Drawings - Heads & Faces | 27 | Human Figure |
| `copy-of-finished-drawings-1.html` | Select Pencil Drawings | 27 | Drawings |
| `copy-of-finished-drawings.html` | Select Charcoal Drawings | 20 | Drawings |
| `copy-of-select-charcoal-drawings.html` | Select Pen & Ink Drawings | 15 | Drawings |
| `copy-of-sketches-studies.html` | Perspective Studies | 20 | Drawings |
| `copy-of-watercolor-gouache.html` | Select Watercolors | 16 | Other |
| `copy-of-select-watercolors-gouache.html` | Select Gouache | 7 | Other |
| `copy-of-the-play-drawings.html` | The Play - Illustrations | 11 | UC Berkeley |

---

## Implementation Steps

### 1. Extract images from missing galleries
Use existing `scripts/extract_gallery.py` for each missing gallery:
```bash
uv run --with beautifulsoup4 --with requests --with pyyaml python3 scripts/extract_gallery.py \
  ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-new-page.html \
  viking-village
```

**New gallery slugs to create:**
- `viking-village`
- `select-oils`
- `cal-band-detail`
- `cal-band-drawings`
- `rowing-drawings`
- `rowing-boathouse`
- `rowing-montlake`
- `oski-caricatures`
- `figure-complete`
- `figure-anatomical`
- `figure-heads-faces`
- `pencil-drawings`
- `select-charcoal` (check overlap with existing charcoal-drawings)
- `pen-ink-drawings`
- `perspective-studies`
- `select-watercolors`
- `select-gouache`
- `the-play-illustrations` (check overlap with existing the-play)

### 2. Generate artwork markdown files
Run `scripts/generate_artworks.py` to create `_artworks/*.md` for new images.

### 3. Create gallery markdown pages
For each new gallery, create a page like:
```yaml
---
layout: gallery
title: Brynilsen's Viking Village
subtitle: Old Forge, New York
gallery_id: viking-village
---
```

### 4. Update hub navigation data files
Add new galleries to appropriate `_data/*_galleries.yml` files:
- `landscapes_galleries.yml` - add Viking Village, Select Oils
- `uc_berkeley_galleries.yml` - add Oski Caricatures, The Play Illustrations
- `figure_galleries.yml` - add Complete Figures, Anatomical Studies, Heads & Faces
- `drawings_galleries.yml` - add Pencil, Pen & Ink, Perspective Studies
- Create new hub data files if needed for sub-navigation

### 5. Check for duplicates
Some galleries may overlap with existing ones:
- `copy-of-finished-drawings.html` (Select Charcoal) vs `charcoal-drawings`
- `copy-of-the-play-drawings.html` (The Play Illustrations) vs `the-play`
- Compare image counts and content before creating duplicates

### 6. Update hub pages
If adding new sub-gallery levels, update hub pages like:
- `landscapes.md` - add Viking Village link
- `human-figure.md` - add sub-galleries for Figure Drawings
- May need to create intermediate hub pages for 3-level navigation

---

## Files to Create

| File | Purpose |
|------|---------|
| `assets/images/galleries/<new-gallery>/*.jpg` | Downloaded images |
| `_artworks/<new-artwork>.md` | Artwork collection entries |
| `<new-gallery>.md` | Gallery pages |
| `_data/*_galleries.yml` | Updated hub navigation |

---

## Hierarchy Structure (3 levels in some cases)

```
Human Figure (hub)
├── Figure Studies
├── Life Drawing
├── Figure Paintings
└── Figure Drawings (hub)
    ├── Complete Figures
    ├── Anatomical Studies
    └── Heads & Faces

Drawings (hub)
├── Finished Drawings
├── Sketches & Studies
├── Charcoal Drawings
├── Select Pencil Drawings
├── Select Pen & Ink Drawings
└── Perspective Studies

Landscapes (hub)
├── Mt. Diablo
├── Brynilsen's Viking Village  ← NEW
├── Other Landscapes
├── Select Oils  ← NEW (or merge with Other?)
├── Painted Outdoors
└── Watercolors

Cal Rowing (hub or sub-galleries?)
├── Rowing Paintings (existing)
├── Boathouse Drawings  ← NEW
└── Montlake Drawings  ← NEW
```

---

## Notes
- May need to decide if some "Select X" galleries should be merged with existing galleries or kept separate
- The 3-level navigation (Human Figure → Figure Drawings → Heads & Faces) may need a new hub page layout
- Some images may already exist in other galleries - the artworks collection handles this via multi-gallery assignment
