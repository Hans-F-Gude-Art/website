# AGENTS.md

This file provides guidance to LLM coding agents when working with code in
this repository. Both `CLAUDE.md` and `GEMINI.md` are symlinks to this file.

## Project Overview

Jekyll-based art portfolio website for Hans F. Gude, migrated from WIX. Uses Docker for development.

## Development Commands

All commands use Docker via Make:

```bash
make serve          # Start dev server at http://localhost:4000 (live reload)
make build          # Production build
make clean          # Clean build artifacts
make debug          # Interactive bash in container
make serve-drafts   # Serve with draft posts
```

First-time setup:
```bash
make image-build    # Build Docker image
make deps-lock      # Generate Gemfile.lock
```

Python scripts use `uv`:
```bash
uv run python3 _scripts/generate_artworks.py
uv run --with pyyaml python3 _scripts/extract_gallery.py <html_file> <gallery_id>
```

## Architecture

### Navigation Model

Three dimensions, ranked:
- **Subject** (primary): the homepage grid of subject tiles (UC Berkeley,
  Landscapes, Human Figure, Still Lifes, Drawings & Studies, Illustrations &
  Cartoons, Emily, Photographs). The header nav is only Home / Artist Bio /
  By Medium.
- **Medium** (secondary): `/by-medium/*` pages are *derived* — they filter
  the artworks collection on the `mediums` frontmatter tag.
- **Finish** (attribute): finished work vs. study is expressed by curated
  galleries under Drawings & Studies, not by navigation.

Project galleries (The Berkeley Band, Cal Rowing, Viking Village, The Play)
are single curated galleries that deliberately mix a finished work with its
preparatory studies, with narrative intro text in the page body.

### Gallery System

Two-tier structure:
- **Hub pages** (`layout: hub`): Category landing pages; render gallery tiles
  from the data file named by `galleries_data` frontmatter
- **Gallery pages** (`layout: gallery`): Display artwork grids in one of two
  modes: `gallery_id` (curated order from `_data/galleries/`) or `medium_id`
  (derived from artwork `mediums` tags, title order)

### Collections

**Artworks** (`_artworks/*.md`): Single source of truth for artwork metadata. Each artwork specifies which galleries it belongs to via a `galleries` array, allowing the same artwork to appear in multiple galleries. The `mediums` array feeds the derived By Medium pages (see `_scripts/tag_mediums.py`).

```yaml
---
title: "Artwork Title"
image: /assets/images/galleries/gallery-id/filename.jpg
galleries:
  - gallery-id-1
  - gallery-id-2
mediums:
  - oil
---
```

### Layouts

| Layout | Purpose |
|--------|---------|
| `default.html` | Base layout |
| `hub.html` | Gallery-tile grid from `galleries_data` data file |
| `gallery.html` | Artwork grid from `gallery_id` data file or `medium_id` tag query |
| `artwork.html` | Single artwork display with full-size image |
| `page.html` | Minimal wrapper |
| `post.html` | Minimal wrapper |

### Data Files

- `_data/galleries/*.yml` - Per-gallery artwork slug lists (used by `gallery.html` to order artworks)
- `_data/*_galleries.yml` - Hub navigation data (which galleries appear under each hub)

### Validation

`uv run python3 _scripts/validate_galleries.py --check-tags` must pass: every
slug in a gallery data file needs a matching artwork tagged with that gallery.

### Image Storage

Images stored in `assets/images/galleries/{gallery-id}/`. All `image` fields use absolute paths from site root (e.g., `/assets/images/galleries/...`). Use `relative_url` filter in templates since site is hosted at a subpath (`/website`).

## Commits

Use `git secure-commit` instead of `git commit`. Format:
```
Short imperative headline (50 chars)

Detailed body explaining *what* and *why*.

Changes:
- Specific change 1.
- Specific change 2.
```
