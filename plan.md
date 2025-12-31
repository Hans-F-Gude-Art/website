# WIX to Jekyll Gallery Conversion Plan

This document tracks the conversion of HFGudeArt from WIX to Jekyll.

---

## Project Structure

```
hfgudeart/
├── scripts/
│   └── extract_gallery.py      # Image extraction & download script
├── _data/
│   ├── galleries/              # Individual gallery YAML files
│   │   ├── campus_drawings.yml
│   │   └── ...
│   ├── homepage_galleries.yml  # Homepage category thumbnails
│   └── uc_berkeley_galleries.yml
├── _layouts/
│   └── gallery.html            # Gallery page template
├── assets/images/galleries/    # Downloaded artwork images
└── *.md                        # Gallery & hub pages
```

---

## Using the Extraction Script

### Basic Usage
```bash
cd hfgudeart

# Dry run (preview what will be extracted)
python3 scripts/extract_gallery.py <html_file> <gallery-name> --dry-run

# Download images and generate YAML
python3 scripts/extract_gallery.py <html_file> <gallery-name> --output-dir . --download
```

### What the Script Does
1. Parses WIX HTML for `aria-label` attributes (artwork titles)
2. Extracts wixstatic.com URLs and strips `/v1/...` to get original quality
3. Slugifies titles to create meaningful filenames (e.g., "Sather Tower" → `sather-tower.jpg`)
4. Downloads images to `assets/images/galleries/<gallery-name>/`
5. Generates YAML to `_data/galleries/<gallery_name>.yml`

### Example
```bash
python3 scripts/extract_gallery.py \
  ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/landscapes-mt-diablo.html \
  landscapes-mt-diablo \
  --output-dir . \
  --download
```

This creates:
- `assets/images/galleries/landscapes-mt-diablo/*.jpg`
- `_data/galleries/landscapes_mt_diablo.yml`

---

## Completed Galleries ✓

| Gallery | Images | WIX Source |
|---------|--------|------------|
| campus-drawings | 25 | copy-of-berkeley-campus.html |
| uc-berkeley-campus | 11 | images-of-the-berkeley-campus.html |
| cal-marching-band | 9 | copy-of-cal-marching-band.html |
| cal-athletics | 17 | images-of-cal-sports.html |
| cal-rowing | 11 | copy-of-rowing-drawings.html |
| the-play | 9 | copy-of-the-play-drawings.html |

**Total: 82 images, ~215MB**

---

## Remaining Galleries

### Landscapes (4 galleries)
```bash
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/landscapes-mt-diablo.html landscapes-mt-diablo --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/landscapes-other.html landscapes-other --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/landscapes-outdoors.html landscapes-outdoors --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/landscapes-watercolor-g.html landscapes-watercolor --output-dir . --download
```

### Human Figure (4 galleries)
```bash
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/figures-figure-studies.html figure-studies --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/figures-life-drawing-class.html life-drawing --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/figures-paintings.html figure-paintings --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-figure-drawings.html figure-drawings --output-dir . --download
```

### Drawings (3 galleries)
```bash
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/drawings-finished-drawings.html finished-drawings --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/drawings-sketches-studies.html sketches-studies --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-select-charcoal-drawings.html charcoal-drawings --output-dir . --download
```

### Other (5 galleries)
```bash
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/still-lifes.html still-lifes --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/photographs.html photographs --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/emily.html emily --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-campus-drawings.html illustrations --output-dir . --download
python3 scripts/extract_gallery.py ../old/hfgudeart.wixsite.com_cleaned/hfgudeart/copy-of-watercolor-gouache.html watercolor-gouache --output-dir . --download
```

---

## Creating Gallery Pages

After extracting images, create a markdown file for each gallery:

```markdown
---
layout: gallery
title: Mt. Diablo Landscapes
subtitle: Paintings of Mount Diablo
gallery_data: landscapes_mt_diablo
---
```

The `gallery_data` value must match the YAML filename (without `.yml`, using underscores).

---

## Creating Hub Pages

Hub pages link to multiple galleries. Example `landscapes.md`:

```markdown
---
layout: default
title: Landscapes
---

# Landscape Artwork

<ul class="gallery-grid">
{% for item in site.data.landscapes_galleries %}
  <li>
    <a href="{{ item.url | relative_url }}">
      <img src="/assets/images/galleries/{{ item.image }}" alt="{{ item.title }}">
      <h2>{{ item.title }}</h2>
    </a>
  </li>
{% endfor %}
</ul>
```

Then create `_data/landscapes_galleries.yml`:
```yaml
- title: Mt. Diablo
  url: /landscapes-mt-diablo
  image: landscapes-mt-diablo/some-thumbnail.jpg

- title: Plein Air
  url: /landscapes-outdoors
  image: landscapes-outdoors/some-thumbnail.jpg
```

---

## Hub Pages to Create

| Hub Page | Data File | Sub-galleries |
|----------|-----------|---------------|
| `landscapes.md` | `landscapes_galleries.yml` | mt-diablo, other, outdoors, watercolor |
| `human-figure.md` | `figure_galleries.yml` | figure-studies, life-drawing, paintings, drawings |
| `drawings.md` | `drawings_galleries.yml` | finished, sketches-studies, charcoal |

---

## Testing

```bash
make build    # Build the site
make serve    # Local preview at http://localhost:4000
```

---

## Checklist

- [x] Create extraction script
- [x] Process UC Berkeley galleries (6) - 82 images
- [x] Process Landscapes galleries (4) - 94 images
- [x] Process Human Figure galleries (4) - 88 images
- [x] Process Drawings galleries (3) - 63 images
- [x] Process Other galleries (5) - 97 images
- [x] Create gallery markdown pages (22)
- [x] Create hub pages (3)
- [x] Update homepage_galleries.yml
- [ ] Final build test

**Total: 424 images across 22 galleries (832MB)**
