"""Russian rendering for the Click help and diagnostics used by DiskTide."""

from __future__ import annotations

import inspect
import re
from collections.abc import Sequence

import click
from click.utils import make_default_short_help

from disktide.i18n import diagnostic, language, translate


class _Formatter(click.HelpFormatter):
    def write_usage(self, prog: str, args: str = "", prefix: str | None = None) -> None:
        if prefix is None and language() == "ru":
            prefix = translate("Usage: ")
            args = (
                args.replace("[OPTIONS]", "[ПАРАМЕТРЫ]")
                .replace("COMMAND", "КОМАНДА")
                .replace("[ARGS]", "[АРГУМЕНТЫ]")
            )
        super().write_usage(prog, args, prefix)

    def write_text(self, text: str) -> None:
        super().write_text(translate(text))

    def write_heading(self, heading: str) -> None:
        super().write_heading(translate(heading))

    def write_dl(
        self, rows: Sequence[tuple[str, str]], col_max: int = 30, col_spacing: int = 2
    ) -> None:
        if language() == "ru":
            localized = []
            for name, description in rows:
                if name.startswith("-"):
                    name = re.sub(
                        r"(?<=\s)(INTEGER RANGE|FLOAT RANGE|INTEGER|FLOAT|TEXT)(?=\s|$)",
                        lambda match: translate(match[0]),
                        name,
                    )
                    description, sep, annotations = description.rpartition("  [")
                    if sep:
                        description = (
                            translate(description)
                            + sep
                            + _help_annotations(annotations)
                        )
                    else:
                        description = translate(annotations)
                localized.append((name, description))
            rows = localized
        super().write_dl(rows, col_max, col_spacing)


def _help_annotations(text: str) -> str:
    return re.sub(
        r"(^|; )(default:|env var:|required(?=[;\]]))",
        lambda match: match[1] + translate(match[2]),
        text,
    )


class _Context(click.Context):
    formatter_class = _Formatter


class _LocalizedHelp:
    context_class = _Context

    def get_short_help_str(self, limit: int = 45) -> str:
        if language() == "ru" and not self.deprecated:
            if self.short_help:
                return translate(inspect.cleandoc(self.short_help)).strip()
            if self.help:
                text = inspect.cleandoc(self.help).partition("\f")[0]
                return make_default_short_help(translate(text), limit).strip()
        return super().get_short_help_str(limit)


class LocalizedCommand(_LocalizedHelp, click.Command):
    pass


class LocalizedGroup(_LocalizedHelp, click.Group):
    command_class = LocalizedCommand

    def main(self, *args, standalone_mode: bool = True, **kwargs):
        if not standalone_mode or language() != "ru":
            return super().main(*args, standalone_mode=standalone_mode, **kwargs)
        try:
            status = super().main(*args, standalone_mode=False, **kwargs)
        except click.ClickException as exc:
            _show_error(exc)
            status = exc.exit_code
        except click.Abort:
            click.echo(translate("Aborted!"), err=True)
            status = 1
        # DiskTide callbacks return None or use ctx.exit() explicitly.
        raise SystemExit(status)


LocalizedGroup.group_class = LocalizedGroup


def _show_error(exc: click.ClickException) -> None:
    # Click 8.4 uses a UsageError subclass to show a full help page for
    # empty command groups. The page is already localized by _Formatter.
    no_args = getattr(click.exceptions, "NoArgsIsHelpError", None)
    if no_args is not None and isinstance(exc, no_args):
        exc.show()
        return
    ctx = exc.ctx if isinstance(exc, click.UsageError) else None
    color = exc.show_color
    if ctx is not None:
        color = ctx.color
        click.echo(f"{ctx.get_usage()}\n", err=True, color=color)
        if ctx.command.get_help_option(ctx) is not None:
            option = max(ctx.command.get_help_option_names(ctx), key=len)
            hint = translate("Try '{command} {option}' for help.")
            click.echo(
                hint.format(command=ctx.command_path, option=option) + "\n",
                err=True,
                color=color,
            )
    detail = diagnostic(exc.format_message())
    if isinstance(exc, click.UsageError):
        detail = _usage_error(detail)
    click.echo(
        translate("Error: {message}").format(message=detail), err=True, color=color
    )


_ERROR_PATTERNS = (
    (r"No such option: (.+)", "No such option: {value}"),
    (r"No such command (.+)", "No such command {value}"),
    (r"Missing argument (.+)", "Missing argument {value}"),
    (r"Missing option (.+)", "Missing option {value}"),
    (r"Missing parameter (.+)", "Missing parameter {value}"),
    (r"Got unexpected extra argument(?:s)? (.+)", "Unexpected arguments: {value}"),
    (r"Option (.+) requires an argument\.", "Option {value} requires an argument."),
)


def _usage_error(message: str) -> str:
    if match := re.fullmatch(r"Invalid value for (.+?): (.+)", message, re.DOTALL):
        return translate("Invalid value for {option}: {value}").format(
            option=match[1], value=_invalid_value(diagnostic(match[2]))
        )
    for pattern, template in _ERROR_PATTERNS:
        if match := re.fullmatch(pattern, message, re.DOTALL):
            return translate(template).format(value=match[1])
    return message


def _invalid_value(message: str) -> str:
    if match := re.fullmatch(
        r"(Path|File|Directory) (.+) "
        r"(does not exist|is a file|is a directory|is not readable|is not writable|is not executable)\.",
        message,
        re.DOTALL,
    ):
        return f"{translate(match[1])} {match[2]} {translate(match[3])}."
    if match := re.fullmatch(r"(.+) is not a valid (integer|float|boolean)\.", message):
        return translate("{value} is not a valid {type}.").format(
            value=match[1], type=translate(match[2])
        )
    if match := re.fullmatch(r"(.+) is not one of (.+)\.", message):
        return translate("{value} is not one of {choices}.").format(
            value=match[1], choices=match[2]
        )
    if match := re.fullmatch(r"(.+) is not in the range (.+)\.", message):
        return translate("{value} is not in the range {range}.").format(
            value=match[1], range=match[2]
        )
    return message
