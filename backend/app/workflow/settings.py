"""Tunable values for the guided run (feature 007; research R4, R5).

WORKFLOW_MODEL and WORKFLOW_EFFORT come from the environment (app/settings.py), like 006's
answer model; the values here are fixed by the spec.
"""

# Each agent step gives its result, or its plain result, within this many seconds (FR-019), as
# 006's answers do.
STEP_SECONDS = 15.0

# The research agent may search at most this many times (research R4).
MAX_SEARCHES = 3
