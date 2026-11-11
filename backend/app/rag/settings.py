"""Tunable values for the tax assistant (feature 006; research R4, R5, R7).

Kept in one place so the search-quality eval (T022) can set the cut-off it measured, with the
run that justified it.
"""

# How many passages a question is answered from (research R4).
TOP_K = 5

# The lowest cosine similarity (1 = same direction) at which the best passage still counts as
# relevant; below it the question is "not covered" and the AI is never asked (FR-006).
# Set by the retrieval eval (task T022, 2026-11-11; evals/retrieval/report-cutoff-0.66.md):
# 40 questions in everyday wording found the expected passage for 30 of 30, but in- and
# out-of-corpus top scores overlap (in 0.585-0.755, out 0.531-0.695). Anywhere in 0.659-0.666
# gets the most right; 0.66 is the low end, giving hit@5 0.93 and a refusal rate of 0.90 (the
# proposed pass marks: 0.80, 0.90). The price: answerable questions scoring lower are refused
# ("Does my yearly bonus get taxed like my salary?" 0.655; live, "Is my medical allowance
# taxable?" 0.651 and "How much tax do I owe?" 0.624, which then gets no Tax page line). At
# 0.62 those are answered and the model refuses borderline ones itself, but the refusal rate
# drops to 0.70. The lead sets the pass marks; if they lower the refusal mark, lower this too.
RELEVANCE_CUTOFF = 0.66
