# Процесс выпуска

Релизы disktide используют зафиксированные зависимости, собирают два стандартных формата Python-дистрибутива, проверяют чистую установку и публикуются в PyPI через Trusted Publishing. Сценарий выпуска находится в .github/workflows/release.yml.

После добавления необязательного расширения C выпуск включает **матрицу wheel-пакетов и sdist**, а не один универсальный wheel плюс sdist.

## Условия выпуска

1. Версия совпадает в pyproject.toml, src/disktide/__init__.py и uv.lock.
2. uv sync --locked проходит без изменения uv.lock.
3. CI-матрица Python 3.10–3.14 завершилась успешно.
4. Минимальная среда укладывается в 20 runtime-дистрибутивов и 20 MiB, без сторонних нативных расширений. Собственный необязательный ускоритель disktide проверяется отдельно через tool/check_dependency_budget.py.
5. Из core wheel проходят doctor, doctor --json, небольшое сканирование и smoke-проверка периодического watch.
6. Отдельная чистая установка disktide[watch] обнаруживает нативный backend и проходит watch --events.
7. Полный набор проверок проходит в зафиксированной основной среде и в окружении Python 3.13 с дополнением watch.

## Локальная сборка кандидата

    uv sync --locked
    .venv/bin/python -m pytest -q
    uv sync --locked --python 3.13 --extra watch
    .venv/bin/python -m pytest -q
    uv sync --locked
    uv build --python 3.13
    .venv/bin/python tool/verify_distribution.py

Python 3.13 соответствует smoke-средам. Обычная сборка из checkout на Python 3.12 создаёт cp312 wheel, который те среды не используют. Если система задаёт CC=icc, используйте CC=gcc: hook сначала пробует переменную CC, а объект icc может связать Intel runtime, отсутствующий в опубликованных пакетах.

После изменения исходной версии обновите установленную рабочую копию и проверьте версии всех команд:

    expected="$(uv run python -c 'from fs_monitor import __version__; print(__version__)')"
    uv tool install --force .
    test "$(disktide --version | awk '{print $NF}')" = "$expected"
    test "$(sizetrail --version | awk '{print $NF}')" = "$expected"
    test "$(fsmonitor --version | awk '{print $NF}')" = "$expected"
    test "$(fsmonitor-cli --version | awk '{print $NF}')" = "$expected"
    uv tool list

Wheel и sdist проверяются в чистых окружениях, не в среде разработки. Подробный smoke-сценарий со всеми вариантами установки приведён в [английском оригинале](release-process.md#local-candidate-build). Проверяются wheel, sdist с компилятором и без него, вариант с watch, doctor --json, оба режима watch, бюджет зависимостей и активный scanner backend.

Локальный uv build создаёт wheel с тегом linux_x86_64 или macosx_*; он подходит для локального smoke-теста, но не публикации. PyPI-пакеты строятся матрицей cibuildwheel. Путь без компилятора можно проверить через CC=/bin/false uv build --wheel; установка sdist должна использовать запасной Python backend.

## Матрица wheel-пакетов

Расширение disktide/scanner/_scanfast собирается отдельно для каждой версии интерпретатора и платформы. cibuildwheel собирает CPython 3.10–3.14:

| Runner | Пакеты |
|---|---|
| ubuntu-latest | manylinux_x86_64, musllinux_x86_64 |
| ubuntu-latest + QEMU | manylinux_aarch64, musllinux_aarch64 |
| macos-15 | macosx_arm64 |
| macos-15-intel | macosx_x86_64 |

Каждый wheel проверяется импортом disktide.scanner.accel.ACCEL_BACKEND с требованием native. Hook намеренно допускает отсутствие компилятора; без этой проверки можно опубликовать платформенный пакет без расширения. Локальный linux_x86_64 не подходит для PyPI; cibuildwheel преобразует его в manylinux через auditwheel repair. Расширение связывается только с libc.

Универсальный py3-none-any wheel больше не публикуется: версия выпускает либо один чистый wheel, либо набор платформенных пакетов; для остальных платформ используется sdist. Он пересобирает расширение при наличии компилятора и использует запасной вариант Python без него. CI проверяет обе ветки, чтобы запасной путь не перестал работать.

Сборки aarch64 используют QEMU и добавляют около десяти минут CI. При появлении runner ubuntu-24.04-arm его можно использовать вместо эмуляции.

## Автоматический выпуск

Публикация тега v* запускает workflow:

1. Версия тега должна совпасть с pyproject.toml (например, v0.3.0 для 0.3.0); иначе сборка не начинается.
2. Собираются wheel-пакеты матрицы и sdist; проверяется нативный backend.
3. tool/verify_distribution.py проверяет wheel и sdist.
4. Проверяются чистая установка, doctor, бюджет зависимостей и backend в wheel, sdist с компилятором и sdist без него.
5. Создаются контрольные суммы SHA-256 и SBOM формата CycloneDX.
6. Для публичного репозитория создаются GitHub-аттестации происхождения сборки. В приватном репозитории шаг пропускается, поскольку требует Enterprise Cloud.
7. Загружаются неизменяемые артефакты workflow.
8. Wheel и sdist публикуются через защищённое окружение pypi.

До первого тега необходимо настроить PyPI Trusted Publishing для workflow release.yml и защитить окружение pypi.

## Проверка после публикации

После индексации версии в PyPI проверьте способы установки в чистой оболочке:

    uvx disktide --version
    uvx disktide doctor
    uv tool install --force disktide
    disktide --version
    pipx install --force disktide
    pipx run disktide doctor --json

На платформе, входящей в матрицу, uvx disktide doctor должен сообщать Scanner: native (_scanfast): это подтверждает, что выбрался нужный wheel. Сверьте контрольные суммы с SHA256SUMS. Сохраните SBOM и ссылки на аттестации (если репозиторий был публичен при сборке) вместе с примечаниями выпуска.
