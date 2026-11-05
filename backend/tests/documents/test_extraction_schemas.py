"""The output schemas Claude must follow (feature 003, task T007, research R2)."""

import pytest
from pydantic import ValidationError

from app.documents.extraction.schemas import OUTPUT_SCHEMAS, ExtractedValue
from app.documents.models import FIELDS_BY_TYPE, DocType

IDENTITY_WORDS = ("name", "cnic", "ntn", "account", "address", "iban")


@pytest.mark.parametrize("doc_type", list(DocType))
def test_each_type_asks_for_exactly_its_fields(doc_type: DocType) -> None:
    """Fails if the schema and the stored fields drift apart (a field never saved, or lost)."""
    schema = OUTPUT_SCHEMAS[doc_type].model_json_schema()

    assert set(schema["properties"]) == {name.value for name in FIELDS_BY_TYPE[doc_type]}
    assert set(schema["required"]) == set(schema["properties"])


@pytest.mark.parametrize("doc_type", list(DocType))
def test_no_identity_fields_are_requested(doc_type: DocType) -> None:
    """Fails if the schema would ask the model for names, CNICs, accounts etc. (FR-003)."""
    properties = OUTPUT_SCHEMAS[doc_type].model_json_schema()["properties"]

    for field_name in properties:
        assert not any(word in field_name for word in IDENTITY_WORDS)


def test_each_value_has_value_confidence_page_and_label() -> None:
    """Fails if a field loses where it was found or how sure the model is (R2)."""
    value = ExtractedValue(value="1,800,000", confidence="high", page=1, label="Gross Salary")

    assert value.model_dump() == {
        "value": "1,800,000",
        "confidence": "high",
        "page": 1,
        "label": "Gross Salary",
    }


def test_not_found_is_null_value() -> None:
    """Fails if "not found" can't be expressed (the model must not guess, R2)."""
    assert ExtractedValue(value=None, confidence="low", page=None, label=None).value is None


@pytest.mark.parametrize("confidence", ["certain", "HIGH", ""])
def test_unknown_confidence_is_refused(confidence: str) -> None:
    """Fails if a confidence other than high, medium or low gets through."""
    with pytest.raises(ValidationError):
        ExtractedValue(value="1", confidence=confidence, page=1, label="x")  # type: ignore[arg-type]
