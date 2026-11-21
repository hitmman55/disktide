"""Exercise Russian localization through the CLI and Textual entry points."""

from __future__ import annotations

import ast
import json
import os
import select
import struct
import subprocess
import sys
import time
from pathlib import Path
from string import Formatter

import pytest

from disktide.i18n import diagnostic, language


def test_every_literal_translation_has_a_catalog_entry() -> None:
    project = Path(sys.modules["disktide"].__file__).parent
    catalog = project / "assets" / "messages.ru.json"
    messages = json.loads(catalog.read_text(encoding="utf-8"))
    missing = []
    for path in project.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id != "translate" or not call.args:
                continue
            argument = call.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                if argument.value not in messages:
                    missing.append(
                        (str(path.relative_to(project)), call.lineno, argument.value)
                    )
    assert not missing


@pytest.fixture
def isolated_env(tmp_path: Path) -> dict[str, str]:
    return {
        **os.environ,
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_DATA_HOME": str(tmp_path / "data"),
        "DISKTIDE_LANG": "ru",
        "LC_ALL": "C.UTF-8",
    }


def run_cli(env: dict[str, str], *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "disktide", *arguments],
        env=env,
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )


def test_catalog_keeps_every_template_field() -> None:
    assets = Path(sys.modules["disktide"].__file__).with_name("assets")
    formatter = Formatter()
    for name in ("messages.ru.json", "diagnostics.ru.json"):
        messages = json.loads((assets / name).read_text(encoding="utf-8"))
        for original, russian in messages.items():
            assert russian.strip()
            assert {
                field
                for _, field, _, _ in formatter.parse(original)
                if field is not None
            } == {
                field
                for _, field, _, _ in formatter.parse(russian)
                if field is not None
            }, original


def test_locale_override_and_literal_system_error(monkeypatch) -> None:
    monkeypatch.setenv("LC_ALL", "ru_RU.UTF-8")
    monkeypatch.delenv("DISKTIDE_LANG", raising=False)
    assert language() == "ru"
    error = "Permission denied"
    assert diagnostic(error) == error
    assert (
        diagnostic(f"stat probe failed: {error}")
        == f"вызов stat завершился ошибкой: {error}"
    )
    monkeypatch.setenv("DISKTIDE_LANG", "en")
    assert language() == "en"


def test_cli_help_and_error_use_russian_and_keep_flags(isolated_env) -> None:
    root_help = run_cli(isolated_env, "--help")
    assert root_help.returncode == 0, root_help.stderr
    for heading in ("Использование:", "Параметры:", "Команды:"):
        assert heading in root_help.stdout
    assert "cleanup" in root_help.stdout
    nested = run_cli(isolated_env, "cleanup", "quarantine", "rebuild", "--help")
    assert nested.returncode == 0, nested.stderr
    assert "Пересоздать журнал" in nested.stdout
    assert "--json" in nested.stdout
    invalid = run_cli(isolated_env, "scan", "--workers", "0")
    assert invalid.returncode == 2
    assert "Недопустимое значение" in invalid.stderr
    assert "--workers" in invalid.stderr


def test_scan_localization_preserves_json_and_unicode_paths(
    isolated_env, tmp_path
) -> None:
    root = tmp_path / "Каталог теста"
    root.mkdir()
    (root / "файл.txt").write_bytes(b"hello")
    russian = run_cli(isolated_env, "scan", str(root), "--workers", "1")
    assert russian.returncode == 0, russian.stderr
    assert "Сканирование" in russian.stdout
    assert "Файлов: 1" in russian.stdout

    json_args = ("scan", str(root), "--workers", "1", "--json")
    reports = []
    for locale in ("ru", "en"):
        result = run_cli({**isolated_env, "DISKTIDE_LANG": locale}, *json_args)
        assert result.returncode == 0, result.stderr
        reports.append(json.loads(result.stdout))
    russian, english = reports
    assert russian.keys() == english.keys()
    for key in ("path", "metric", "status", "totals", "coverage", "policy"):
        assert russian[key] == english[key], key


def test_cleanup_preview_distinguishes_risk_from_action(isolated_env, tmp_path) -> None:
    root = tmp_path / "Данные"
    cache = root / "__pycache__"
    cache.mkdir(parents=True)
    item = cache / "fixture.pyc"
    item.write_bytes(b"fixture")

    plan = run_cli(isolated_env, "cleanup", str(root), "--workers", "1")
    assert plan.returncode == 0, plan.stderr
    assert "[низкий риск/" in plan.stdout
    assert "· с восстановлением" in plan.stdout
    assert "каталог байткода Python" in plan.stdout
    assert item.read_bytes() == b"fixture"


@pytest.mark.skipif(sys.platform != "linux", reason="Ubuntu pseudo-terminal smoke test")
def test_textual_modes_and_confirmation_at_eighty_columns(
    isolated_env, tmp_path
) -> None:
    import errno
    import fcntl
    import pty
    import termios

    config = Path(isolated_env["XDG_CONFIG_HOME"]) / "disktide"
    config.mkdir(parents=True)
    (config / "config.toml").write_text("[ui]\nshow_cleanup = true\n", encoding="utf-8")
    root = tmp_path / "Данные"
    root.mkdir()
    (root / "проверка.txt").write_text("проверка", encoding="utf-8")

    env = {**isolated_env, "TERM": "xterm-256color", "DISKTIDE_CELL_ASPECT": "2"}
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 80, 0, 0))
    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "disktide"],
            env=env,
            cwd=root,
            stdin=slave,
            stdout=slave,
            stderr=slave,
        )
    finally:
        os.close(slave)

    frames = bytearray()

    def read_frame() -> bool:
        if not select.select([master], [], [], 0.1)[0]:
            return True
        try:
            frame = os.read(master, 65536)
        except OSError as exc:
            if exc.errno != errno.EIO:
                raise
            return False
        frames.extend(frame)
        return bool(frame)

    def expect(word: str) -> None:
        start = len(frames)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and read_frame():
            if word.encode() in frames[start:]:
                return
        pytest.fail(f"{word!r} missing: {bytes(frames[start:])[-3000:]!r}")

    try:
        expect("Интерактивный анализ")
        os.write(master, b"\r")
        expect("Подробности")
        os.write(master, b"\x10")
        expect("Поиск команд")
        os.write(master, b"zzzz")
        expect("Совпадений нет")
        os.write(master, b"\x1b")
        expect("Подробности")
        for key, label in (
            (b"2", "Центр мониторинга"),
            (b"3", "Блочные устройства"),
            (b"4", "Кандидатов:"),
            (b",", "Сведения о системе"),
            (b"\x1b", "Кандидатов:"),
            (b"q", "Выйти из DiskTide?"),
        ):
            os.write(master, key)
            expect(label)
        os.write(master, b"y")
        deadline = time.monotonic() + 8
        while process.poll() is None and time.monotonic() < deadline and read_frame():
            continue
        assert process.wait(timeout=1) == 0
        assert b"Traceback (most recent call last)" not in frames
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        os.close(master)
