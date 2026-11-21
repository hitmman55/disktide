"""Language selection and the application message catalog."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from disktide.domain.policy import ScanPolicy


def language() -> str:
    """Choose the language for this process without setting the system locale."""
    locale = (
        os.environ.get("DISKTIDE_LANG")
        or os.environ.get("LC_ALL")
        or os.environ.get("LC_MESSAGES")
        or os.environ.get("LANGUAGE", "").split(":", 1)[0]
        or os.environ.get("LANG", "")
    )
    code = locale.lower().partition(".")[0].partition("@")[0]
    return "ru" if code.replace("-", "_").split("_", 1)[0] == "ru" else "en"


@lru_cache(maxsize=2)
def _catalog(name: str) -> dict[str, str]:
    catalog = Path(__file__).with_name("assets") / name
    with catalog.open(encoding="utf-8") as source:
        return json.load(source)


def translate(message: str) -> str:
    """Translate a program-owned message or template."""
    if language() == "ru":
        return _catalog("messages.ru.json").get(message, message)
    return message


@lru_cache(maxsize=1)
def _diagnostic_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    patterns = []
    for source, translation in _catalog("diagnostics.ru.json").items():
        # A literal tmux format expression is part of the shell example.
        if "#{client_" in source:
            continue
        pieces = []
        has_fields = False
        for literal, field, _, _ in Formatter().parse(source):
            pieces.append(re.escape(literal))
            if field is not None:
                has_fields = True
                pieces.append(rf"(?P<{field}>.*?)")
        if has_fields:
            patterns.append((re.compile("".join(pieces), re.DOTALL), translation))
    return tuple(patterns)


def diagnostic(message: str) -> str:
    """Render a known application diagnostic without translating its arguments.

    Domain models and stored records can already contain rendered English
    diagnostics. Keep those records stable and translate only at the display
    boundary. Unrecognized messages and embedded OS details pass through.
    """
    if language() != "ru":
        return message
    catalog = _catalog("diagnostics.ru.json")
    if message in catalog:
        return catalog[message]
    for pattern, translation in _diagnostic_patterns():
        if match := pattern.fullmatch(message):
            return translation.format_map(match.groupdict())
    return status_label(message)


def status_label(value: object) -> str:
    """Localize a built-in state code when displayed, preserving its case."""
    text = str(value)
    if language() != "ru":
        return text
    label = _catalog("messages.ru.json").get(f"state:{text.lower()}", text)
    return label.upper() if text.isupper() else label


def policy_text(policy: ScanPolicy) -> str:
    """Present the components of a scan policy in the selected language."""
    return "; ".join(diagnostic(part) for part in policy.summary().split("; "))


def worker_policy_text(message: str) -> str:
    """Present the reasons recorded alongside an automatically chosen count."""
    if language() != "ru":
        return message
    count, separator, reasons = message.partition(" (")
    if count.isdecimal() and separator and reasons.endswith(")"):
        parts = (diagnostic(reason) for reason in reasons[:-1].split("; "))
        return f"{count} ({'; '.join(parts)})"
    return diagnostic(message)


def format_size(value: int | float, *, binary: bool = False, gnu: bool = False) -> str:
    """Format a byte count with compact Russian units in human-readable output."""
    from humanize import naturalsize

    text = naturalsize(value, binary=binary, gnu=gnu)
    if language() != "ru" or gnu:
        return text
    amount, sep, unit = text.rpartition(" ")
    return amount + sep + _SIZE_UNITS.get(unit, unit)


_SIZE_UNITS = {
    "Byte": "Б",
    "Bytes": "Б",
    "kB": "кБ",
    "MB": "МБ",
    "GB": "ГБ",
    "TB": "ТБ",
    "PB": "ПБ",
    "EB": "ЭБ",
    "ZB": "ЗБ",
    "YB": "ЙБ",
    "KiB": "КиБ",
    "MiB": "МиБ",
    "GiB": "ГиБ",
    "TiB": "ТиБ",
    "PiB": "ПиБ",
    "EiB": "ЭиБ",
    "ZiB": "ЗиБ",
    "YiB": "ЙиБ",
}
