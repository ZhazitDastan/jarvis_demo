# J.A.R.V.I.S — Архитектура системы

## Общая схема

```
Пользователь
    │
    ▼
[Tauri Desktop App]  ←──────────────────────────────┐
  React + Vite                                       │
  (D:\Diploma project\J.A.R.V.I.S)                  │
    │  HTTP / WebSocket                              │
    ▼                                                │
[FastAPI Backend]  :8000                             │
  api/server.py                                      │
    ├── Brain (GPT-4o-mini + function calling)       │
    ├── STT  (Vosk — speech-to-text)                 │
    ├── TTS  (Edge TTS — text-to-speech)             │
    ├── File Indexer (SQLite)                        │
    └── Commands (hot-reload плагины)  ──────────────┘
```

---

## Как это работает (шаг за шагом)

### Голосовой режим
```
1. Микрофон всегда слушает
2. Vosk слышит слово "Jarvis" (wake word)
3. TTS говорит "Да, сэр?"
4. Recorder записывает команду (до 12 секунд тишины)
5. Vosk транскрибирует аудио → текст
6. Brain.think(текст) → запрос к GPT-4o-mini
7. GPT решает: ответить текстом ИЛИ вызвать команду
8. Если команда → execute_command() → результат → GPT формирует ответ
9. TTS озвучивает ответ
10. 12 секунд followup (можно говорить без wake word)
```

### Чат-режим (через UI)
```
POST /chat  {"text": "...", "speak": false}
    → Brain.think() → GPT → команды при необходимости → ответ
```

---

## Файловая структура

```
jarvis_demo/
├── api/
│   ├── server.py          # FastAPI: все эндпоинты, VoiceRunner, State
│   └── files.py           # эндпоинты для файлового поиска
├── ai/
│   └── brain.py           # Brain: история, GPT запросы, tool_calls
├── commands/
│   ├── __init__.py        # автозагрузчик команд (hot-reload, параллельно)
│   ├── system/            # управление ПК
│   ├── apps/              # открытие/закрытие приложений
│   ├── search/            # поиск файлов
│   ├── web/               # браузер, Chrome
│   ├── vision/            # анализ экрана через GPT-4o Vision
│   ├── productivity/      # таймер, заметки, буфер обмена
│   └── fun/               # шутки, факты, цитаты
├── speech/
│   ├── STT/               # Vosk (speech-to-text), wake word, recorder
│   └── TTS/               # Edge TTS (Microsoft Azure Neural, бесплатно)
├── database/
│   └── files/
│       └── file_indexer.py  # SQLite индекс файлов (WAL mode)
├── config.py              # настройки, языковые профили, system prompt
├── .env                   # OPENAI_API_KEY (не в git)
├── launcher.config.json   # пути к фронту и Python (не в git)
├── launch.ps1             # запускает бэк + фронт
├── setup.ps1              # первичная настройка на новой машине
└── build_launcher_exe.ps1 # собирает JARVIS.exe из launch.ps1
```

---

## API эндпоинты

| Метод | Путь | Что делает |
|-------|------|-----------|
| GET | `/status` | статус, язык, wake word |
| GET | `/ws` | WebSocket — события в реальном времени |
| POST | `/jarvis/start` | запустить голосовой цикл |
| POST | `/jarvis/stop` | остановить голосовой цикл |
| POST | `/chat` | отправить текстовую команду |
| GET | `/chat/history` | история чата |
| POST | `/chat/reset` | очистить историю |
| GET | `/settings` | получить настройки |
| PATCH | `/settings` | изменить настройки (язык, модель, голос...) |
| GET | `/microphones` | список микрофонов |
| PATCH | `/microphone/active` | сменить микрофон |
| GET | `/neural` | статус STT / TTS моделей |
| GET | `/commands` | список доступных команд |
| GET | `/resources` | CPU / RAM / GPU загрузка |
| GET | `/logs` | последние логи |
| DELETE | `/logs` | очистить логи |

### WebSocket события (от сервера к UI)
```json
{"type": "status",      "value": "idle|listening|thinking|speaking"}
{"type": "wake_word"}
{"type": "transcribed", "text": "текст команды"}
{"type": "response",    "text": "ответ Jarvis"}
{"type": "error",       "message": "описание ошибки"}
```

---

## Команды

### Система (commands/system/)
| Команда | Что делает |
|---------|-----------|
| `get_date` | текущая дата и время |
| `lock_pc` | заблокировать компьютер |
| `shutdown_pc` | выключить / перезагрузить |
| `screenshot` | сделать скриншот |
| `show_desktop` | свернуть все окна |
| `system_info` | CPU, RAM, диск |
| `network_info` | IP, скорость сети |
| `battery_status` | заряд батареи |
| `volume` | изменить громкость |
| `brightness` | изменить яркость |
| `wifi_control` | вкл/выкл Wi-Fi |
| `bluetooth_control` | вкл/выкл Bluetooth |
| `night_light` | ночной режим |
| `do_not_disturb` | режим "не беспокоить" |
| `set_wallpaper` | сменить обои |
| `empty_trash` | очистить корзину |
| `task_manager` | открыть диспетчер задач |
| `open_settings` | открыть настройки Windows |
| `show_overlay` | показать оверлей |

### Приложения (commands/apps/)
| Команда | Что делает |
|---------|-----------|
| `open_app` | открыть любое приложение по имени |
| `close_app` | закрыть приложение |
| `open_vscode` | открыть VS Code |
| `open_telegram` | открыть Telegram |
| `open_spotify` | открыть Spotify |
| `window_control` | maximize / minimize / close / snap окна |

### Поиск файлов (commands/search/)
| Команда | Что делает |
|---------|-----------|
| `search_by_name` | поиск файла по имени (SQLite индекс) |
| `search_by_content` | поиск по содержимому файла |
| `open_file_result` | открыть файл из результатов поиска |
| `next_results` | следующие результаты |
| `open_quick_folder` | открыть часто используемую папку |
| `rebuild_index` | перестроить индекс файлов |
| `file_stats` | статистика индекса |

### Браузер / Веб (commands/web/)
| Команда | Что делает |
|---------|-----------|
| `search_youtube` | поиск на YouTube |
| `open_wikipedia` | открыть статью в Wikipedia |
| `translate` | перевести текст |
| `chrome_navigate` | перейти по URL в Chrome |
| `chrome_tab` | управление вкладками Chrome |
| `chrome_zoom` | масштаб страницы |
| `chrome_open_url` | открыть URL |
| `chrome_tools` | инструменты разработчика |

### Зрение / Экран (commands/vision/)
| Команда | Что делает |
|---------|-----------|
| `describe_screen` | описать что на экране (GPT-4o Vision) |
| `read_text_from_screen` | прочитать текст с экрана (OCR) |
| `analyze_active_window` | анализ активного окна |
| `check_errors_on_screen` | найти ошибки на экране |
| `translate_screen_text` | перевести текст с экрана |
| `solve_math_from_screen` | решить задачу с экрана |
| `summarize_screen` | краткое изложение страницы |
| `count_objects_on_screen` | посчитать объекты на экране |
| `find_and_click` | найти кнопку и нажать |
| `read_clipboard_image` | прочитать изображение из буфера |
| `write_content` | написать/напечатать текст |
| `whats_changed` | что изменилось на экране |
| `fill_form_from_screen` | заполнить форму |

### Продуктивность (commands/productivity/)
| Команда | Что делает |
|---------|-----------|
| `set_timer` | установить таймер |
| `create_note` | создать заметку |
| `clipboard` | работа с буфером обмена |

### Развлечения (commands/fun/)
| Команда | Что делает |
|---------|-----------|
| `tell_joke` | рассказать анекдот |
| `tell_fact` | рассказать факт |
| `tell_quote` | цитата дня |

---

## Как добавить новую команду

Создать файл в любой подпапке `commands/`, например `commands/system/my_command.py`:

```python
COMMAND_NAME = "my_command"
DESCRIPTION  = "Описание команды для GPT"
PARAMETERS   = {
    "param1": {"type": "string", "description": "..."},
}
REQUIRED = ["param1"]

def handler(param1: str) -> str:
    # логика команды
    return "Готово."
```

Команда подхватится автоматически (hot-reload) — перезапуск не нужен.

---

## Модели

| Компонент | Модель | Размер |
|-----------|--------|--------|
| LLM | GPT-4o-mini (OpenAI API) | облако |
| STT (RU) | Vosk small-ru-0.22 | ~45 MB |
| STT (EN) | Vosk en-us-0.22-lgraph | ~128 MB |
| TTS | Edge TTS (Microsoft Neural) | облако, бесплатно |
| Vision | GPT-4o (скриншот → base64) | облако |

---

## Запуск

### Первый раз на новой машине
```powershell
.\setup.ps1          # настройка, pip install, создание launcher.config.json
```

### Ежедневный запуск
```
Двойной клик на JARVIS.exe  (или ярлык на рабочем столе)
```

### Сборка JARVIS.exe
```powershell
.\build_launcher_exe.ps1
```

### Ручной запуск (разработка)
```powershell
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload
```