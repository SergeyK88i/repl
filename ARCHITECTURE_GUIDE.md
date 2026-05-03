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
```

Такой подход нужен, чтобы разные команды могли работать независимо:

- команда Coordinator работает в `src/agents/coordinator/`;
- команда Requirements Agent работает в `src/agents/requirements/`;
- команда CR Manager работает в `src/agents/cr_manager/`;
- команда EP Coordinator работает в `src/agents/ep_coordinator/`.

Позже любого агента можно вынести в отдельный сервис, если его границы останутся чистыми.

WARP в production не является нашим агентным модулем. Это внешний сервис другой команды.
В нашем проекте для WARP остаются только contracts, `WarpPort`, mock adapter для POC и HTTP adapter для real API.

## Внутренняя структура агента

Целевая структура агента:

```text
src/agents/{agent_name}/
  api/
  application/
  domain/
  ports/
  adapters/
  reasoning/
  tools/
  skills/
```

Папка `tools/` нужна только тем агентам, у которых есть LLM-слой или планируется LLM-слой.

Например, у CR Manager она нужна почти точно.
У Coordinator на первом этапе её может не быть, потому что Coordinator лучше держать максимально детерминированным.

Папка `skills/` тоже нужна только LLM-агентам. Она хранит инструкции и playbooks для reasoning-слоя, но не заменяет кодовые правила, state machine и contracts.

Папка `reasoning/` нужна только агентам, у которых есть LLM-слой. Она содержит код, который готовит контекст для LLM, вызывает LLM provider, валидирует структурированный ответ и возвращает application service проверяемый план.

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

## `reasoning/`

`reasoning` содержит LLM-слой агента.

Эта папка нужна не каждому агенту. Она появляется только там, где LLM реально помогает:

- Requirements Agent;
- CR Manager;
- позже EP Coordinator;
- возможно Coordinator только для объяснений и summary.

Пример структуры:

```text
reasoning/
  service.py
  prompts.py
  schemas.py
  policy.py
  context_builder.py
  memory.py
```

`service.py` вызывает LLM provider и возвращает структурированный результат.

`prompts.py` собирает system/developer/user messages.

`schemas.py` описывает Pydantic-схемы ответа LLM.

`policy.py` содержит ограничения: какие intents и tools разрешены в текущей роли.

`context_builder.py` собирает минимальный контекст для LLM из application state, trace и внешних read-only источников.

`memory.py` описывает доступ к памяти агента, если агенту нужна краткосрочная или долгосрочная память.

Reasoning-слой не должен:

- менять статус;
- писать напрямую в БД;
- напрямую ходить во внешние API;
- выполнять tools в обход application service;
- хранить prompt memory как источник истины.

Правильная цепочка:

```text
application service
→ context_builder собирает контекст
→ reasoning service получает structured plan от LLM
→ application service проверяет plan
→ tools выполняют разрешённые действия
→ state machine контролирует статус
→ trace фиксирует результат
```

### Нужен ли LangGraph

Для MVP LangGraph не нужен как обязательная зависимость.

Начальный production-friendly вариант проще:

```text
ReasoningService
→ structured output schema
→ policy validation
→ tool execution через application service
```

LangGraph можно добавить позже внутри конкретного агента, если появятся реальные причины:

- многошаговое планирование;
- сложное ветвление;
- циклы tool-use;
- параллельные ветки reasoning;
- human-in-the-loop внутри одного агента;
- необходимость сохранять граф выполнения.

Даже если LangGraph будет добавлен, он должен жить внутри `reasoning/` или `application/agent.py` конкретного агента и не становиться фундаментом всей системы.

### Reasoning endpoints

Reasoning не должен быть публичным бизнес-endpoint по умолчанию.

Основные endpoint-ы остаются агентными:

```text
POST /requirements/check
POST /cr-manager/task
POST /ep-coordinator/task
```

Внутри этих endpoint-ов application service может вызвать reasoning.

Для отладки можно добавить внутренние admin/debug endpoint-ы:

```text
POST /internal/requirements/reasoning/preview
POST /internal/cr-manager/reasoning/preview
```

Они должны:

- быть выключены в production или закрыты авторизацией;
- не выполнять tools;
- возвращать только proposed plan;
- писать audit/trace;
- не менять состояние.

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

### Чем tool отличается от adapter

Tool и adapter оба могут приводить к реальному действию, но они находятся на разных уровнях архитектуры.

Tool отвечает на вопрос:

```text
"Что агенту разрешено сделать по смыслу?"
```

Adapter отвечает на вопрос:

```text
"Как именно технически выполнить это действие?"
```

Пример:

```text
LLM решил: "нужно создать CR"
  ↓
Tool: create_jira_issue
  ↓
Port: JiraPort
  ↓
Adapter: JiraCloudAdapter
  ↓
Jira API
```

Для LLM это одно бизнес-действие:

```text
создать CR
```

Для backend это контролируемая цепочка:

```text
create_jira_issue
→ validate input
→ JiraPort.create_issue(...)
→ JiraCloudAdapter
→ Jira API
→ trace event
```

Один и тот же tool может работать через разные adapters:

```text
create_jira_issue
  -> JiraPort
    -> MockJiraAdapter
    -> JiraCloudAdapter
    -> JiraMcpAdapter
```

Так LLM не зависит от того, работаем мы с mock, реальной Jira или MCP server.

## Какие решения может принимать LLM

Мы хотим, чтобы LLM принимала решения, но не все решения в системе должны быть отданы LLM без контроля.

LLM полезна там, где нужна гибкость:

- понять свободный текст пользователя;
- определить, каких данных не хватает;
- сформулировать уточняющий вопрос;
- объяснить статус простым языком;
- разложить remediation-план;
- выбрать подходящий connector из разрешённых;
- подготовить комментарий в Jira;
- подготовить escalation summary.

Но есть решения, где LLM не должна быть единственным контролёром:

- можно ли менять статус предзаказа на `READY`;
- можно ли считать WARP меньше 100% не блокером;
- можно ли создать заказ без согласования СДО;
- можно ли обойти final-check;
- можно ли повторно создать тот же Jira ticket;
- можно ли отправить секрет в trace.

Эти решения должны контролироваться кодом:

- domain rules;
- state machine;
- permissions;
- contracts;
- tools validation;
- trace;
- idempotency rules.

Правильная модель:

```text
LLM предлагает намерение
→ tool оформляет намерение в безопасное действие
→ workflow проверяет, можно ли это действие сейчас
→ port вызывает adapter
→ adapter выполняет вызов во внешний мир
→ state machine разрешает или запрещает изменение состояния
→ trace фиксирует результат
```

Пример CR Manager:

```text
CR Manager LLM: "похоже, критерии закрыты"
→ tool run_warp_self_check вызывает WARP
→ WARP возвращает READY или NOT_READY
→ CR Manager сообщает Coordinator результат self-check
→ Coordinator делает official final-check через WARP
→ только Coordinator может поставить READY
```

Именно поэтому система не должна работать по принципу:

```text
LLM решила → система сразу сделала
```

Production-подход:

```text
LLM = рассуждение и гибкость
Backend rules = безопасность, статус, права и контроль
Tools = разрешённые действия
Adapters = техническое исполнение
Trace = доказательство того, что произошло
```

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

## Память и контекст LLM-агентов

Prompt history не является памятью системы.

Для production нужно разделять несколько типов контекста.

### Execution context

Контекст одного запуска агента.

Обязательные поля:

```text
correlation_id
agent_run_id
preorder_id или order_id
task_id
source_id
load_plan, если применимо
attempt
current_status
```

Execution context передаётся во все tools, trace-события и внешние вызовы.

### Short-term memory

Краткосрочная память внутри одного agent run.

Примеры:

- промежуточный план CR Manager;
- выбранные tools;
- результаты уже выполненных tools;
- ошибки текущей попытки;
- reasoning summary текущего шага.

Где хранить:

```text
agent_runs
agent_run_steps
tool_executions
```

Short-term memory должна переживать retry и рестарт процесса, если agent run уже начался.

### Long-term memory

Долгосрочная память между разными задачами.

Примеры:

- успешные remediation-паттерны;
- типовые причины эскалации;
- runbooks;
- knowledge base;
- статистика connector success/failure;
- предпочтения по планам загрузки, если они подтверждены правилами.

Где хранить:

```text
knowledge_base
remediation_patterns
agent_learnings
vector_index, если понадобится semantic search
```

Long-term memory нельзя использовать как единственный источник истины.

Если память говорит “обычно это чинится так”, агент всё равно должен проверить:

- текущий WARP response;
- permissions;
- актуальные contracts;
- state machine;
- результат tools.

### Conversation memory

История общения с пользователем.

Используется для:

- уточняющих вопросов;
- объяснения статуса;
- восстановления контекста диалога.

Не используется для:

- смены статусов;
- подтверждения READY;
- обхода СДО/WARP/Jira;
- хранения секретов.

### Что отправлять в LLM

В LLM нужно отправлять минимальный достаточный контекст:

- роль агента;
- цель текущего шага;
- execution context без секретов;
- текущий статус;
- релевантные trace summary;
- результаты read-only tools;
- список разрешённых tools;
- ограничения policy.

Не отправляем:

- service tokens;
- raw credentials;
- лишние персональные данные;
- полный trace, если достаточно summary;
- внутренние данные других агентов без необходимости.

## `src/shared/`

`shared` содержит только то, что действительно общее для нескольких агентов.

Пример:

```text
src/shared/
  contracts/
  domain/
  ports/
  adapters/
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

## `shared/adapters/`

Общие adapter-ы для инфраструктурных провайдеров, которые могут использовать несколько агентов.

Пример:

```text
adapters/
  llm/
    gigachat.py
```

LLM provider не должен жить внутри конкретного агента, если им могут пользоваться Requirements Agent, CR Manager и EP Coordinator.

Текущая модель:

```text
ReasoningService
→ LlmPort
→ GigaChatAdapter
→ GigaChat API
```

GigaChat adapter отвечает только за транспорт:

- OAuth token;
- refresh token on 401;
- chat completions;
- embeddings;
- TLS/certificate settings;
- mapping provider response в `LlmChatResponse`.

Он не хранит conversation history и не управляет памятью агента. Память собирается в `reasoning/context_builder.py` и `reasoning/memory.py`.

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
