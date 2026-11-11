"""Tunable values for the tax assistant (feature 006; research R4, R5, R7).

Kept in one place so the search-quality eval (T022) can set the cut-off it measured, with the
run that justified it.
"""

# How many passages a question is answered from (research R4).
TOP_K = 5

# The lowest cosine similarity (1 = same direction) at which the best passage still counts as
# relevant; below it the question is "not covered" and the AI is never asked (FR-006).
# PROVISIONAL until the eval sets it (task T022). A first real check (2026-11-11, six questions)
# gave 0.70-0.72 for every in-scope question (salary withholding, bank profit, reconciliation,
# a company car) and 0.60-0.63 for out-of-scope ones (sales tax, rental income), so it sits
# between the two.
RELEVANCE_CUTOFF = 0.66
