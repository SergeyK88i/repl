# Архитектурная карта проекта

Этот файл нужен как быстрый справочник по структуре проекта: где что лежит, зачем нужна каждая папка и как агенты должны взаимодействовать между собой.

Основные правила разработки остаются в `PROJECT_RULES.md`.
Требования к агентам — в `AGENT_REQUIREMENTS.md`.
План развития — в `ROADMAP.md`.
Сценарии процесса — в `SCENARIOS.md`.

## Общая структура

```text
src/
  app/
  agents/
  shared/
```

### `src/app/`

`app` — это слой сборки приложения.

Он отвечает не за бизнес-логику, а за то, как система запускается:

- создать FastAPI-приложение;
- подключить routes агентов;
- загрузить настройки;
- собрать dependency container;
- выбрать mock или real adapters;
- отдать временный POC UI.

Пример:

```text
src/app/
  main.py
  config/
    settings.py
    container.py
  static/
    agent_console.html
```

`app/main.py` подключает агентов к FastAPI.

`app/config/settings.py` хранит настройки:

```text
ADAPTER_PROFILE=mock|real
DATABASE_URL=...
WARP_BASE_URL=...
JIRA_BASE_URL=...
MAX_ATTEMPTS=3
```

`app/config/container.py` собирает зависимости:

```text
WarpPort -> MockWarpAdapter
CrManagerPort -> MockCrManagerAdapter
OrderRepositoryPort -> InMemoryOrderRepository
```

Позже тот же container сможет выбрать реальные адаптеры:

```text
WarpPort -> HttpWarpAdapter
CrManagerPort -> HttpCrManagerAdapter
OrderRepositoryPort -> PostgresOrderRepository
```

Важно: `app` не должен содержать бизнес-логику агентов.

## `src/agents/`

`agents` — это папка с агентами системы.

Каждый агент живёт в своей папке:

```text
src/agents/
  coordinator/
  requirements/
  cr_manager/
  ep_coordinator/
  warp/
```

Такой подход нужен, чтобы разные команды могли работать независимо:

- команда Coordinator работает в `src/agents/coordinator/`;
- команда Requirements Agent работает в `src/agents/requirements/`;
- команда CR Manager работает в `src/agents/cr_manager/`;
- команда EP Coordinator работает в `src/agents/ep_coordinator/`.

Позже любого агента можно вынести в отдельный сервис, если его границы останутся чистыми.

## Внутренняя структура агента

Целевая структура агента:

```text
src/agents/{agent_name}/
  api/
  application/
  domain/
  ports/
  adapters/
  tools/
  skills/
```

Папка `tools/` нужна только тем агентам, у которых есть LLM-слой или планируется LLM-слой.

Например, у CR Manager она нужна почти точно.
У Coordinator на первом этапе её может не быть, потому что Coordinator лучше держать максимально детерминированным.

Папка `skills/` тоже нужна только LLM-агентам. Она хранит инструкции и playbooks для reasoning-слоя, но не заменяет кодовые правила, state machine и contracts.

## `api/`

`api` содержит HTTP endpoints агента.

Пример для CR Manager:

```text
POST /cr-manager/task
GET  /cr-manager/task/{task_id}
```

Задача `api`:

- принять HTTP-запрос;
- провалидировать request schema;
- вызвать application service;
- вернуть response schema.

`api` не должен содержать сложный workflow.

## `application/`

`application` содержит сценарии работы агента.

Например, workflow CR Manager:

```text
1. принять remediation-поручение от Coordinator;
2. создать Jira/CR;
3. запросить remediation-инструкции у WARP;
4. выбрать tools или connectors;
5. выполнить исправления;
6. сделать self-check через WARP;
7. отправить callback Coordinator.
```

Этот слой знает бизнес-сценарий, но не знает деталей конкретной Jira, HTTP-клиента, Postgres или внешнего API.

## `domain/`

`domain` содержит бизнес-модель агента.

Пример:

```text
domain/
  task.py
  statuses.py
  state_machine.py
  remediation_execution.py
```

Здесь живут:

- статусы;
- правила переходов;
- доменные модели;
- доменные ошибки;
- бизнес-инварианты.

`domain` не должен зависеть от FastAPI, Jira, Postgres, HTTP или LLM.

## `ports/`

`ports` содержит интерфейсы, через которые агент обращается наружу.

Порт отвечает на вопрос:

```text
"Что агенту нужно уметь вызвать?"
```

Но порт не отвечает на вопрос:

```text
"Как именно это реализовано?"
```

Пример для CR Manager:

```text
ports/
  jira.py
  warp.py
  connector.py
  coordinator_callback.py
  task_repository.py
  trace.py
```

CR Manager знает, что ему нужен `JiraPort`.
Но он не знает, будет это mock Jira, Jira Cloud, внутренняя Jira или тестовый сервер.

## `adapters/`

`adapters` содержит конкретные реализации портов.

Пример:

```text
adapters/
  mock/
    jira.py
    warp.py
    connectors.py
  mcp/
    jira.py
    confluence.py
  http/
    warp.py
    coordinator_callback.py
  jira/
    jira_cloud.py
  persistence/
    postgres_tasks.py
```

Mock adapter используется для POC и тестов.

Real adapter используется для настоящих API.

MCP adapter используется, если внешний инструмент подключён через MCP server. Например:

```text
JiraPort -> JiraMcpAdapter -> Jira MCP server -> Jira API
```

Для application-слоя это всё равно обычный adapter за обычным port.

Главное правило:

```text
Замена mock adapter на real adapter не должна требовать переписывания application/domain логики.
```

## `tools/`

`tools` содержит безопасные действия, которые может вызывать LLM-слой агента.

LLM не должен напрямую ходить в Jira, WARP, БД или внешние API.

Правильная цепочка:

```text
LLM reasoning
→ typed tool
→ port
→ adapter
→ external system
```

Пример для CR Manager:

```text
tools/
  create_jira_issue.py
  get_warp_remediation.py
  run_connector.py
  run_warp_self_check.py
  notify_coordinator.py
```

Пример выполнения:

```text
CR Manager LLM решил: "нужно создать CR"
→ вызывает tool create_jira_issue
→ tool валидирует вход
→ вызывает JiraPort.create_issue(...)
→ JiraCloudAdapter создаёт задачу в Jira
→ trace фиксирует событие
```

Tools нужны для безопасности:

- валидируют вход;
- ограничивают доступные действия;
- скрывают детали внешних API;
- не дают LLM менять состояние напрямую;
- пишут trace там, где это нужно.

Если tool работает через MCP, цепочка остаётся контролируемой:

```text
LLM reasoning
→ typed tool
→ port
→ MCP adapter
→ MCP server
→ external system
```

MCP server не должен становиться обходом permissions, validation, trace или state machine.

## `skills/`

`skills` содержит инструкции и playbooks для LLM-слоя агента.

Пример для CR Manager:

```text
skills/
  remediation.md
  escalation.md
  jira_commenting.md
```

Skill может объяснять:

- как читать remediation-инструкции WARP;
- как выбирать connector;
- как формулировать комментарий в Jira;
- когда запускать self-check;
- когда готовить эскалацию человеку.

Skill не должен:

- менять статус предзаказа;
- объявлять источник READY;
- обходить WARP;
- обходить typed tools;
- хранить секреты;
- заменять domain rules или application workflow.

Простая формула:

```text
PROJECT_RULES.md / domain logic = правила системы
skills/ = инструкции для LLM, как действовать внутри роли
```

## `src/shared/`

`shared` содержит только то, что действительно общее для нескольких агентов.

Пример:

```text
src/shared/
  contracts/
  domain/
  ports/
  telemetry/
  security/
```

## `shared/contracts/`

Общие request/response-схемы между агентами.

Например:

```text
contracts/
  orders.py
  readiness.py
  remediation.py
  tasks.py
  trace.py
```

Если Coordinator вызывает WARP, оба должны понимать один контракт:

```text
ReadinessCheckRequest
ReadinessCheckResponse
```

Если Coordinator поручает работу CR Manager, оба должны понимать:

```text
DispatchCrTaskRequest
DispatchCrTaskResponse
```

## `shared/domain/`

Общие базовые вещи, которые не принадлежат одному агенту:

```text
domain/
  ids.py
  errors.py
  timestamps.py
```

Например:

- генерация `correlation_id`;
- генерация `agent_run_id`;
- базовые application errors;
- работа со временем.

## `shared/ports/`

Общие порты, которые нужны нескольким агентам.

Например:

```text
ports/
  trace.py
  event_bus.py
```

Trace нужен всем агентам, поэтому общий контракт trace можно держать в `shared`.

## `shared/telemetry/`

Общие правила наблюдаемости:

```text
telemetry/
  correlation.py
  trace_events.py
```

Здесь можно держать:

- обязательные поля trace event;
- helpers для correlation;
- стандартные имена событий;
- правила связывания событий по `correlation_id`.

## `shared/security/`

Общие правила безопасности:

```text
security/
  permissions.py
  service_accounts.py
```

Здесь можно держать:

- перечень разрешений для tools;
- правила service accounts;
- запрет на секреты в prompts;
- запрет на секреты в trace;
- базовые политики доступа.

## Как агенты взаимодействуют

Целевая логика:

```text
Пользователь
→ Coordinator создаёт DRAFT-предзаказ
→ Coordinator поручает Requirements Agent проверку входа
→ Requirements Agent проверяет КЭ, атрибуты и СДО
→ Coordinator вызывает WARP
→ если WARP < 100%, Coordinator поручает CR Manager remediation
→ CR Manager создаёт Jira/CR и оркестрирует исправления
→ CR Manager делает self-check через WARP
→ CR Manager возвращает callback Coordinator
→ Coordinator делает final-check через WARP
→ Coordinator переводит предзаказ в READY
→ Coordinator передаёт READY-предзаказ EP Coordinator
→ EP Coordinator создаёт заказ и запускает контур репликации
```

## Главное правило границ

Агенты не должны импортировать внутренний код друг друга.

Нельзя:

```python
from agents.warp.application.service import WarpService
```

Можно:

```python
from shared.contracts.readiness import ReadinessCheckRequest
from agents.coordinator.ports.warp import WarpPort
```

Coordinator не знает внутреннюю реализацию WARP.
Coordinator знает только порт и контракт.

## Как моки заменяются на реальные API

В POC:

```text
WarpPort -> MockWarpAdapter
CrManagerPort -> MockCrManagerAdapter
EpCoordinatorPort -> MockEpCoordinatorAdapter
```

В test/prod:

```text
WarpPort -> HttpWarpAdapter
CrManagerPort -> HttpCrManagerAdapter
EpCoordinatorPort -> HttpEpCoordinatorAdapter
```

Меняется wiring в `app/config/container.py`.

Application и domain слои агентов при этом не переписываются.

Если внешняя система подключается через MCP:

```text
JiraPort -> JiraMcpAdapter -> Jira MCP server
ConfluencePort -> ConfluenceMcpAdapter -> Confluence MCP server
```

Для агента это всё равно работа через port. MCP остаётся деталью adapter-слоя.

## Короткая формула проекта

```text
app      = сборка и запуск приложения
agents   = самостоятельные агентные модули
shared   = общие контракты и базовые правила
api      = входные endpoints агента
domain   = бизнес-модель агента
application = сценарии работы агента
ports    = интерфейсы наружу
adapters = mock, HTTP, queue, MCP или другие реализации интерфейсов
tools    = безопасные действия для LLM
skills   = инструкции и playbooks для LLM-агентов
```
