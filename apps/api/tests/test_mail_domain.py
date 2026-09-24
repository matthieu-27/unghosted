"""Sending rules and grounding checks (us-5 items 3 and 5)."""

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from unghosted.domain.mail import (
    RECIPIENT_COOLDOWN,
    GroundingWarning,
    SendLimitError,
    assert_send_allowed,
    attachment_document_ids,
    day_start,
    detect_language,
    own_links_from_text,
    today_value,
    validate_grounding,
)

PARIS = ZoneInfo("Europe/Paris")
UTC = ZoneInfo("UTC")


class TestAssertSendAllowed:
    def test_send_allowed_under_cap_and_after_cooldown(self) -> None:
        now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        assert_send_allowed(
            sent_today=9,
            daily_cap=10,
            recipient_last_sent=now - RECIPIENT_COOLDOWN,
            now=now,
        )

    def test_send_blocked_at_daily_cap(self) -> None:
        now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        with pytest.raises(SendLimitError) as exc_info:
            assert_send_allowed(
                sent_today=10,
                daily_cap=10,
                recipient_last_sent=None,
                now=now,
            )
        assert exc_info.value.code == "daily_cap_reached"

    def test_send_blocked_inside_recipient_cooldown(self) -> None:
        now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        with pytest.raises(SendLimitError) as exc_info:
            assert_send_allowed(
                sent_today=0,
                daily_cap=10,
                recipient_last_sent=now - RECIPIENT_COOLDOWN + timedelta(seconds=1),
                now=now,
            )
        assert exc_info.value.code == "recipient_cooldown"

    def test_send_allowed_again_exactly_seven_days_later(self) -> None:
        now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
        assert_send_allowed(
            sent_today=0,
            daily_cap=10,
            recipient_last_sent=now - RECIPIENT_COOLDOWN,
            now=now,
        )

    def test_daily_cap_boundary_follows_project_timezone(self) -> None:
        """A 23:30 Paris send and a 00:10 Paris send fall on different local
        days even though both sit in the same UTC day window."""
        late_evening = datetime(2026, 9, 24, 21, 30, tzinfo=UTC)  # 23:30 Paris
        early_morning = datetime(2026, 9, 25, 0, 10, tzinfo=UTC)  # 02:10 Paris
        assert day_start(late_evening, PARIS) != day_start(early_morning, PARIS)
        assert day_start(late_evening, PARIS) == datetime(
            2026, 9, 23, 22, 0, tzinfo=UTC
        )
        assert day_start(early_morning, PARIS) == datetime(
            2026, 9, 24, 22, 0, tzinfo=UTC
        )


class TestDayStart:
    def test_day_start_paris_matches_utc_offset(self) -> None:
        # 12:00 UTC is 14:00 Paris (UTC+2 in June): the local day started at
        # 00:00 Paris, which is 22:00 UTC the previous evening.
        now = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
        assert day_start(now, PARIS) == datetime(2026, 5, 31, 22, 0, tzinfo=UTC)

    def test_day_start_winter_offset(self) -> None:
        # UTC+1 in January: 00:00 Paris is 23:00 UTC the previous day.
        now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        assert day_start(now, PARIS) == datetime(2026, 1, 14, 23, 0, tzinfo=UTC)


class TestDetectLanguage:
    def test_french_detected(self) -> None:
        assert detect_language("Bonjour, je vous écris pour ma candidature.") == "fr"

    def test_english_detected(self) -> None:
        assert detect_language("Hello, I am writing about your job offer.") == "en"

    def test_no_words_gives_none(self) -> None:
        assert detect_language("...") is None


class TestValidateGrounding:
    def base_kwargs(self) -> dict[str, Any]:
        return {
            "text": "Bonjour Martin,\n\nLe Dojo Club propose un poste intéressant.",
            "used_highlights": ["h1"],
            "known_highlight_ids": ["h1", "h2"],
            "company": "Le Dojo Club",
            "contact_name": "Martin",
            "expected_language": None,
            "own_links": [],
            "letter_attached": False,
        }

    def test_clean_draft_gives_no_warnings(self) -> None:
        assert validate_grounding(**self.base_kwargs()) == []

    def test_unknown_highlight_warns(self) -> None:
        warnings = validate_grounding(
            **{**self.base_kwargs(), "used_highlights": ["h9"]}
        )
        assert [w.code for w in warnings] == ["unknown_highlight"]

    def test_placeholder_leftover_warns(self) -> None:
        warnings = validate_grounding(
            **{
                **self.base_kwargs(),
                "text": (
                    "Bonjour Martin,\n\nLe Dojo Club propose un poste "
                    "intéressant. {{contact_name}}"
                ),
            }
        )
        assert [w.code for w in warnings] == ["placeholder_leftover"]

    def test_missing_company_and_contact_warn(self) -> None:
        warnings = validate_grounding(
            **{
                **self.base_kwargs(),
                "text": "Bonjour, voici ma candidature.",
            }
        )
        assert [w.code for w in warnings] == ["company_missing", "contact_missing"]

    def test_language_mismatch_warns(self) -> None:
        warnings = validate_grounding(
            **{
                **self.base_kwargs(),
                "expected_language": "fr",
                "text": "Hello Martin, I am applying to Le Dojo Club.",
            }
        )
        assert [w.code for w in warnings] == ["language_mismatch"]

    def test_foreign_link_warns_and_own_link_does_not(self) -> None:
        warnings = validate_grounding(
            **{
                **self.base_kwargs(),
                "own_links": ["https://matt.example/cv"],
                "text": (
                    "Bonjour Martin, Le Dojo Club — see https://matt.example/cv "
                    "and https://evil.example/offer"
                ),
            }
        )
        assert [w.code for w in warnings] == ["foreign_link"]
        assert "evil.example" in warnings[0].message

    def test_letter_attached_length_range_enforced(self) -> None:
        long_email = "Bonjour Martin. ".join(["x" for _ in range(8)]) + "Le Dojo Club."
        warnings = validate_grounding(
            **{**self.base_kwargs(), "text": long_email, "letter_attached": True}
        )
        assert [w.code for w in warnings] == ["length_out_of_range"]

    def test_warning_carries_user_facing_message(self) -> None:
        warning = GroundingWarning(code="x", message="explain")
        assert warning.message == "explain"


class TestHelpers:
    def test_own_links_from_text_collects_urls_and_ignores_none(self) -> None:
        links = own_links_from_text(None, "see https://a.example/x and nothing")
        assert links == ["https://a.example/x"]

    def test_attachment_ids_dedupe_in_order(self) -> None:
        import uuid

        first = uuid.uuid4()
        second = uuid.uuid4()
        assert attachment_document_ids([first, second, first]) == [first, second]

    def test_today_value_uses_local_date(self) -> None:
        now = datetime(2026, 9, 24, 23, 30, tzinfo=UTC)  # already Sep 25 in Paris
        assert today_value(now, PARIS) == "2026-09-25"
