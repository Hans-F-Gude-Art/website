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

### Gallery System

Two-tier structure:
- **Hub pages** (`layout: default`): Category landing pages with inline Liquid that render gallery links
- **Gallery pages** (`layout: gallery`): Display artwork grids

### Collections

**Artworks** (`_artworks/*.md`): Single source of truth for artwork metadata. Each artwork specifies which galleries it belongs to via a `galleries` array, allowing the same artwork to appear in multiple galleries.

```yaml
---
title: "Artwork Title"
image: /assets/images/galleries/gallery-id/filename.jpg
galleries:
  - gallery-id-1
  - gallery-id-2
---
```

### Layouts

| Layout | Purpose |
|--------|---------|
| `default.html` | Base layout (also used by hub pages) |
| `gallery.html` | Filters `_artworks` collection by `gallery_id` from frontmatter |
| `artwork.html` | Single artwork display with full-size image |
| `page.html` | Minimal wrapper |
| `post.html` | Minimal wrapper |

### Data Files

- `_data/galleries/*.yml` - Per-gallery artwork slug lists (used by `gallery.html` to order artworks)
- `_data/*_galleries.yml` - Hub navigation data (which galleries appear under each hub)

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
