"""Mail API: draft, edit, approve and send against the compose DBs (us-5).
Model, mail and PDF gateways are replaced per test through app state, so
the HTTP path runs without a provider, an SMTP server or Chromium."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from conftest import OWNER_USER, create_project
from test_documents import make_pdf

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.testing import AsyncTestClient

    from unghosted.gateways.mail import OutgoingMail

pytestmark = pytest.mark.integration

PARIS = ZoneInfo("Europe/Paris")
LISTING_URL = "https://jobs.dojoclub.example/alternant-data-engineer"
LISTING_TEXT = (
    "Le Dojo Club recherche un alternant data engineer en alternance "
    "pour accompagner son équipe data. Mission : construire des pipelines "
    "de données et des tableaux de bord."
)
LETTER_TEXT = (
    "Bonjour Martin,\n\nLe Dojo Club propose un poste d'alternant data "
    "engineer qui correspond bien à mon profil. Mon expérience de "
    "construction d'un tracker de candidatures me prépare directement à "
    "cette mission.\n\nJe vous remercie de votre attention.\n\n"
    "Bien cordialement, Matt"
)
FIRST_CONTACT_BODY = (
    "Bonjour Martin,\n\nLe Dojo Club propose un poste d'alternant data "
    "engineer qui me correspond bien. Vous trouverez ma lettre de "
    "motivation et mon CV en pièce jointe. Je serais ravi d'en discuter "
    "avec vous.\n\nBien cordialement, Matt"
)


class MailModel:
    """ModelGateway double for every mail task. The letter and first-contact
    outputs are grounded by construction, so a clean draft proves the
    warning pipeline runs and finds nothing, not that it is skipped."""

    provider = "fake"

    def __init__(
        self,
        *,
        letter: dict[str, Any] | None = None,
        first_contact: dict[str, Any] | None = None,
    ) -> None:
        self.letter_tasks: list[Any] = []
        self.first_contact_tasks: list[Any] = []
        self._letter = letter or {
            "text": LETTER_TEXT,
            "used_highlights": ["h1"],
        }
        self._first_contact = first_contact or {
            "subject": "Candidature alternance data engineer — Le Dojo Club",
            "body": FIRST_CONTACT_BODY,
            "used_highlights": ["h1"],
        }

    async def draft_profile(self, task: Any) -> dict[str, Any]:
        return {
            "headline": "Curious data apprentice",
            "seeking": "A work-study data role",
            "highlights": ["Built a tracker", "Loves clean data"],
            "motivation": "Wants to learn data engineering",
            "style_notes": ["Direct tone"],
            "availability": "From September",
        }

    async def draft_letter(self, task: Any) -> dict[str, Any]:
        self.letter_tasks.append(task)
        return self._letter

    async def draft_first_contact(self, task: Any) -> dict[str, Any]:
        self.first_contact_tasks.append(task)
        return self._first_contact

    async def extract_fields(self, task: Any) -> dict[str, Any]:
        raise AssertionError("mail tests never extract tracker fields")

    async def classify_kind(self, page_text: str) -> None:
        raise AssertionError("mail tests never classify pages")


class FakeMailGateway:
    """Records every message instead of delivering; answers like SMTP."""

    def __init__(self) -> None:
        self.sent: list[OutgoingMail] = []

    async def send(self, mail: OutgoingMail) -> Any:
        from unghosted.gateways.mail import SentMail

        self.sent.append(mail)
        return SentMail(
            provider="fake", message_id="fake-msg-1", thread_id="fake-thread-1"
        )


class FakePdfGateway:
    """Approve only needs bytes and a page verdict — no real rendering."""

    def __init__(self) -> None:
        self.rendered_html: list[str] = []

    async def render(self, html: str) -> Any:
        from unghosted.gateways.pdf import RenderedLetter

        self.rendered_html.append(html)
        return RenderedLetter(pdf_bytes=b"%PDF-fake-letter", fits_one_page=True)


def install_gateways(
    app: Litestar,
    model: MailModel | None = None,
    mail: FakeMailGateway | None = None,
    pdf: FakePdfGateway | None = None,
) -> None:
    """provide_mail_service reads state at request time, so per-test
    gateways land without rebuilding the app."""
    app.state["model_gateway"] = model
    app.state["mail_gateway"] = mail or FakeMailGateway()
    app.state["pdf_gateway"] = pdf or FakePdfGateway()


async def prepare_project_with_profile(
    client: AsyncTestClient[Any],
) -> tuple[dict[str, Any], MailModel]:
    """Consent, project, CV, approved profile — the full mail precondition."""
    response = await client.post(
        "/api/v1/account/consents", json={"kind": "model_processing"}
    )
    assert response.status_code == 201, response.text
    project = await create_project(client, "apprenticeship-search", "Search")
    upload = await client.post(
        f"/api/v1/projects/{project['id']}/documents",
        files={"file": ("cv.pdf", make_pdf(), "application/pdf")},
        data={"type_key": "cv"},
    )
    assert upload.status_code == 201, upload.text
    cv_id = upload.json()["id"]

    model = MailModel()
    install_gateways(client.app, model=model)
    drafted = await client.post(f"/api/v1/projects/{project['id']}/profile/drafts")
    assert drafted.status_code == 200, drafted.text
    version = drafted.json()["version"]
    approved = await client.post(
        f"/api/v1/projects/{project['id']}/profile/versions/{version}/approve"
    )
    assert approved.status_code == 200, approved.text
    return {**project, "cv_id": cv_id}, model


async def store_listing_analysis(project_id: str, source: str, text: str) -> None:
    """Seed the listing analysis directly: the HTTP route fetches real URLs,
    which integration tests must never do."""
    from unghosted.config import load_settings
    from unghosted.db.models import LinkAnalysis
    from unghosted.db.sql import create_engine

    engine = create_engine(load_settings())
    try:
        factory = async_sessionmaker(engine)
        async with factory() as session:
            session.add(
                LinkAnalysis(
                    project_id=uuid.UUID(project_id),
                    requested_by=OWNER_USER,
                    input_type="url",
                    source=source,
                    status="ok",
                    cleaned_text=text,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


async def add_row_with_listing(client: AsyncTestClient[Any], project_id: str) -> str:
    """One tracker row with the cells mail drafting grounds on."""
    listing_url = LISTING_URL
    response = await client.patch(
        f"/api/v1/projects/{project_id}/tracker/operations",
        json={
            "base_revision": 0,
            "operations": [{"op": "insert_rows", "count": 1}],
        },
    )
    assert response.status_code == 200, response.text
    revision = int(response.json()["revision"])
    tracker = await client.get(f"/api/v1/projects/{project_id}/tracker")
    row_id = str(tracker.json()["rows"][0]["id"])
    response = await client.patch(
        f"/api/v1/projects/{project_id}/tracker/operations",
        json={
            "base_revision": revision,
            "operations": [
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "company",
                    "value": "Le Dojo Club",
                },
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "position",
                    "value": "Data engineer apprentice",
                },
                {
                    "op": "set_cell",
                    "row_id": row_id,
                    "column_key": "listing_url",
                    "value": listing_url,
                },
            ],
        },
    )
    assert response.status_code == 200, response.text
    await store_listing_analysis(project_id, listing_url, LISTING_TEXT)
    return row_id


async def draft_letter(
    client: AsyncTestClient[Any], project_id: str, row_id: str
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/projects/{project_id}/rows/{row_id}/letter",
        json={"contact_name": "Martin", "language": "fr"},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def draft_first_contact(
    client: AsyncTestClient[Any],
    project_id: str,
    row_id: str,
    recipient: str = "martin@dojoclub.example",
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/projects/{project_id}/rows/{row_id}/first-contact",
        json={"recipient": recipient, "contact_name": "Martin", "language": "fr"},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_letter_draft_requires_an_approved_profile(
    client: AsyncTestClient[Any],
) -> None:
    await client.post("/api/v1/account/consents", json={"kind": "model_processing"})
    project = await create_project(client, "apprenticeship-search", "Search")
    install_gateways(client.app, model=MailModel())
    row_id = await add_row_with_listing(client, project["id"])
    response = await client.post(
        f"/api/v1/projects/{project['id']}/rows/{row_id}/letter", json={}
    )
    assert response.status_code == 409, response.text
    assert response.json()["extra"]["code"] == "no_approved_profile"


async def test_letter_draft_requires_an_analyzed_listing(
    client: AsyncTestClient[Any],
) -> None:
    project, _ = await prepare_project_with_profile(client)
    response = await client.patch(
        f"/api/v1/projects/{project['id']}/tracker/operations",
        json={
            "base_revision": 0,
            "operations": [{"op": "insert_rows", "count": 1}],
        },
    )
    assert response.status_code == 200, response.text
    tracker = await client.get(f"/api/v1/projects/{project['id']}/tracker")
    row_id = str(tracker.json()["rows"][0]["id"])
    response = await client.post(
        f"/api/v1/projects/{project['id']}/rows/{row_id}/letter", json={}
    )
    assert response.status_code == 409, response.text
    assert response.json()["extra"]["code"] == "no_listing_text"


async def test_letter_draft_refused_after_consent_withdrawal(
    client: AsyncTestClient[Any],
) -> None:
    project, _ = await prepare_project_with_profile(client)
    row_id = await add_row_with_listing(client, project["id"])
    withdrawn = await client.delete("/api/v1/account/consents/model_processing")
    assert withdrawn.status_code == 204
    response = await client.post(
        f"/api/v1/projects/{project['id']}/rows/{row_id}/letter", json={}
    )
    assert response.status_code == 403, response.text
    assert response.json()["extra"]["code"] == "consent_required"


async def test_letter_draft_edit_and_approve_lifecycle(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    pdf = FakePdfGateway()
    install_gateways(client.app, model=model, pdf=pdf)
    row_id = await add_row_with_listing(client, project["id"])

    draft = await draft_letter(client, project["id"], row_id)
    assert draft["kind"] == "customised_letter"
    assert draft["status"] == "draft"
    assert "Le Dojo Club" in draft["text"]
    assert draft["warnings"] == []
    assert len(model.letter_tasks) == 1
    assert model.letter_tasks[0].company == "Le Dojo Club"

    edited = await client.patch(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}",
        json={"text": LETTER_TEXT + "\n\nP.S. — added by hand"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["text"].endswith("added by hand")

    approved = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["fits_one_page"] is True
    assert body["draft"]["status"] == "approved"
    assert body["draft"]["letter_document_id"] == body["document_id"]
    # The letter layout carries the contact, company and French date, and
    # the body text is escaped, not interpreted.
    assert len(pdf.rendered_html) == 1
    assert "Martin" in pdf.rendered_html[0]
    assert "Le Dojo Club" in pdf.rendered_html[0]

    documents = await client.get(f"/api/v1/projects/{project['id']}/documents")
    types = {d["type_key"] for d in documents.json()["data"]}
    assert "generated_customised_letter" in types

    # An approved letter is frozen: further edits and re-approval refuse.
    conflict = await client.patch(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}",
        json={"text": "no longer editable"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["extra"]["code"] == "draft_state"
    again = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}/approve"
    )
    assert again.status_code == 409


async def test_draft_discard_freezes_the_draft(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])
    draft = await draft_letter(client, project["id"], row_id)

    discarded = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}/discard"
    )
    assert discarded.status_code == 200, discarded.text
    assert discarded.json()["status"] == "discarded"

    edited = await client.patch(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}",
        json={"text": "too late"},
    )
    assert edited.status_code == 409
    assert edited.json()["extra"]["code"] == "draft_state"


async def test_first_contact_preselects_cv_and_approved_letter(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])

    # Before any letter approval, only the CV is preselected.
    bare = await draft_first_contact(client, project["id"], row_id)
    assert bare["attachment_document_ids"] == [project["cv_id"]]
    assert bare["letter_document_id"] is None

    letter = await draft_letter(client, project["id"], row_id)
    approved = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{letter['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    letter_document_id = approved.json()["document_id"]

    with_letter = await draft_first_contact(client, project["id"], row_id)
    assert with_letter["attachment_document_ids"] == [
        project["cv_id"],
        letter_document_id,
    ]
    assert with_letter["kind"] == "first_contact_email"
    assert with_letter["recipient"] == "martin@dojoclub.example"
    assert len(model.first_contact_tasks) == 2
    assert model.first_contact_tasks[0].letter_attached is False
    assert model.first_contact_tasks[1].letter_attached is True


async def test_send_delivers_attachments_and_updates_the_row(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    mail = FakeMailGateway()
    install_gateways(client.app, model=model, mail=mail)
    row_id = await add_row_with_listing(client, project["id"])

    letter = await draft_letter(client, project["id"], row_id)
    approved = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{letter['id']}/approve"
    )
    assert approved.status_code == 200, approved.text
    letter_document_id = approved.json()["document_id"]
    draft = await draft_first_contact(client, project["id"], row_id)

    sent = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}/send", json={}
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["provider"] == "fake"
    assert body["recipient"] == "martin@dojoclub.example"
    assert sorted(map(str, body["attachment_document_ids"])) == sorted(
        [project["cv_id"], letter_document_id]
    )
    assert body["row_revision"] >= 2

    # The gateway carried both attachments and the final edited body.
    assert len(mail.sent) == 1
    outgoing = mail.sent[0]
    assert outgoing.sender == "applicant@example.com"
    assert len(outgoing.attachments) == 2
    assert all(a.mimetype == "application/pdf" for a in outgoing.attachments)
    assert outgoing.text_body == FIRST_CONTACT_BODY

    # The draft is closed and the row records the send (us-5 item 6).
    closed = await client.get(f"/api/v1/projects/{project['id']}/drafts/{draft['id']}")
    assert closed.status_code == 200
    assert closed.json()["status"] == "sent"
    tracker = await client.get(f"/api/v1/projects/{project['id']}/tracker")
    row = next(r for r in tracker.json()["rows"] if str(r["id"]) == row_id)
    cells = row["cells"]
    today = datetime.now(UTC).astimezone(PARIS).date().isoformat()
    assert cells["date_sent"] == today
    assert cells["last_contact"] == today
    assert cells["cv"] == [project["cv_id"]]
    assert cells["customised_letter"] == [letter_document_id]

    # The sent list is the read-back record of what went out.
    messages = await client.get(f"/api/v1/projects/{project['id']}/sent")
    assert messages.status_code == 200, messages.text
    data = messages.json()["data"]
    assert len(data) == 1
    assert data[0]["text"] == FIRST_CONTACT_BODY
    assert data[0]["row_id"] == row_id
    assert data[0]["direction"] == "outbound"


async def test_second_send_to_same_recipient_hits_the_cooldown(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])
    first = await draft_first_contact(client, project["id"], row_id)
    sent = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{first['id']}/send", json={}
    )
    assert sent.status_code == 200, sent.text

    second = await draft_first_contact(client, project["id"], row_id)
    blocked = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{second['id']}/send", json={}
    )
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["extra"]["code"] == "recipient_cooldown"


async def test_send_without_subject_is_a_validation_error(
    client: AsyncTestClient[Any],
) -> None:
    project, _ = await prepare_project_with_profile(client)
    model = MailModel(first_contact={"subject": None, "body": FIRST_CONTACT_BODY})
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])
    draft = await draft_first_contact(client, project["id"], row_id)
    assert draft["subject"] is None
    response = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{draft['id']}/send", json={}
    )
    assert response.status_code == 422, response.text
    assert response.json()["extra"]["code"] == "send_validation"


async def test_only_first_contact_drafts_are_sent_and_only_letters_approved(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])
    letter = await draft_letter(client, project["id"], row_id)
    email = await draft_first_contact(client, project["id"], row_id)

    sent_letter = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{letter['id']}/send", json={}
    )
    assert sent_letter.status_code == 409, sent_letter.text
    assert sent_letter.json()["extra"]["code"] == "draft_state"

    approved_email = await client.post(
        f"/api/v1/projects/{project['id']}/drafts/{email['id']}/approve"
    )
    assert approved_email.status_code == 409
    assert approved_email.json()["extra"]["code"] == "draft_state"


async def test_draft_for_missing_project_and_row_are_not_found(
    client: AsyncTestClient[Any],
) -> None:
    project, model = await prepare_project_with_profile(client)
    install_gateways(client.app, model=model)
    row_id = await add_row_with_listing(client, project["id"])

    missing_project = "00000000-0000-4000-8000-000000000404"
    response = await client.post(
        f"/api/v1/projects/{missing_project}/rows/{row_id}/letter", json={}
    )
    assert response.status_code == 404
    response = await client.post(
        f"/api/v1/projects/{project['id']}/rows/ghost-row/letter", json={}
    )
    assert response.status_code == 404
    response = await client.get(
        f"/api/v1/projects/{project['id']}/drafts/00000000-0000-4000-8000-000000000405"
    )
    assert response.status_code == 404
