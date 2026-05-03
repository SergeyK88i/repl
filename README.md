# Agentic Replica Readiness Platform

Production-shaped POC системы ИИ-агентов для подготовки источника данных к созданию реплики.

## Документы проекта

Основные md-файлы и их назначение:

| Файл | Для чего нужен |
| --- | --- |
| `PROJECT_RULES.md` | Главные правила реализации: Python, ports/adapters, границы агентов, LLM/tools/MCP/skills, state machine, trace, idempotency. |
| `ARCHITECTURE_GUIDE.md` | Человеческая карта архитектуры: зачем нужны `app`, `agents`, `shared`, что лежит внутри агента, чем tool отличается от adapter. |
| `AGENT_REQUIREMENTS.md` | Требования к агентам: роли, входы/выходы, state model, tools, LLM reasoning по агентам, ограничения. |
| `CR_MANAGER_REQUIREMENTS.md` | Контрактное описание CR Manager: task lifecycle, Jira/CR, remediation, tools, LLM reasoning, trace и idempotency. |
| `WARP_INTEGRATION_REQUIREMENTS.md` | Контрактная модель интеграции с внешним WARP: readiness, remediation, `load_plan`, `warp_check_id`, критерии и параметры. |
| `FEATURE_BACKLOG.md` | Рабочая нарезка roadmap на конкретные фичи с acceptance criteria и статусами. |
| `SCENARIOS.md` | Бизнес-сценарии и объяснение текущего POC API. |
| `ROADMAP.md` | План развития от POC на заглушках до test/prod-ready агентной системы. |
| `MANAGEMENT_PRESENTATION_NOTES.md` | Бизнес-описание для руководства без лишней технической детализации. |

`agents.md` — исходная черновая постановка. Она полезна как контекст, но не является главным источником правил, если расходится с документами ниже.

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
- `CR Manager Agent` как отдельный модуль;
- replaceable ports/adapters;
- mock WARP adapter;
- in-process Coordinator -> CR Manager adapter;
- mock Jira adapter;
- HTTP Jira adapter;
- lightweight fake Jira API for local development;
- mock WARP remediation adapter для CR Manager;
- mock Replica Init;
- in-memory order repository;
- in-memory CR Manager task repository;
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
POST /cr-manager/task
GET  /cr-manager/task/{task_id}
GET  /trace/{correlation_id}
GET  /console
GET  /product
GET  /internal-delivery-status-2026
```

## Fake Jira

Лёгкая fake Jira нужна для локальной проверки HTTP-контракта без установки настоящей Jira:

```bash
PYTHONPATH=src python3 -m uvicorn fakes.jira.app:app --port 9001
JIRA_ADAPTER_PROFILE=http JIRA_BASE_URL=http://127.0.0.1:9001 JIRA_BROWSE_URL=http://127.0.0.1:9001 PYTHONPATH=src python3 -m uvicorn app.main:app --port 8000
```

Fake Jira поддерживает минимальный набор Jira-like endpoints:

```text
POST /rest/api/3/issue
GET  /rest/api/3/issue/{issueIdOrKey}
POST /rest/api/3/issue/{issueIdOrKey}/comment
GET  /rest/api/3/issue/{issueIdOrKey}/transitions
POST /rest/api/3/issue/{issueIdOrKey}/transitions
```

## Пример создания заказа

```json
{
  "source_id": "SRC-123",
  "request": "загрузить реплику"
}
```
