# Artwork Title Review Process

Instructions for an AI agent to review and suggest titles for artworks with bad titles (filenames, timestamps, etc.).

## Overview

This project has ~160 artworks with non-descriptive titles that need human-readable titles. The workflow:

1. **Triage** - Identify bad titles (already done)
2. **Suggest** - AI views images and suggests titles
3. **Review** - Human approves/edits via web app
4. **Repeat** - Until all bad titles are fixed

## Files

| File | Purpose |
|------|---------|
| `_scripts/title_review_status.json` | Tracking file with per-artwork status |
| `_scripts/triage_titles.py` | Re-scans artworks, updates tracking |
| `_scripts/title_reviewer/app.py` | Flask web app for human review |
| `_artworks/*.md` | Artwork files with frontmatter |

## Status Values

- `good` - Title is fine, no action needed
- `needs_review` - Bad title, needs a suggested title
- `has_suggestion` - Has `suggested_title` field, ready for web app review
- `completed` - Human approved via web app

## How to Suggest Titles

### 1. Get artworks needing suggestions

```python
import json
with open('_scripts/title_review_status.json', 'r') as f:
    data = json.load(f)

needs_review = [(k, v) for k, v in data['artworks'].items()
                if v.get('status') == 'needs_review']

# Get first N artworks
for filename, info in needs_review[:10]:
    print(f"{filename}: {info['title']}")
```

### 2. Get image paths

For each artwork file, read it and extract the `image:` field:

```bash
grep "^image:" _artworks/FILENAME.md
```

Image paths are relative to project root, e.g., `/assets/images/galleries/still-lifes/image.jpg`

### 3. View the image

Use the Read tool to view the image file. The actual file path is:
```
/Users/agude/Projects/hfgudeart/assets/images/galleries/{gallery}/{image-file}
```

### 4. Generate a descriptive title

Guidelines:
- **3-10 words** - Concise but descriptive
- **Title Case** - Capitalize major words
- **Descriptive** - What is depicted, not how it was made
- **No file extensions** - Never include .jpg, .png, etc.

Examples:
- Bad: `IMG_0042a.jpg`
- Good: `Connie Napping on Green Couch`

- Bad: `20140822_133020a.jpg`
- Good: `Gloved Hand on Saxophone`

### 5. Add suggested_title to artwork file

Edit the artwork markdown to add `suggested_title` after the `title` line:

```yaml
---
layout: artwork
title: "IMG_0042a.jpg"
suggested_title: "Connie Napping on Green Couch"
image: /assets/images/galleries/figure-paintings/connie-napping-painting.jpg
galleries:
  - figure-paintings
---
```

### 6. Update tracking file

Update the artwork's status in `_scripts/title_review_status.json`:

```python
import json

with open('_scripts/title_review_status.json', 'r') as f:
    data = json.load(f)

filename = "img-0042a-jpg.md"
suggested = "Connie Napping on Green Couch"

data['artworks'][filename]['status'] = 'has_suggestion'
data['artworks'][filename]['suggested_title'] = suggested
data['statistics']['needs_review'] -= 1
data['statistics']['has_suggestion'] += 1

with open('_scripts/title_review_status.json', 'w') as f:
    json.dump(data, f, indent=2)
```

## Batch Processing Script

Here's a complete script to process multiple artworks:

```python
import json
import re
from pathlib import Path

# Define suggestions (filename -> suggested title)
suggestions = {
    "img-0042a-jpg.md": "Connie Napping on Green Couch",
    "img-0051a-jpg.md": "Paper Lanterns in the Garden",
    # ... more suggestions
}

artworks_dir = Path("_artworks")

# Add suggested_title to each artwork file
for filename, suggested in suggestions.items():
    filepath = artworks_dir / filename
    content = filepath.read_text()

    # Insert suggested_title after title line
    new_content = re.sub(
        r'^(title: "[^"]*")\n',
        f'\\1\nsuggested_title: "{suggested}"\n',
        content,
        count=1,
        flags=re.MULTILINE
    )
    filepath.write_text(new_content)

# Update tracking file
with open("_scripts/title_review_status.json", "r") as f:
    data = json.load(f)

for filename, suggested in suggestions.items():
    if filename in data["artworks"]:
        data["artworks"][filename]["status"] = "has_suggestion"
        data["artworks"][filename]["suggested_title"] = suggested
        data["statistics"]["needs_review"] -= 1
        data["statistics"]["has_suggestion"] += 1

with open("_scripts/title_review_status.json", "w") as f:
    json.dump(data, f, indent=2)
```

## Running the Web App

After suggestions are added, the human reviews them:

```bash
uv run --with flask --with pyyaml python3 _scripts/title_reviewer/app.py
```

Then open http://localhost:5000

The web app:
- Shows the image and current bad title
- Displays suggested title in an editable field
- **Approve** - Saves title to artwork file, marks completed
- **Skip** - Moves to next without saving
- **Back** - Returns to previous

## Checking Progress

```bash
uv run python3 -c "
import json
with open('_scripts/title_review_status.json') as f:
    data = json.load(f)
print(json.dumps(data['statistics'], indent=2))
"
```

## Re-running Triage

If new artworks are added or you want to refresh the tracking:

```bash
uv run python3 _scripts/triage_titles.py
```

This preserves `completed` and `has_suggestion` statuses while detecting new bad titles.

## Tips for Good Titles

1. **Describe the subject** - "Portrait of Ash in Profile" not "Charcoal Drawing"
2. **Be specific** - "Still Life with Pink Bunny and Silver Teapot" not "Still Life"
3. **Use context clues** - Gallery name hints at subject matter
4. **Match existing style** - Look at good titles in the collection for reference
5. **For Cal Band details** - Describe what's visible (plume, uniform, instrument)
6. **For studies/sketches** - Include what's being studied ("Studies of Eyes", "Hand Studies")
