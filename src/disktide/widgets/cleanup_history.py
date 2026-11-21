"""Cleanup savings history modal with distinct accounting columns."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Static

from disktide.i18n import format_size, translate
from disktide.domain.cleanup import CleanupSavingsSummary


class CleanupHistoryModal(ModalScreen[None]):
    DEFAULT_CSS = """
    CleanupHistoryModal {
        align: center middle;
    }

    #cleanup-history-dialog {
        width: 110;
        max-width: 96%;
        height: 34;
        max-height: 90%;
        background: $surface;
        border: double $primary;
        padding: 1 2;
    }

    #cleanup-history-table {
        height: 1fr;
    }

    #cleanup-history-actions {
        height: 3;
        align: center middle;
    }
    """

    def __init__(
        self,
        summaries: list[CleanupSavingsSummary],
        *,
        group_by: str = "category",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._summaries = summaries
        self._group_by = group_by

    def compose(self) -> ComposeResult:
        with Vertical(id="cleanup-history-dialog"):
            yield Static(
                translate("Cleanup savings history · grouped by {_group_by}").format(
                    _group_by=self._group_by,
                ),
                classes="title",
            )
            yield Static(
                translate(
                    "Estimated, isolated, purged, actual reclaimed, and undone are "
                    "kept separate. Quarantine isolation is not free space."
                )
            )
            table = DataTable(id="cleanup-history-table")
            table.add_columns(
                self._group_by.title(),
                translate("Actions"),
                translate("Estimated"),
                translate("Isolated"),
                translate("Purged"),
                translate("Actual"),
                translate("Undone"),
            )
            yield table
            with Horizontal(id="cleanup-history-actions"):
                yield Button(
                    translate("Close"), id="cleanup-history-close", variant="primary"
                )

    def on_mount(self) -> None:
        table = self.query_one("#cleanup-history-table", DataTable)
        for item in self._summaries:
            table.add_row(
                item.key,
                str(item.action_count),
                _size(item.estimated_bytes),
                _size(item.isolated_bytes),
                _size(item.purged_bytes),
                _size(item.actual_reclaimed_bytes),
                _size(item.undone_bytes),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cleanup-history-close":
            self.dismiss(None)


def _size(value: int) -> str:
    return format_size(value, binary=True)
