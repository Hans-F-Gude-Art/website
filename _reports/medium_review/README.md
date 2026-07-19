# Medium-tagging review swarm

Goal: propose `mediums:` tags for the artworks listed in the manifests here
(`*.yml`, one per gallery cluster), by looking at the images.

## Orchestration

1. Regenerate manifests if artworks changed since they were built:
   `uv run python3 _scripts/generate_medium_review.py`
2. Spawn one Sonnet subagent per manifest file (13 clusters, ~200 works
   total). Give each agent the prompt template below with its manifest path.
3. Each agent writes `proposals/<cluster>.yml`.
4. Apply high-confidence proposals:
   `uv run --with pyyaml python3 _scripts/apply_medium_proposals.py`
   Then re-run with `--threshold medium --dry-run` to print what a lower bar
   would add, and show the below-threshold list to the user for judgment.
5. Verify: `uv run python3 _scripts/validate_galleries.py --check-tags` and
   `make build`; spot-check `/by-medium/` page counts.

## Agent prompt template

> Read the manifest at `_reports/medium_review/<cluster>.yml`. It lists
> artworks needing medium identification, plus reference works by the same
> artist whose media are known — view the reference images first to calibrate
> how this artist's materials photograph.
>
> For each work in `works:`, view the image with the Read tool and identify
> the medium. Vocabulary (use one or more): oil, watercolor, gouache,
> charcoal, pencil, pen-ink, digital, photograph. Guidance: pencil has
> graphite sheen and fine gray line; charcoal is matte, darker, broader, often
> on toned paper with white highlights; watercolor is transparent washes
> (paper shows through); gouache is opaque, flat matte color; photographs of
> sculptures/scenes are `photograph` only. If a work is a photo *of* a
> painting or drawing in situ (e.g. hanging on a wall, artist at work),
> tag the artwork's own medium as photograph.
>
> Write `_reports/medium_review/proposals/<cluster>.yml` as a YAML list:
>
>     - slug: the-slug
>       mediums: [pencil]
>       confidence: high   # high = certain; medium = probable; low = guessing
>       notes: only for non-high confidence — what else it could be and why
>
> Every work in the manifest must appear in the output. Do not edit any other
> files.

## Notes

- `misc`, `oski-caricatures`, and `the-play` have no reference works; expect
  lower confidence there.
- Known hard pairs: pencil vs charcoal, watercolor vs gouache. Confidence
  should be at most medium when the distinction rests on subtle texture.
- Ask the user first whether any cluster can be bulk-tagged from memory
  (e.g. "all life drawings are charcoal") — that removes whole clusters.
