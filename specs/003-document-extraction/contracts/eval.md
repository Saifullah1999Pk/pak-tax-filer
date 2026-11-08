# Contract: Extraction eval

## Generate the cases

```bash
docker compose exec backend python -m evals.extraction.generate
```

Writes 80 files plus `ground_truth.json` to `backend/evals/extraction/cases/` (git-ignored):
20 per type × {clean PDF, photo-like JPG}, at least 4 layouts per type. Same seed, same files.

## Run it

```bash
docker compose exec backend python -m evals.extraction.run --model gemini-3.8-flash
```

Needs `GEMINI_API_KEY` (free, from AI Studio). Sends one request per case, paced under the free
per-minute limit; if the day's limit is reached it stops and says so. Prints and writes
`backend/evals/extraction/report.md`:

| Measure | Bar |
|---|---|
| Fields correct, clean PDFs | ≥ 95% |
| Fields correct, photos | ≥ 90% |
| Wrong values marked `high` confidence | ≤ 2% |

Also per-field accuracy, per-layout accuracy and the token cost of the run. Exit code `0` if all
bars are met, `1` otherwise. A field is correct when its normalised value equals the ground
truth exactly (both "not found" counts as correct only if the ground truth is absent).
