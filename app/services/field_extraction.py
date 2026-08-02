from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, field_serializer

class FieldExtractionError(Exception): 
    """Raised when structured fields cannot be extracted."""

class CreditApplicationFields(BaseModel):
    full_name: str | None = None
    net_monthly_salary: Decimal | None = None
    requested_loan_amount: Decimal | None = None
    iban: str | None = None
    credit_card_balance: Decimal | None = None

    @field_serializer(
        "net_monthly_salary",
        "requested_loan_amount",
        "credit_card_balance",
        when_used="json",
    )
    def serialize_money(
        self,
        value: Decimal | None,
    ) -> str | None:
        return format_money_austrian(value)

def format_money_austrian(
    value: Decimal | None,
) -> str | None:

    if value is None:
        return None

    english_format = f"{value:,.2f}"

    return english_format.translate(
        str.maketrans({
            ",": ".",
            ".": ",",
        })
    )

def normalize_document_text(text: str) -> str:
    # Remove page markers
    text = re.sub(
        r"---\s*Page\s+\d+\s*---",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Replace non-breaking spaces
    text = text.replace("\u00a0", " ")

    # Replace repeated whitespace and line breaks with one space.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()

def extract_value_between_labels(
    text: str,
    start_label: str,
    end_labels: list[str],
) -> str | None:

    if not end_labels:
        raise ValueError(
            "At least one end label must be provided."
        )

    escaped_end_labels = [
        re.escape(label)
        for label in end_labels
    ]

    end_pattern = "|".join(
        escaped_end_labels
    )

    pattern = (
        rf"{re.escape(start_label)}"
        rf"\s+"
        rf"(.*?)"
        rf"(?=\s+(?:{end_pattern})|$)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    value = match.group(1).strip()

    return value or None

def parse_money(
    value: str | None
) -> Decimal | None:
    
    if value is None:
        return None

    money_pattern = (
        r"(?<![\d.,])"
        r"-?"
        r"(?:"
        r"\d{1,3}(?:\.\d{3})+"
        r"|"
        r"\d+"
        r")"
        r",\d{2}"
        r"(?![\d.,])"
    )

    number_match = re.search(
        money_pattern,
        value,
    )

    if number_match is None:
        return None

    austrian_number = number_match.group(0)

    normalized_number = (
        austrian_number
        .replace(".", "")
        .replace(",", ".")
    )

    try:
        return Decimal(normalized_number)

    except InvalidOperation:
        return None

def normalize_austrian_iban(
    value: str | None,
) -> str | None:
    """
    Normalize and validate an Austrian IBAN.

    Austrian IBAN format:
        AT followed by 18 digits

    Example:
        AT61 1904 3002 3457 3201

    becomes:
        AT611904300234573201
    """

    if value is None:
        return None

    normalized_iban = re.sub(
        r"[^A-Z0-9]",
        "",
        value.upper(),
    )

    if not re.fullmatch(
        r"AT\d{18}",
        normalized_iban,
    ):
        return None

    return normalized_iban


def extract_credit_application_fields(
    text: str,
) -> CreditApplicationFields:
    """
    Extract the initial five structured fields from document text.
    """

    if not text.strip():
        raise FieldExtractionError(
            "The extracted document text is empty."
        )

    normalized_text = normalize_document_text(
        text
    )

    full_name = extract_value_between_labels(
        text=normalized_text,
        start_label="Full name",
        end_labels=[
            "Date of birth",
        ],
    )

    salary_text = extract_value_between_labels(
        text=normalized_text,
        start_label="Net monthly salary",
        end_labels=[
            "Other monthly income",
        ],
    )

    loan_amount_text = extract_value_between_labels(
        text=normalized_text,
        start_label="Requested loan amount",
        end_labels=[
            "Loan purpose",
        ],
    )

    iban_text = extract_value_between_labels(
        text=normalized_text,
        start_label="IBAN",
        end_labels=[
            "BIC / SWIFT",
            "BIC",
        ],
    )

    credit_card_text = extract_value_between_labels(
        text=normalized_text,
        start_label="Credit card balance",
        end_labels=[
            "7. Supporting Documents Submitted",
            "Supporting Documents Submitted",
            "7. Supporting Documents",
            "Supporting Documents",
        ],
    )

    return CreditApplicationFields(
        full_name=full_name,
        net_monthly_salary=parse_money(
            salary_text
        ),
        requested_loan_amount=parse_money(
            loan_amount_text
        ),
        iban=normalize_austrian_iban(
            iban_text
        ),
        credit_card_balance=parse_money(
            credit_card_text
        ),
    )