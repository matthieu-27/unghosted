"""CLI commands registered on the Litestar app.

`litestar contacts-reconcile` reports contact↔row inconsistencies between
Postgres and Mongo (us-7 item 3); `--repair` opts into the deterministic,
cell-first fixes. It runs through the app's own wiring, so the command
reads exactly what the API reads — no second set of settings to keep in
step.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import click
from litestar import Litestar
from litestar.plugins import CLIPluginProtocol

from unghosted.repositories.contacts import (
    ContactRepository,
    ContactRowLinkRepository,
)
from unghosted.repositories.projects import ProjectRepository
from unghosted.repositories.tracker import TrackerRepository
from unghosted.services.contacts import ContactReconciler, format_reports

if TYPE_CHECKING:
    from click import Group


async def _run_reconcile(app: Litestar, *, repair: bool = False) -> str:
    """One report, then close what the command opened.

    The CLI never runs the ASGI lifespan, so nothing else would close the
    database pools — and connections that outlive their event loop surface
    as ResourceWarnings.
    """
    factory = app.state.session_factory
    try:
        async with factory() as session:
            reconciler = ContactReconciler(
                projects=ProjectRepository(session),
                contacts=ContactRepository(session),
                links=ContactRowLinkRepository(session),
                tracker=TrackerRepository(app.state.mongo_db),
            )
            reports = await reconciler.run(repair=repair)
            if repair:
                await session.commit()
            return format_reports(reports)
    finally:
        await app.state.mongo_client.close()
        await app.state.engine.dispose()


class ContactsCliPlugin(CLIPluginProtocol):
    def on_cli_init(self, cli: Group) -> None:
        @cli.command(name="contacts-reconcile")
        @click.option(
            "--repair",
            is_flag=True,
            default=False,
            help="Apply the per-class fixes (opt-in: the report alone is the safe default).",
        )
        def contacts_reconcile(app: Litestar, repair: bool) -> None:
            """Report — and with --repair, fix — contact links that Postgres
            and Mongo disagree on."""
            click.echo(asyncio.run(_run_reconcile(app, repair=repair)))
