"""Splitting FBR's texts into citable passages (feature 006, task T005; research R2, FR-003).

Made-up pages copy the real files' shapes: the Ordinance's running header, footnotes and
amendment markers ("5[7B."), and the manual's page header and numbered headings.
"""

from app.rag.split import Part, split_guidance, split_law

ORDINANCE_PAGES = {
    58: (
        "Chapter II – Charge of Tax______________________ \n \n39 \n \n"
        "5[7B.  Tax on profit on debt. —(1) Subject to this Ordinance, a tax shall be imposed on "
        "every person who receives a yield or profit on debt.\n"
        " (2) The tax imposed under sub-section (1) shall be computed by applying the rate "
        "specified in Division IIIA of Part I of the First Schedule.] \n"
        "                                            \n"
        "5 Inserted by the Finance Act, 2010.\n"
    ),
    59: (
        "Chapter II – Charge of Tax______________________ \n \n40 \n \n"
        " (3) The profit on debt shall be treated as a separate block of income.\n"
        "3[7C. Tax on builders. — (1) Subject to this Ordinance, builders pay tax.\n"
    ),
    67: (
        "Chapter III – Tax on Taxable Income ______________________ \n \n48 \n \n"
        "PART II \nHEAD OF INCOME: SALARY \n \n"
        "12. Salary.— (1)  Any salary received by an employee in a tax year, other than "
        "salary that is exempt, shall be chargeable to tax 1[;] \n \n"
        " (2) Salary means any amount received by an employee from any employment, including —\n"
        "(a) any pay, wages or other remuneration provided to an employee;\n"
        "                                            \n"
        "1Semi-colon substituted by the Finance Act, 2015. \n"
    ),
    68: (
        "Chapter III – Tax on Taxable Income ______________________ \n \n49 \n \n"
        "(b) any perquisite, whether convertible to money or not; \n"
        # A footnote number stuck to the sub-section, with no bracket, as in the real §13(3).
        " \n1(3)  Where an employee receives a perquisite, see section 13.\n"
    ),
    69: (
        "Chapter III – Tax on Taxable Income ______________________ \n \n50 \n \n"
        "13. Value of perquisites.— (1)  For the purposes of computing the income of an "
        "employee, perquisites are valued as follows.\n"
    ),
}

LAW_PARTS = [Part("7B", (58, 59)), Part("12", (67, 69))]


def test_ordinance_sections_become_passages_cited_by_sub_section() -> None:
    """Fails if a sub-section loses its citable location or its page."""
    passages = split_law(ORDINANCE_PAGES, LAW_PARTS)

    assert [(p.location, p.page) for p in passages] == [
        ("§7B(1)", 58),
        ("§7B(2)", 58),
        ("§7B(3)", 59),
        ("§12(1)", 67),
        ("§12(2)", 67),
        ("§12(3)", 68),
    ]


def test_headers_footnotes_and_amendment_markers_are_removed() -> None:
    """Fails if page furniture or amendment notes reach a passage (they would be cited)."""
    text = " ".join(p.text for p in split_law(ORDINANCE_PAGES, LAW_PARTS))

    for noise in ("Chapter III", "Finance Act, 2015", "Semi-colon", "5[", "1[", "]"):
        assert noise not in text
    assert "Tax on profit on debt" in text


def test_nothing_outside_the_named_sections_is_kept() -> None:
    """Fails if a neighbouring section on a shared page (7C, 13) slips into the corpus (FR-001)."""
    text = " ".join(p.text for p in split_law(ORDINANCE_PAGES, LAW_PARTS))

    assert "builders" not in text
    assert "Value of perquisites" not in text


def test_a_long_sub_section_is_split_keeping_its_location() -> None:
    """Fails if a passage is far too long to search well, or a piece loses its location."""
    sentence = "The employer shall deduct tax at the average rate each month. "
    pages = {327: "149.  Salary. — (1)  " + sentence * 120}

    passages = split_law(pages, [Part("149", (327, 327))])

    assert len(passages) > 1
    assert {p.location for p in passages} == {"§149(1)"}
    assert all(len(p.text.split()) <= 400 for p in passages)


MANUAL_PAGES = {
    79: (
        "Normal IT Return – User Manual \n \n \n"
        "Document Version :1.1 PRAL © 2026 – All rights reserved Page 78 of 128 \n \n"
        "13.3. Computation \nThe system computes the tax.\n"
    ),
    80: (
        "Normal IT Return – User Manual \n \n \n"
        "Document Version :1.1 PRAL © 2026 – All rights reserved Page 79 of 128 \n \n"
        "14. (a) Wealth Statement \nThe wealth statement lists assets and liabilities.\n"
        "14.1. Foreign Assets / Liabilities \nEnter foreign assets here.\n"
    ),
    81: (
        "Normal IT Return – User Manual \n \n \n"
        "Document Version :1.1 PRAL © 2026 – All rights reserved Page 80 of 128 \n \n"
        "14.3. Reconciliation of Net Assets \nInflows minus outflows explain the change.\n"
        "(b) Immoveable Property (For Non-Resident Only) \nNon-residents enter property.\n"
    ),
}


def test_manual_chapters_become_passages_cited_by_heading() -> None:
    """Fails if a manual passage loses its chapter location or page, or keeps page furniture."""
    passages = split_guidance(MANUAL_PAGES, [Part("14", (80, 81))])

    assert [(p.location, p.page) for p in passages] == [
        ("ch. 14", 80),
        ("ch. 14.1", 80),
        ("ch. 14.3", 81),
    ]
    text = " ".join(p.text for p in passages)
    assert "Document Version" not in text and "User Manual" not in text
    assert "Non-residents" not in text  # part (b) is left out
    assert "computes the tax" not in text  # chapter 13 is not a named part


def test_every_passage_has_a_page_inside_its_part() -> None:
    """Fails if a passage could be cited with a page outside the configured range."""
    passages = split_law(ORDINANCE_PAGES, LAW_PARTS) + split_guidance(
        MANUAL_PAGES, [Part("14", (80, 81))]
    )

    assert all(p.page in (58, 59, 67, 68, 69, 80, 81) for p in passages)
    assert all(p.text.strip() for p in passages)
