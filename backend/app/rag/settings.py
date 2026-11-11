"""Tunable values for the tax assistant (feature 006; research R4, R5, R7).

Kept in one place so the search-quality eval (T022) can set the cut-off it measured, with the
run that justified it.
"""

# How many passages a question is answered from (research R4).
TOP_K = 5

# The lowest cosine similarity (1 = same direction) at which the best passage still counts as
# relevant; below it the question is "not covered" and the AI is never asked (FR-006).
# PROVISIONAL until the eval sets it (task T022). The first check (2026-11-11) gave 0.70-0.72 for
# questions worded like the law (salary withholding, bank profit) and 0.60-0.63 for out-of-scope
# ones (sales tax, rental income). Everyday wording scores lower: "Is my medical allowance
# taxable?" 0.651, "How much tax do I owe?" 0.624, so 0.66 refused answerable questions. The
# model is the second filter (its not_covered flag), so the cut-off only has to drop questions
# clearly far from every passage; a borderline one goes to the model, which can still refuse.
RELEVANCE_CUTOFF = 0.62
