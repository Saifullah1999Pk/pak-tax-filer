"""What Claude must return for each certificate type (feature 003, research R1-R2).

Sent as a structured-output JSON schema, so the reply is always valid JSON in this shape. Only
figures are requested: never names, CNICs, NTNs, account numbers or addresses (FR-003).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.documents.models import DocType


class ExtractedValue(BaseModel):
    """One figure as printed, with how sure the model is and where it found it."""

    model_config = ConfigDict(extra="forbid")

    value: str | None = Field(
        description="Exactly as printed, e.g. 'Rs. 1,800,000/-'; null if not on the document."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="high: clearly printed and labelled; medium: some doubt; low: a guess."
    )
    page: int | None = Field(description="1-based page it was found on; null if not found.")
    label: str | None = Field(
        description="The label printed next to it, e.g. 'Gross Salary'; null if not found."
    )


class SalaryCertificateFields(BaseModel):
    """The four figures on an employer's salary certificate."""

    model_config = ConfigDict(extra="forbid")

    tax_year: ExtractedValue = Field(description="The tax year the certificate covers.")
    gross_salary: ExtractedValue = Field(description="Total salary before exemptions.")
    taxable_salary: ExtractedValue = Field(description="Salary on which tax is charged.")
    tax_deducted: ExtractedValue = Field(description="Income tax deducted by the employer.")


class BankProfitCertificateFields(BaseModel):
    """The three figures on a bank's profit (profit on debt) certificate."""

    model_config = ConfigDict(extra="forbid")

    tax_year: ExtractedValue = Field(description="The tax year the certificate covers.")
    profit_amount: ExtractedValue = Field(description="Gross profit paid on the deposits.")
    tax_withheld: ExtractedValue = Field(description="Tax withheld by the bank under section 151.")


OUTPUT_SCHEMAS: dict[DocType, type[BaseModel]] = {
    DocType.SALARY_CERTIFICATE: SalaryCertificateFields,
    DocType.BANK_PROFIT_CERTIFICATE: BankProfitCertificateFields,
}
