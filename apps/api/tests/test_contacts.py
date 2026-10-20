"""Contact field rules (us-7 item 1). Pure domain, no database."""

from __future__ import annotations

import pytest

from unghosted.domain.contacts import (
    MAX_NAME_LENGTH,
    ContactValidationError,
    search_pattern,
    validate_contact,
)


def test_validation_keeps_the_name_and_drops_surrounding_space() -> None:
    fields = validate_contact(name="  Martin Dupont  ")
    assert fields.name == "Martin Dupont"


def test_validation_turns_blank_optional_fields_into_none() -> None:
    fields = validate_contact(name="Martin", role="   ", notes="")
    assert fields.role is None
    assert fields.notes is None


def test_validation_rejects_an_empty_name() -> None:
    with pytest.raises(ContactValidationError) as caught:
        validate_contact(name="   ")
    assert caught.value.field == "name"


def test_validation_rejects_an_over_long_name() -> None:
    with pytest.raises(ContactValidationError):
        validate_contact(name="x" * (MAX_NAME_LENGTH + 1))


@pytest.mark.parametrize(
    "email", ["martin(at)dojoclub", "martin@dojoclub", "martin @dojoclub.example"]
)
def test_validation_rejects_a_malformed_email(email: str) -> None:
    with pytest.raises(ContactValidationError) as caught:
        validate_contact(name="Martin", email=email)
    assert caught.value.field == "email"


def test_validation_accepts_a_plain_email() -> None:
    fields = validate_contact(name="Martin", email=" martin@dojoclub.example ")
    assert fields.email == "martin@dojoclub.example"


def test_validation_rejects_a_profile_url_without_a_web_scheme() -> None:
    with pytest.raises(ContactValidationError) as caught:
        validate_contact(name="Martin", profile_url="javascript:alert(1)")
    assert caught.value.field == "profile_url"


def test_validation_accepts_an_https_profile_url() -> None:
    fields = validate_contact(name="Martin", profile_url="https://example.com/martin")
    assert fields.profile_url == "https://example.com/martin"


def test_search_pattern_escapes_sql_wildcards() -> None:
    assert search_pattern("50%") == "%50\\%%"
    assert search_pattern("a_b") == "%a\\_b%"
    assert search_pattern(" dojo ") == "%dojo%"
