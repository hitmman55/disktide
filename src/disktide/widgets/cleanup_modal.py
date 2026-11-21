"""CleanupPlan review with distinct preview, safe apply, and permanent paths."""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Static

from disktide.i18n import format_size, status_label, translate
from disktide.domain.cleanup import CleanupActionKind, CleanupPlan
from disktide.models.patterns import RiskLevel
from disktide.services.cleanup import CleanupService
from disktide.viz.colors import ink


@dataclass(frozen=True, slots=True)
class CleanupModalResult:
    action: CleanupActionKind
    confirmation: str | None = None


class CleanupModal(ModalScreen[CleanupModalResult | None]):
    """Review one persisted plan before any filesystem mutation."""

    PREVIEW = CleanupActionKind.PREVIEW
    APPLY = CleanupActionKind.TRASH
    PERMANENT = CleanupActionKind.PERMANENT
    DRY_RUN = PREVIEW
    DELETE = PERMANENT

    DEFAULT_CSS = """
    CleanupModal {
        align: center middle;
    }

    #cleanup-dialog {
        width: 118;
        max-width: 98%;
        max-height: 44;
        background: $surface;
        border: double $primary;
        padding: 1 2;
    }

    #cleanup-table {
        height: auto;
        max-height: 20;
    }

    #cleanup-confirmation {
        height: auto;
        padding: 1 0;
        color: $error;
    }

    #confirm-input {
        margin-top: 1;
    }

    .button-row {
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, plan: CleanupPlan, **kwargs):
        super().__init__(**kwargs)
        self._plan = plan
        self._confirmation = CleanupService.permanent_confirmation(plan.id)
        self._has_executable_actions = any(
            not action.detection_only for action in plan.active_actions
        )

    def compose(self) -> ComposeResult:
        with Vertical(id="cleanup-dialog"):
            yield Static(
                Text(
                    translate("CleanupPlan {value} · v{version}").format(
                        value=self._plan.id[:12],
                        version=self._plan.version,
                    ),
                    style="bold",
                )
            )
            yield Static(
                translate(
                    "Preview is read-only. Safe apply uses system Trash when "
                    "possible, otherwise same-filesystem quarantine."
                )
            )
            table = DataTable(id="cleanup-table")
            table.add_columns(
                translate("Pack"),
                translate("Category"),
                translate("Path"),
                translate("Age"),
                translate("Estimated"),
                translate("Score"),
                translate("Confidence"),
                translate("Risk"),
                translate("Policy"),
            )
            yield table
            yield Static(
                Text(
                    translate(
                        "Estimated reclaimable: {naturalsize} across {len} action(s); confidence "
                        "{confidence}; {value} subsumed."
                    ).format(
                        naturalsize=format_size(
                            self._plan.estimated_reclaimable_bytes, binary=True
                        ),
                        len=len(self._plan.active_actions),
                        confidence=f"{self._plan.confidence:.0%}",
                        value=len(self._plan.actions) - len(self._plan.active_actions),
                    ),
                    style=ink("bar_strong"),
                )
            )
            with Vertical(id="cleanup-confirmation"):
                yield Static(
                    Text(
                        translate(
                            "Permanent delete bypasses recovery. To use the red button, type exactly: "
                            "{_confirmation}"
                        ).format(
                            _confirmation=self._confirmation,
                        ),
                        style=ink("error_strong"),
                    )
                )
                yield Input(
                    placeholder=self._confirmation,
                    id="confirm-input",
                )
            with Horizontal(classes="button-row"):
                yield Button(
                    translate("Save Preview"), variant="primary", id="btn-preview"
                )
                yield Button(
                    translate("Apply Safe Candidates"),
                    variant="success",
                    id="btn-apply",
                    disabled=not self._has_executable_actions,
                )
                yield Button(
                    translate("Permanent Delete"),
                    variant="error",
                    id="btn-permanent",
                    disabled=not self._has_executable_actions,
                )
                yield Button(translate("Cancel"), variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        table = self.query_one("#cleanup-table", DataTable)
        for action in self._plan.active_actions:
            risk_style = {
                RiskLevel.SAFE: ink("bar"),
                RiskLevel.MODERATE: ink("warning"),
                RiskLevel.DANGEROUS: ink("error_strong"),
            }[action.risk]
            table.add_row(
                f"{action.rule_pack}@{action.rule_pack_version}",
                status_label(action.category),
                _truncate(action.path, 34),
                translate("{age_days}d").format(age_days=f"{action.age_days:.1f}"),
                format_size(
                    action.estimated_reclaimable_bytes,
                    binary=True,
                ),
                f"{action.score:.1f}",
                f"{action.confidence:.0%}",
                Text(status_label(action.risk.value), style=risk_style),
                translate("detection-only")
                if action.detection_only
                else translate(action.rule_action_policy.value),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-preview":
            self.dismiss(CleanupModalResult(CleanupActionKind.PREVIEW))
        elif event.button.id == "btn-apply":
            self.dismiss(CleanupModalResult(CleanupActionKind.TRASH))
        elif event.button.id == "btn-permanent":
            value = self.query_one("#confirm-input", Input).value
            if value != self._confirmation:
                self.query_one("#confirm-input", Input).focus()
                self.notify(
                    translate("Permanent confirmation does not match"), severity="error"
                )
                return
            self.dismiss(
                CleanupModalResult(
                    CleanupActionKind.PERMANENT,
                    confirmation=value,
                )
            )


def _truncate(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return "..." + value[-(width - 3):]
