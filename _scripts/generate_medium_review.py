#!/usr/bin/env python3
"""Generate per-cluster manifests for the medium-tagging review swarm.

Groups untagged artworks by their first gallery, merging small clusters into
"misc". Each manifest includes reference works from the same gallery that
already have medium tags, so a reviewing agent can calibrate against known
examples of this artist's media.

Output: _reports/medium_review/<cluster>.yml

Usage:
    uv run python3 _scripts/generate_medium_review.py
"""

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT = ROOT / "_reports" / "medium_review"
MIN_CLUSTER = 6
MAX_REFERENCES = 4


def frontmatter(path: Path) -> dict:
    text = path.read_text()
    fields = {"slug": path.stem}
    m = re.search(r'^title: "?(.*?)"?$', text, re.M)
    fields["title"] = m.group(1) if m else path.stem
    m = re.search(r"^image: (.+)$", text, re.M)
    fields["image"] = m.group(1) if m else ""
    for key in ("galleries", "mediums"):
        m = re.search(rf"^{key}:\n((?:  - .+\n)*)", text, re.M)
        fields[key] = re.findall(r"  - (.+)", m.group(1)) if m else []
    return fields


def main() -> None:
    arts = [frontmatter(p) for p in sorted((ROOT / "_artworks").glob("*.md"))]
    untagged = [a for a in arts if not a["mediums"]]
    tagged_by_gallery = defaultdict(list)
    for a in arts:
        if a["mediums"]:
            for g in a["galleries"]:
                tagged_by_gallery[g].append(a)

    clusters = defaultdict(list)
    for a in untagged:
        clusters[a["galleries"][0] if a["galleries"] else "misc"].append(a)
    for name in [n for n, works in clusters.items() if len(works) < MIN_CLUSTER]:
        if name != "misc":
            clusters["misc"].extend(clusters.pop(name))

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.yml"):
        old.unlink()
    for name, works in sorted(clusters.items()):
        refs = tagged_by_gallery.get(name, [])[:MAX_REFERENCES]
        lines = [f"cluster: {name}", "references:"]
        for r in refs:
            lines += [f"  - slug: {r['slug']}",
                      f"    image: {r['image']}",
                      f"    mediums: [{', '.join(r['mediums'])}]"]
        if not refs:
            lines[-1] = "references: []"
        lines.append("works:")
        for w in works:
            lines += [f"  - slug: {w['slug']}",
                      f"    title: \"{w['title']}\"",
                      f"    image: {w['image']}"]
        (OUT / f"{name}.yml").write_text("\n".join(lines) + "\n")
        print(f"{name}: {len(works)} works, {len(refs)} references")
    print(f"\nmanifests in {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
