from __future__ import annotations
import re
from decimal import Decimal, InvalidOperation
from pydantic import BaseModel, field_serializer
from typing import Final

class FieldExtractionError(Exception): 
    """Raised when structured fields cannot be extracted."""

class CreditApplicationFields(BaseModel):
    # Applicant information
    full_name: str | None = None
    date_of_birth: str | None = None
    nationality: str | None = None
    residential_address: str | None = None
    email: str | None = None
    phone: str | None = None
    marital_status: str | None = None
    dependants: int | None = None

    # Employment information
    employment_status: str | None = None
    employer: str | None = None
    position: str | None = None
    employment_since: str | None = None

    # Income
    net_monthly_salary: Decimal | None = None
    other_monthly_income: Decimal | None = None
    total_monthly_income: Decimal | None = None

    # Requested credit
    requested_loan_amount: Decimal | None = None
    loan_purpose: str | None = None
    requested_term: int | None = None
    preferred_payment_date: str | None = None

    # Monthly expenses
    rent_and_utilities: Decimal | None = None
    food_and_household: Decimal | None = None
    transport_expenses: Decimal | None = None
    insurance_expenses: Decimal | None = None
    existing_loan_payment: Decimal | None = None
    total_monthly_expenses: Decimal | None = None

    # Bank account
    iban: str | None = None
    bic: str | None = None
    average_account_balance: Decimal | None = None

    # Liabilities
    outstanding_personal_loan: Decimal | None = None
    credit_card_balance: Decimal | None = None



    @field_serializer(
        "net_monthly_salary",
        "other_monthly_income",
        "total_monthly_income",
        "requested_loan_amount",
        "rent_and_utilities",
        "food_and_household",
        "transport_expenses",
        "insurance_expenses",
        "existing_loan_payment",
        "total_monthly_expenses",
        "average_account_balance",
        "outstanding_personal_loan",
        "credit_card_balance",
        when_used="json",
    )
    def serialize_money(
        self,
        value: Decimal | None,
    ) -> str | None:
        return format_money_austrian(value)

FIELD_LABELS: Final[dict[str, list[str]]] = {
    "full_name": ["Full name"],
    "date_of_birth": ["Date of birth"],
    "nationality": ["Nationality"],
    "residential_address": ["Residential address"],
    "email": ["Email"],
    "phone": ["Phone"],
    "marital_status": ["Marital status"],
    "dependants": ["Dependants", "Dependents"],

    "employment_status": ["Employment status"],
    "employer": ["Employer"],
    "position": ["Position"],
    "employment_since": ["Employment since"],

    "net_monthly_salary": ["Net monthly salary"],
    "other_monthly_income": ["Other monthly income"],
    "total_monthly_income": ["Total monthly net income", "Total monthly income"],

    "requested_loan_amount": ["Requested loan amount"],
    "loan_purpose": ["Loan purpose"],
    "requested_term": ["Requested term"],
    "preferred_payment_date": ["Preferred payment date"],

    "rent_and_utilities": ["Rent including utilities"],
    "food_and_household": ["Food and household expenses", "Food and household"],
    "transport_expenses": ["Transport expenses", "Transport"],
    "insurance_expenses": ["Insurance expenses", "Insurance"],
    "existing_loan_payment": ["Existing personal loan payment"],
    "total_monthly_expenses": ["Total monthly expenses"],

    "iban": ["IBAN"],
    "bic": ["BIC / SWIFT", "BIC/SWIFT", "BIC"],
    "average_account_balance": ["Average account balance (3 months)", "Average balance (3 months)"],

    "outstanding_personal_loan": ["Existing personal loan - outstanding", "Existing personal loan outstanding"],
    "credit_card_balance": ["Credit card balance"],
}

BOUNDARY_LABELS: Final[list[str]] = [
    "1. Applicant Information",
    "Applicant Information",
    "2. Employment and Income",
    "Employment and Income",
    "3. Requested Credit",
    "Requested Credit",
    "4. Monthly Expenses and Existing Obligations",
    "Monthly Expenses and Existing Obligations",
    "5. Bank Account Information",
    "Bank Account Information",
    "6. Existing Liabilities",
    "Existing Liabilities",
    "7. Supporting Documents",
    "Supporting Documents",
    "7. Supporting Documents Submitted",
    "Supporting Documents Submitted",
    "8. Applicant Declaration",
    "Applicant Declaration",
    "CREDIT APPLICATION - FINANCIAL DETAILS",
]

MONEY_FIELDS: Final[set[str]] = {
    "net_monthly_salary",
    "other_monthly_income",
    "total_monthly_income",
    "requested_loan_amount",
    "rent_and_utilities",
    "food_and_household",
    "transport_expenses",
    "insurance_expenses",
    "existing_loan_payment",
    "total_monthly_expenses",
    "average_account_balance",
    "outstanding_personal_loan",
    "credit_card_balance",
}

INTEGER_FIELDS: Final[set[str]] = {
    "dependants",
    "requested_term",
}

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
    text = re.sub(
        r"---\s*Page\s+\d+\s*---",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        (
            r"Synthetic test document\s*-\s*"
            r"all persons,\s*accounts and values are fictional"
            r"\s*Page\s*\d+"
        ),
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("\u00a0", " ")

    text = text.replace("–", "-")
    text = text.replace("—", "-")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()

def build_label_lookup() -> dict[str, str | None]:

    lookup: dict[str, str | None] = {}

    for field_name, labels in FIELD_LABELS.items():
        for label in labels:
            lookup[label.casefold()] = field_name

    for label in BOUNDARY_LABELS:
        lookup[label.casefold()] = None

    return lookup

def build_label_pattern(
    label_lookup: dict[str, str | None],
) -> re.Pattern[str]:
    labels = sorted(
        label_lookup.keys(),
        key=len,
        reverse=True,
    )

    alternatives = "|".join(
        re.escape(label)
        for label in labels
    )

    return re.compile(
        rf"(?<!\w)(?:{alternatives})(?!\w)",
        flags=re.IGNORECASE,
    )

def extract_raw_fields(
    text: str,
) -> dict[str, str]:

    label_lookup = build_label_lookup()
    label_pattern = build_label_pattern(label_lookup)

    matches = list(label_pattern.finditer(text))

    extracted: dict[str, str] = {}

    for index, match in enumerate(matches):
        matched_label = match.group(0).casefold()

        field_name = label_lookup.get(matched_label)

        if field_name is None:
            continue

        value_start = match.end()

        if index + 1 < len(matches):
            value_end = matches[index + 1].start()
        else:
            value_end = len(text)

        value = text[
            value_start:value_end
        ].strip()

        value = value.strip(" :-|")

        if value and field_name not in extracted:
            extracted[field_name] = value

    return extracted

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

def parse_integer(
    value: str | None,
) -> int | None:

    if value is None:
        return None

    match = re.search(
        r"\d+",
        value,
    )

    if match is None:
        return None

    return int(match.group(0))


def normalize_iban(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    match = re.search(
        r"\bAT(?:[\s-]*\d){18}\b",
        value,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    normalized_iban = re.sub(
        r"[^A-Z0-9]",
        "",
        match.group(0).upper(),
    )

    return normalized_iban

def normalize_bic(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    bic_match = re.search(
        r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",
        value.upper(),
    )

    if bic_match is None:
        return None

    return bic_match.group(0)


def normalize_email(
    value: str | None,
) -> str | None:
    
    if value is None:
        return None

    match = re.search(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
        value,
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    return match.group(0).lower()


def normalize_phone(
    value: str | None,
) -> str | None:

    if value is None:
        return None

    match = re.search(
        r"\+43(?:[\s-]*\d){7,14}",
        value,
    )

    if match is None:
        return None

    phone = re.sub(
        r"\s+",
        " ",
        match.group(0),
    )

    return phone.strip()

def extract_credit_application_fields(
    text: str,
) -> CreditApplicationFields:

    if not text.strip():
        raise FieldExtractionError("The extracted document text is empty.")

    normalized_text = normalize_document_text(text)

    raw_fields = extract_raw_fields(normalized_text)

    parsed_fields: dict[str, object] = {}

    for field_name in FIELD_LABELS:
        raw_value = raw_fields.get(field_name)

        if field_name in MONEY_FIELDS:
            parsed_fields[field_name] = (
                parse_money(
                    raw_value
                )
            )

        elif field_name in INTEGER_FIELDS:
            parsed_fields[field_name] = (
                parse_integer(
                    raw_value
                )
            )

        elif field_name == "iban":
            parsed_fields[field_name] = (
                normalize_iban(
                    raw_value
                )
            )

        elif field_name == "bic":
            parsed_fields[field_name] = (
                normalize_bic(
                    raw_value
                )
            )

        elif field_name == "email":
            parsed_fields[field_name] = (
                normalize_email(
                    raw_value
                )
            )

        elif field_name == "phone":
            parsed_fields[field_name] = (
                normalize_phone(
                    raw_value
                )
            )

        else:
            parsed_fields[field_name] = (
                raw_value.strip()
                if raw_value
                else None
            )

    return CreditApplicationFields(**parsed_fields)