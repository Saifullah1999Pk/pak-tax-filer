# Data Model: Repo Foundations (001)

This feature stores no data and creates no tables (spec FR-014).

The only database change is enabling the `vector` extension, done by the first Alembic
migration (see [research.md](research.md), R3). The first tables arrive with feature 002
(taxpayer profile and auth).
