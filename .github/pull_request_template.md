## What and why

<!-- What this pull request changes, and why. Link the feature spec and tasks. -->

## Checks

- [ ] Backend: `pytest`, Ruff, pylint, mypy
- [ ] Frontend: `npm test`, Prettier, oxlint, `tsc -b`
- [ ] Quickstart sections for the stories touched

## Extraction eval (only if extraction changed)

<!--
GitHub doesn't give the API key to workflows for pull requests from forks, so the eval can't
run here (feature 003, research R7). If this changes backend/app/documents/extraction/** or
backend/evals/**, run it locally and paste report.md:

    docker compose exec backend python -m evals.extraction.generate
    docker compose exec backend python -m evals.extraction.run --model <model>

The "Extraction eval" workflow runs it again on main after merge.
-->

## Retrieval eval (only if the tax assistant's search changed)

<!--
The "Retrieval eval" workflow runs on pull requests that have the API key; pull requests from
forks don't, so it skips with a notice (feature 006, research R10). If this changes
backend/app/rag/** or backend/evals/retrieval/**, run it locally and paste report.md:

    docker compose exec backend python -m app.rag.build
    docker compose exec backend python -m evals.retrieval.run

It runs again on main after merge and fails below the pass marks in thresholds.yaml.
-->
