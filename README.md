# Agentic Replica Readiness Platform

Production-shaped POC системы ИИ-агентов для подготовки источника данных к созданию реплики.

## Документы проекта

Основные md-файлы и их назначение:

| Файл | Для чего нужен |
| --- | --- |
| `PROJECT_RULES.md` | Главные правила реализации: Python, ports/adapters, границы агентов, LLM/tools/MCP/skills, state machine, trace, idempotency. |
| `ARCHITECTURE_GUIDE.md` | Человеческая карта архитектуры: зачем нужны `app`, `agents`, `shared`, что лежит внутри агента, чем tool отличается от adapter. |
| `AGENT_REQUIREMENTS.md` | Требования к агентам: роли, входы/выходы, state model, tools, LLM reasoning matrix, ограничения. |
| `WARP_INTEGRATION_REQUIREMENTS.md` | Контрактная модель интеграции с внешним WARP: readiness, remediation, `load_plan`, `warp_check_id`, критерии и параметры. |
| `FEATURE_BACKLOG.md` | Рабочая нарезка roadmap на конкретные фичи с acceptance criteria и статусами. |
| `SCENARIOS.md` | Бизнес-сценарии и объяснение текущего POC API. |
| `ROADMAP.md` | План развития от POC на заглушках до test/prod-ready агентной системы. |
| `MANAGEMENT_PRESENTATION_NOTES.md` | Бизнес-описание для руководства без лишней технической детализации. |
| `WORK_DONE.md` | История уже выполненной работы. |

Если документы расходятся, приоритет такой:

```text
PROJECT_RULES.md
→ ARCHITECTURE_GUIDE.md
→ AGENT_REQUIREMENTS.md
→ WARP_INTEGRATION_REQUIREMENTS.md
→ FEATURE_BACKLOG.md
→ ROADMAP.md
→ SCENARIOS.md
→ MANAGEMENT_PRESENTATION_NOTES.md
```

WARP в production является внешним сервисом другой команды. В нашем проекте для WARP остаются contracts, `WarpPort`, mock adapter для POC и HTTP adapter для real API.

## LLM provider

LLM подключается через общий порт:

```text
ReasoningService -> LlmPort -> GigaChatAdapter -> GigaChat API
```

Переменные окружения для GigaChat:

```text
GIGACHAT_AUTH_TOKEN=...
GIGACHAT_SCOPE=GIGACHAT_API_PERS
GIGACHAT_MODEL=GigaChat
GIGACHAT_EMBEDDINGS_MODEL=Embeddings
GIGACHAT_VERIFY_SSL=true
GIGACHAT_CA_BUNDLE_PATH=/path/to/ca.pem
GIGACHAT_TIMEOUT_SECONDS=60
```

`GIGACHAT_CA_BUNDLE_PATH` пригодится, когда перейдём на проверку через корпоративный сертификат.

Первый реализованный контур:

- `Coordinator Agent`;
- replaceable ports/adapters;
- mock WARP adapter;
- mock CR Manager;
- mock Replica Init;
- in-memory order repository;
- in-memory trace collector;
- FastAPI endpoints.

## Запуск

```bash
pip install -r requirements.txt
PYTHONPATH=src uvicorn app.main:app --reload
```

## Проверка

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Основные endpoints

```text
POST /order
GET  /order/{order_id}
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
```

## Пример создания заказа

```json
{
  "source_id": "SRC-123",
  "request": "загрузить реплику"
}
```
