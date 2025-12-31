# HFGudeArt Site Architecture

This document describes the architecture of the Hans F. Gude art portfolio website, including the original WIX site structure, the Jekyll implementation, and the migration process.

## Table of Contents

1. [Overview](#overview)
2. [Jekyll Site Structure](#jekyll-site-structure)
3. [Original WIX Site Structure](#original-wix-site-structure)
4. [Gallery System](#gallery-system)
5. [Data Files](#data-files)
6. [Extraction Scripts](#extraction-scripts)
7. [File Mappings](#file-mappings)

---

## Overview

The site is an art portfolio showcasing the work of Hans F. Gude. It was originally built on WIX and has been migrated to Jekyll for easier maintenance. The site uses a two-tier gallery system:

- **Hub Pages**: Category landing pages that link to multiple related galleries
- **Gallery Pages**: Individual galleries displaying artwork images

---

## Jekyll Site Structure

### Directory Layout

```
hfgudeart/
├── _artworks/              # Collection: individual artwork markdown files
│   └── *.md                # One file per artwork image
├── _data/
│   ├── galleries/          # Gallery image data (YAML files)
│   │   └── *.yml           # One file per gallery
│   └── *_galleries.yml     # Hub navigation data files
├── _includes/              # Reusable HTML snippets
├── _layouts/
│   ├── artwork.html        # Single artwork display
│   ├── default.html        # Base layout
│   ├── gallery.html        # Gallery grid display
│   └── hub.html            # Category hub display
├── _sass/                  # Stylesheets
├── assets/                 # Static assets (CSS, JS)
├── images/
│   └── artworks/           # Artwork images organized by gallery
│       └── {gallery-id}/   # Folder per gallery
├── scripts/                # Python extraction/generation scripts
├── docs/                   # Documentation
└── *.md                    # Gallery and hub page files
```

### Key Configuration

**`_config.yml`** defines:
- Site metadata
- Collections (`artworks` with `output: true`)
- Default layouts and permalinks
- Build settings

### Layouts

#### `gallery.html`
Displays a grid of artwork thumbnails. Uses `gallery_id` from front matter to filter artworks.

```yaml
---
layout: gallery
title: Gallery Title
subtitle: Optional subtitle
gallery_id: gallery-slug
---
```

#### `hub.html`
Displays a grid of gallery thumbnails linking to sub-galleries. Uses `hub_id` to load navigation data.

```yaml
---
layout: hub
title: Hub Title
hub_id: hub-name
---
```

#### `artwork.html`
Displays a single artwork with full-size image, title, and navigation back to galleries.

### Collections

#### Artworks Collection (`_artworks/`)

Each artwork is a markdown file with this structure:

```yaml
---
title: "Artwork Title"
image: "gallery-id/filename.jpg"
galleries:
  - gallery-id-1
  - gallery-id-2    # Can belong to multiple galleries
---
```

The `galleries` array allows artworks to appear in multiple galleries (e.g., a watercolor landscape can appear in both "Landscapes" and "Select Watercolors").

---

## Original WIX Site Structure

### Source Files Location

```
old/hfgudeart.wixsite.com_cleaned/hfgudeart/
└── *.html    # 43 HTML files exported from WIX
```

### WIX Naming Convention

WIX uses a confusing naming pattern:
- **Main galleries**: Named descriptively (e.g., `landscapes-mt-diablo.html`)
- **Sub-galleries**: Prefixed with `copy-of-` (e.g., `copy-of-new-page.html` → Viking Village)

The `copy-of-` prefix does NOT indicate the content - you must check the `<title>` tag.

### Navigation Menu Structure

The WIX site has a consistent navigation menu on all pages:

| Menu Item | Target | Type | Dropdown Sub-item |
|-----------|--------|------|-------------------|
| Home | `../hfgudeart.html` | - | - |
| Artist Bio | `about2.html` | Page | - |
| UC Berkeley | `uc-berkeley-artworks.html` | Hub | The Play--Illustrations |
| Landscapes | `copy-of-home.html` | Hub | Painted Outdoors |
| Human Figure | `copy-of-landscapes.html` | Hub | Figure Drawings |
| Still Lifes | `still-lifes.html` | Gallery | - |
| Drawings | `copy-of-figures.html` | Hub | Perspective Studies |
| Illustrations & Cartoons | `copy-of-campus-drawings.html` | Gallery | - |
| Contact | `contact.html` | Page | - |
| By Medium | `copy-of-landscapes-1.html` | Hub | - |
| Emily | `emily.html` | Gallery | - |
| Photographs | `photographs.html` | Gallery | - |

### Hub Hierarchies

#### UC Berkeley Hub
```
UC Berkeley (uc-berkeley-artworks.html)
├── UC Berkeley Campus → images-of-the-berkeley-campus.html (Campus Paintings)
├── Campus Drawings → copy-of-berkeley-campus.html
├── Cal Athletics → cal-men-s-rowing.html [SUB-HUB]
│   ├── Men's Rowing--Paintings → images-of-cal-sports.html
│   └── Men's Rowing--Drawings → copy-of-cal-men-s-rowing.html
├── Oski Caricatures → copy-of-campus-paintings.html
└── Berkeley Band → images-of-cal-marching-band.html [SUB-HUB]
    ├── Painting Details → copy-of-cal-marching-band-1.html
    └── Preparatory Drawings → copy-of-cal-marching-band.html
```

#### Landscapes Hub
```
Landscapes (copy-of-home.html)
├── Mt. Diablo, California → landscapes-mt-diablo.html
├── Brynilsen's Viking Village → copy-of-new-page.html
├── Other Landscapes → landscapes-other.html
├── Watercolor and Gouache → landscapes-watercolor-g.html
├── Painted Outdoors → landscapes-outdoors.html
└── UC Berkeley → images-of-the-berkeley-campus.html (crosslink)
```

#### Human Figure Hub
```
Human Figure (copy-of-landscapes.html)
├── Paintings → figures-paintings.html
├── Life Drawing Classes → figures-life-drawing-class.html
└── Figure Drawings → copy-of-figures-1.html [SUB-HUB]
    ├── Heads & Faces → figures-figure-studies.html
    ├── Complete Figures → copy-of-figure-drawings.html
    └── Anatomical & Other Studies → copy-of-figure-drawings-complete-fi.html
```

#### Drawings Hub
```
Drawings (copy-of-figures.html)
├── Finished Drawings → drawings-finished-drawings.html
├── Sketches and Studies → drawings-sketches-studies.html
└── Perspective Studies → copy-of-sketches-studies.html
```

#### By Medium Hub
```
By Medium (copy-of-landscapes-1.html)
├── Oils → copy-of-other-landscapes.html (Select Oils)
├── Watercolor → copy-of-watercolor-gouache.html (Select Watercolors)
├── Gouache → copy-of-select-watercolors-gouache.html (Select Gouache)
├── Pen & Ink → copy-of-select-charcoal-drawings.html
├── Charcoal → copy-of-finished-drawings.html (Select Charcoal)
└── Pencil → copy-of-finished-drawings-1.html (Select Pencil)
```

---

## Gallery System

### How Galleries Work

1. **Gallery Page** (e.g., `landscapes-mt-diablo.md`):
   ```yaml
   ---
   layout: gallery
   title: Mt. Diablo
   gallery_id: landscapes-mt-diablo
   ---
   ```

2. **Gallery Data** (`_data/galleries/landscapes-mt-diablo.yml`):
   ```yaml
   - title: "Winter Storm Over Mt. Diablo"
     file: winter-storm-over-mt-diablo.jpg
   - title: "Another Painting"
     file: another-painting.jpg
   ```

3. **Artwork Files** (`_artworks/winter-storm-over-mt-diablo.md`):
   ```yaml
   ---
   title: "Winter Storm Over Mt. Diablo"
   image: "landscapes-mt-diablo/winter-storm-over-mt-diablo.jpg"
   galleries:
     - landscapes-mt-diablo
   ---
   ```

4. **Images** stored in `images/artworks/landscapes-mt-diablo/`

### Hub Navigation Data

Hub pages use data files to define which galleries to display:

**`_data/landscapes_galleries.yml`**:
```yaml
- title: Mt. Diablo
  url: /landscapes-mt-diablo
  image: landscapes-mt-diablo/winter-storm-over-mt-diablo.jpg

- title: Other Landscapes
  url: /landscapes-other
  image: landscapes-other/half-dome-yosemite.jpg
```

---

## Data Files

### Gallery Data (`_data/galleries/*.yml`)

Each gallery has a YAML file listing its images:

```yaml
# _data/galleries/landscapes-mt-diablo.yml
- title: "Winter Storm Over Mt. Diablo"
  file: winter-storm-over-mt-diablo.jpg

- title: "Mt. Diablo from Lime Ridge"
  file: mt-diablo-from-lime-ridge.jpg
```

### Hub Navigation (`_data/*_galleries.yml`)

| File | Hub Page | Description |
|------|----------|-------------|
| `homepage_galleries.yml` | Home | Main site navigation |
| `uc_berkeley_galleries.yml` | UC Berkeley | Cal-related galleries (5 items) |
| `landscapes_galleries.yml` | Landscapes | Landscape galleries (6 items) |
| `figure_galleries.yml` | Human Figure | Figure study galleries (3 items) |
| `drawings_galleries.yml` | Drawings | Drawing galleries (3 items) |
| `by_medium_galleries.yml` | By Medium | Medium-based galleries (6 items) |
| `cal_athletics_galleries.yml` | Cal Athletics | Rowing galleries (sub-hub, 2 items) |
| `cal_band_galleries.yml` | Cal Marching Band | Band galleries (sub-hub, 2 items) |
| `figure_drawings_galleries.yml` | Figure Drawings | Figure drawing sub-galleries (3 items) |

---

## Extraction Scripts

### `scripts/extract_gallery.py`

Extracts gallery images from WIX HTML files.

**Usage:**
```bash
uv run python3 scripts/extract_gallery.py <html_file> <gallery_id> [--download]
```

**What it does:**
1. Parses WIX HTML looking for `gallery-item-container` divs
2. Extracts image titles from `aria-label` attributes
3. Extracts image URLs from `data-image-info` JSON
4. Optionally downloads images to `images/artworks/{gallery_id}/`
5. Outputs YAML to `_data/galleries/{gallery_id}.yml`

**Example:**
```bash
uv run python3 scripts/extract_gallery.py \
  ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-new-page.html \
  viking-village \
  --download
```

### `scripts/generate_artworks.py`

Generates `_artworks/*.md` files from gallery data.

**Usage:**
```bash
uv run --with pyyaml python3 scripts/generate_artworks.py
```

**What it does:**
1. Reads all YAML files in `_data/galleries/`
2. For each image, creates or updates an artwork markdown file
3. Tracks which galleries each artwork belongs to
4. Handles artworks appearing in multiple galleries

---

## File Mappings

### WIX HTML to Jekyll Gallery ID

| WIX HTML File | Page Title | Jekyll Gallery ID |
|---------------|------------|-------------------|
| `images-of-the-berkeley-campus.html` | Campus Paintings | `berkeley-campus-paintings` |
| `copy-of-berkeley-campus.html` | Campus Drawings | `campus-drawings` |
| `cal-men-s-rowing.html` | Cal Athletics | (hub page) |
| `images-of-cal-sports.html` | Cal Athletics - Rowing Paintings | `cal-rowing` |
| `copy-of-cal-men-s-rowing.html` | Cal Athletics - Rowing Drawings | (no images extracted) |
| `images-of-cal-marching-band.html` | Cal Marching Band | `cal-marching-band` |
| `copy-of-cal-marching-band-1.html` | Cal Marching Band - Detail | `cal-band-detail` |
| `copy-of-cal-marching-band.html` | Cal Marching Band - Drawings | `cal-band-drawings` |
| `copy-of-campus-paintings.html` | Oski Caricatures | `oski-caricatures` |
| `copy-of-the-play-drawings.html` | The Play--Illustrations | `the-play-illustrations` |
| `copy-of-rowing-drawings.html` | Rowing - Boathouse Drawings | `rowing-boathouse` |
| `copy-of-rowing-drawings-1.html` | Rowing - Montlake Drawings | `rowing-montlake` |
| `landscapes-mt-diablo.html` | Mt. Diablo | `landscapes-mt-diablo` |
| `landscapes-other.html` | Other Landscapes | `landscapes-other` |
| `landscapes-outdoors.html` | Painted Outdoors | `landscapes-outdoors` |
| `landscapes-watercolor-g.html` | Watercolor & Gouache | `landscapes-watercolor` |
| `copy-of-new-page.html` | Brynilsen's Viking Village | `viking-village` |
| `figures-paintings.html` | Figure Paintings | `figure-paintings` |
| `figures-life-drawing-class.html` | Life Drawing Class | `life-drawing` |
| `figures-figure-studies.html` | Figure Drawings--Heads & Faces | `figure-heads-faces` |
| `copy-of-figure-drawings.html` | Figure Drawings--Complete Figures | `figure-complete` |
| `copy-of-figure-drawings-complete-fi.html` | Figure Drawings--Anatomical Studies | `figure-anatomical` |
| `drawings-finished-drawings.html` | Finished Drawings | `finished-drawings` |
| `drawings-sketches-studies.html` | Sketches & Studies | `sketches-studies` |
| `copy-of-sketches-studies.html` | Perspective Studies | `perspective-studies` |
| `still-lifes.html` | Still Lifes | `still-lifes` |
| `copy-of-campus-drawings.html` | Illustrations & Cartoons | `illustrations-cartoons` |
| `copy-of-other-landscapes.html` | Select Oils | `select-oils` |
| `copy-of-watercolor-gouache.html` | Select Watercolors | `select-watercolors` |
| `copy-of-select-watercolors-gouache.html` | Select Gouache | `select-gouache` |
| `copy-of-finished-drawings.html` | Select Charcoal Drawings | `select-charcoal` |
| `copy-of-finished-drawings-1.html` | Select Pencil Drawings | `pencil-drawings` |
| `copy-of-select-charcoal-drawings.html` | Select Pen & Ink Drawings | `pen-ink-drawings` |

### WIX Hub Pages (Not Galleries)

These are hub pages that don't contain gallery images directly:

| WIX HTML File | Hub Title | Links To |
|---------------|-----------|----------|
| `uc-berkeley-artworks.html` | UC Berkeley | 5 sub-galleries/hubs |
| `copy-of-home.html` | Landscapes | 6 sub-galleries |
| `copy-of-landscapes.html` | Human Figure | 3 sub-galleries + 1 sub-hub |
| `copy-of-figures.html` | Drawings | 3 sub-galleries |
| `copy-of-landscapes-1.html` | By Medium | 6 sub-galleries |
| `cal-men-s-rowing.html` | Cal Athletics | 2 sub-galleries |
| `images-of-cal-marching-band.html` | Cal Marching Band | 2 sub-galleries |
| `copy-of-figures-1.html` | Figure Drawings | 3 sub-galleries |

---

## Migration Notes

### Known Issues

1. **`copy-of-cal-men-s-rowing.html`** (Rowing Drawings) - No images extracted because the page doesn't use the standard `gallery-item-container` structure.

2. **Crosslinks** - Some galleries appear under multiple hubs in WIX (e.g., UC Berkeley landscapes). The Jekyll site handles this via the `galleries` array in artwork files.

3. **Similar Gallery Names** - Some galleries have similar but distinct content:
   - `charcoal-drawings` vs `select-charcoal` (separate galleries, some overlap)
   - `the-play` vs `the-play-illustrations` (different image sets)

### Image Storage

All artwork images are stored in:
```
images/artworks/{gallery-id}/{filename}.jpg
```

Images are downloaded at their original resolution from WIX's static CDN during extraction.

---

## Adding New Content

### To Add a New Gallery

1. Create gallery data file:
   ```yaml
   # _data/galleries/new-gallery.yml
   - title: "Artwork Title"
     file: artwork-filename.jpg
   ```

2. Create gallery page:
   ```yaml
   # new-gallery.md
   ---
   layout: gallery
   title: New Gallery
   gallery_id: new-gallery
   ---
   ```

3. Add images to `images/artworks/new-gallery/`

4. Regenerate artworks:
   ```bash
   uv run --with pyyaml python3 scripts/generate_artworks.py
   ```

5. Add to hub navigation (if applicable):
   ```yaml
   # _data/{hub}_galleries.yml
   - title: New Gallery
     url: /new-gallery
     image: new-gallery/cover-image.jpg
   ```

### To Add a New Hub

1. Create hub page:
   ```yaml
   # new-hub.md
   ---
   layout: hub
   title: New Hub
   hub_id: new-hub
   ---
   ```

2. Create hub navigation data:
   ```yaml
   # _data/new_hub_galleries.yml
   - title: Gallery One
     url: /gallery-one
     image: gallery-one/cover.jpg
   ```
