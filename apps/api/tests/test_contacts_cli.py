"""The `contacts-reconcile` command (us-7 item 3) against the compose
databases. Synchronous on purpose: the command owns its event loop."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner
from litestar.cli._utils import LitestarEnv, LitestarGroup

from unghosted.api.cli import ContactsCliPlugin
from unghosted.app import create_app
from unghosted.services.contacts import OrphanReport, format_reports

pytestmark = pytest.mark.integration


def test_contacts_reconcile_command_reports_the_projects_it_checked(
    migrated_db: None,
) -> None:
    group = LitestarGroup(name="litestar")
    ContactsCliPlugin().on_cli_init(group)
    app = create_app()
    env = LitestarEnv(app_path="unghosted.app:create_app", app=app, cwd=Path.cwd())

    result = CliRunner().invoke(group, ["contacts-reconcile"], obj=env)

    assert result.exit_code == 0, result.output
    assert "projects checked" in result.output


def _invoke(*args: str) -> Any:
    group = LitestarGroup(name="litestar")
    ContactsCliPlugin().on_cli_init(group)
    app = create_app()
    env = LitestarEnv(app_path="unghosted.app:create_app", app=app, cwd=Path.cwd())
    return CliRunner().invoke(group, ["contacts-reconcile", *args], obj=env)


def test_contacts_reconcile_repair_flag_fixes_a_lost_index_write(
    migrated_db: None,
) -> None:
    """--repair is the opt-in that closes what the report opens. Synchronous
    on purpose: the command owns its event loop, so the seeding runs on a
    loop of its own first."""
    from sqlalchemy import delete, text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from unghosted.config import load_settings
    from unghosted.db.models import Contact, ContactRowLink, Project
    from unghosted.db.sql import create_engine

    async def seed() -> None:
        engine = create_engine(load_settings())
        factory = async_sessionmaker(engine)
        async with factory() as session:
            project = Project(
                owner_user_id=uuid.uuid4(),
                name="Search",
                template_key="apprenticeship-search",
                template_version=1,
            )
            session.add(project)
            await session.flush()
            contact = Contact(project_id=project.id, name="Martin Dupont")
            session.add(contact)
            await session.flush()
            # A link pointing at a row Mongo never had: pure Postgres state,
            # no tracker needed for this class of orphan.
            session.add(
                ContactRowLink(
                    project_id=project.id,
                    contact_id=contact.id,
                    row_id="row-that-never-existed",
                )
            )
            await session.commit()
        await engine.dispose()

    async def links_left() -> int:
        from sqlalchemy import func, select

        engine = create_engine(load_settings())
        factory = async_sessionmaker(engine)
        async with factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(ContactRowLink)
            )
        await engine.dispose()
        return int(count or 0)

    asyncio.run(seed())
    try:
        report = _invoke()
        assert report.exit_code == 0, report.output
        assert "links pointing at a missing tracker row" in report.output

        repaired = _invoke("--repair")
        assert repaired.exit_code == 0, repaired.output
        assert "repaired" in repaired.output
        assert "1 links dropped" in repaired.output

        after = _invoke()
        assert after.exit_code == 0, after.output
        assert "no orphans" in after.output
        assert asyncio.run(links_left()) == 0
    finally:
        # Leave the databases as empty as the fixture found them.
        async def cleanup() -> None:
            engine = create_engine(load_settings())
            factory = async_sessionmaker(engine)
            async with factory() as session:
                await session.execute(delete(ContactRowLink))
                await session.execute(delete(Contact))
                await session.execute(text("TRUNCATE TABLE app.projects CASCADE"))
                await session.commit()
            await engine.dispose()

        asyncio.run(cleanup())


def test_report_text_names_every_kind_of_orphan() -> None:
    report = OrphanReport(
        project_id="11111111-1111-4111-8111-111111111111",
        project_name="Search",
        unknown_contact_ids=["c-1"],
        links_without_row=["row-1:c-2"],
        links_without_cell=["row-2:c-3"],
        cells_without_link=["row-3:c-4"],
    )
    text = format_reports([report])
    assert "project Search" in text
    assert "contact ids in cells with no contact row: c-1" in text
    assert "links pointing at a missing tracker row: row-1:c-2" in text
    assert "links the tracker cell does not list: row-2:c-3" in text
    assert "cell entries with no link row: row-3:c-4" in text
    assert "orphans above" in text
