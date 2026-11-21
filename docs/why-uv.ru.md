# Почему uv?

В инструкциях по установке DiskTide сначала предлагается [uv](https://docs.astral.sh/uv/). Здесь объясняется, что это такое, почему он рекомендуется и как его установить.

## Что такое uv

uv — менеджер пакетов и проектов Python от Astral. Это одна программа, написанная на Rust; она заменяет многие привычные сценарии pip, venv, pipx и pyenv. Кроме того, uv может сам загрузить интерпретатор Python, поэтому подходит для машины, где нет подходящей версии Python.

## Почему DiskTide рекомендует uv

Команда `uv tool install disktide` устанавливает DiskTide в отдельное изолированное окружение и добавляет команду `disktide` в PATH. Благодаря этому:

- системный Python и виртуальные окружения других проектов не затрагиваются;
- окружение не нужно активировать: достаточно запустить `disktide`;
- позднее программу можно обновить через `uv tool upgrade` и удалить через `uv tool uninstall`;
- разрешение зависимостей и установка проходят быстрее, чем через pip.

`uvx disktide` запускает программу вообще без установки.

## Установка uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux и macOS
brew install uv                                   # macOS с Homebrew
pipx install uv                                   # если Python уже установлен
pip install uv                                    # то же без pipx
```

В Windows (PowerShell) используйте следующую команду. Сама DiskTide пока не поддерживает Windows; команда устанавливает только uv:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Проверьте установку командой `uv --version`. Если после `uv tool install` оболочка не находит `disktide`, выполните `uv tool update-shell` и откройте новую оболочку. Исполняемые файлы uv обычно находятся в `~/.local/bin`.

## Основные команды

```bash
uv tool install disktide           # установить из PyPI
uv tool install 'disktide[watch]'  # установить дополнение Linux inotify
uvx disktide                       # один запуск без установки
uv tool upgrade disktide           # установить новую версию
uv tool list                       # показать установленные программы
uv tool uninstall disktide         # удалить
uv tool install .                  # установить из рабочей копии
uv tool install --reinstall .      # повторно установить после git pull
```

## uv не обязателен

pip тоже работает. См. [README](../README.ru.md) для установки через pip. uv — рекомендация, а не обязательное требование. Полная документация uv опубликована на <https://docs.astral.sh/uv/>.
