# Требования к агентам

## Общие требования

Каждый агент должен быть не просто скриптом, а самостоятельным сервисным компонентом с понятными контрактами.

У каждого агента должны быть:

- зона ответственности;
- входной контракт;
- выходной контракт;
- набор разрешённых tools;
- state model;
- trace events;
- error model;
- retry policy;
- escalation policy;
- security constraints;
- тесты.

## Общая модель агента

```text
Agent = application service + domain logic + ports + adapters + optional LLM reasoning
```

Если агент использует LLM:

```text
LLM reasoning layer
  -> skills / playbooks
  -> typed tools
    -> ports
      -> adapters
        -> external systems
```

LLM не должен напрямую ходить во внешние системы.

MCP servers и skills являются опциональным расширением LLM-агентов.

MCP server — это способ подключить внешний инструмент или систему к LLM/tool execution. В архитектуре проекта MCP должен рассматриваться как реализация adapter или tool backend, а не как замена ports/adapters.

Skill — это инструкция для LLM-слоя агента: как рассуждать, какие шаги соблюдать, когда выбирать tool, когда эскалировать. Skill не является источником истины по статусам, бизнес-правилам, permissions и контрактам.

Правильная модель с MCP:

```text
LLM reasoning
  -> typed tool
    -> port
      -> MCP adapter
        -> MCP server
          -> external system
```

Tool и adapter разделяются по ответственности:

```text
Tool = что агенту разрешено сделать по смыслу
Adapter = как технически выполнить это действие
```

Например:

```text
create_jira_issue
  -> JiraPort
    -> MockJiraAdapter / JiraCloudAdapter / JiraMcpAdapter
```

LLM может выбирать разрешённые tools, формулировать уточнения, планировать remediation и готовить объяснения.

LLM не должна самостоятельно менять критичные статусы, обходить WARP, игнорировать state machine, нарушать permissions или создавать внешние сущности без idempotency-контроля.

## Общие идентификаторы

Каждый агентный вызов должен передавать:

- `correlation_id`;
- `order_id` или будущий `preorder_id`;
- `source_id`;
- `task_id`, если работа выполняется в рамках задачи;
- `agent_run_id`, если запускается отдельное выполнение агента;
- `attempt`, если действие является частью retry-цикла.

## Общие trace-события

Каждый агент пишет свои события сам.

Минимальный набор:

```text
agent_run_started
agent_run_finished
agent_run_failed
external_call_started
external_call_finished
external_call_failed
decision_made
task_status_changed
escalation_requested
```

Trace-события должны быть append-only.

## LLM reasoning по агентам

Этот раздел фиксирует, где в системе нужен LLM reasoning, а где агент должен оставаться преимущественно детерминированным.

Главное правило: LLM может предлагать намерения, планы, объяснения и выбор разрешённых tools. Критичные статусы, финальные решения готовности, права, idempotency и внешние вызовы контролирует backend-система.

### Coordinator

Нужен ли LLM: позже, минимально.

Что делает LLM:

- объясняет статус предзаказа пользователю;
- делает summary trace;
- готовит текст эскалации;
- помогает классифицировать нестандартную ошибку.

Что делает система:

- создаёт `DRAFT`;
- меняет статусы;
- вызывает Requirements Agent, WARP, CR Manager и ЕР-Координатор;
- контролирует retry;
- ставит `READY` только после WARP final-check.

Доступные tools:

- `explain_preorder_status`;
- `summarize_trace`;
- `prepare_escalation_summary`;
- `classify_error`.

Что LLM запрещено:

- менять статус;
- ставить `READY`;
- обходить WARP;
- создавать Jira/CR;
- запускать ЕР-заказ без READY;
- менять retry/idempotency rules.

### Requirements Agent

Нужен ли LLM: да, один из первых.

Что делает LLM:

- понимает свободный текст пользователя;
- извлекает КЭ источника;
- понимает выбранные атрибуты;
- находит недостающие данные;
- формулирует уточняющие вопросы;
- объясняет причину отказа или human review.

Что делает система:

- проверяет КЭ через СДО/каталог;
- валидирует обязательные поля;
- проверяет атрибутный состав;
- решает, можно ли вернуть `APPROVED`;
- сохраняет результат и trace.

Доступные tools:

- `check_source_ke`;
- `validate_attributes`;
- `ask_sdo`;
- `build_clarification_questions`;
- `summarize_requirements_result`.

Что LLM запрещено:

- подтверждать предзаказ без СДО/каталогов;
- менять статус предзаказа напрямую;
- проверять readiness вместо WARP;
- создавать CR;
- запускать ЕР-фазу.

### WARP Integration

Нужен ли LLM: обычно нет.

Что делает LLM:

- не требуется для базовой архитектуры;
- позже может помогать объяснять критерии простым языком, но не считать readiness.

Что делает система:

- оценивает готовность источника;
- возвращает `READY` или `NOT_READY`;
- считает score;
- возвращает failed criteria;
- выдаёт remediation-инструкции;
- формирует audit hash.

Доступные tools:

- `explain_failed_criteria` как необязательный read-only tool.

Что LLM запрещено:

- менять статус предзаказа;
- создавать CR;
- исправлять источник;
- объявлять readiness без правил WARP;
- подменять score.

### CR Manager

Нужен ли LLM: да, основной LLM-агент.

Что делает LLM:

- анализирует remediation-инструкции;
- предлагает план исправлений;
- выбирает разрешённые connectors/tools;
- готовит комментарии в Jira;
- решает, нужен retry или escalation в рамках policy;
- готовит escalation summary.

Что делает система:

- создаёт Jira/CR через tool;
- вызывает WARP remediation;
- запускает connectors;
- делает self-check;
- сохраняет task state;
- отправляет callback Coordinator;
- контролирует idempotency.

Доступные tools:

- `create_jira_issue`;
- `get_warp_remediation`;
- `run_connector`;
- `run_warp_self_check`;
- `complete_jira_issue`;
- `notify_coordinator`;
- `escalate_to_human`.

Что LLM запрещено:

- ставить предзаказу `READY`;
- обходить WARP;
- считать self-check успешным без WARP;
- напрямую вызывать API без tools;
- скрывать ошибки connector;
- создавать дубли Jira/CR.

### EP Coordinator

Нужен ли LLM: да, но позже.

Что делает LLM:

- помогает подобрать параметры реплики;
- объясняет выбранную конфигурацию;
- находит конфликт параметров;
- готовит комментарии в ЕР/Jira;
- предлагает escalation при конфликте.

Что делает система:

- создаёт заказ в ЕР/Jira-контуре;
- валидирует конфиг;
- запускает loader;
- контролирует статусы ЕР-фазы;
- сохраняет trace.

Доступные tools:

- `create_ep_order`;
- `select_replica_parameters`;
- `generate_ep_config`;
- `validate_ep_config`;
- `handoff_to_loader`;
- `prepare_ep_escalation`.

Что LLM запрещено:

- стартовать до `READY`;
- создавать заказ без входного READY-предзаказа;
- применять невалидный конфиг;
- обходить approvals;
- менять статусы предзаказа.

### Init Loader

Нужен ли LLM: скорее нет в MVP.

Что делает LLM:

- позже может объяснять ошибки загрузки;
- может предлагать retry/escalation summary.

Что делает система:

- запускает загрузку;
- проверяет прогресс;
- делает retry по правилам;
- пишет trace;
- сообщает результат дальше.

Доступные tools:

- `start_initial_load`;
- `check_load_status`;
- `prepare_load_failure_summary`.

Что LLM запрещено:

- самостоятельно менять бизнес-статус заказа;
- скрывать ошибки загрузки;
- повторять unsafe operations без разрешения.

### Publisher

Нужен ли LLM: скорее нет в MVP.

Что делает LLM:

- позже может объяснять результат публикации;
- может готовить пользовательское summary.

Что делает система:

- проверяет результат загрузки;
- публикует реплику;
- фиксирует финальный статус;
- отправляет уведомления.

Доступные tools:

- `validate_loaded_replica`;
- `publish_replica`;
- `notify_publication_result`.

Что LLM запрещено:

- публиковать без успешной загрузки;
- обходить финальные проверки;
- менять исходные статусы предзаказа.

## Общий шаблон reasoning для LLM-агента

Для каждого LLM-агента reasoning должен возвращать не свободный текст, а структурированный результат.

Пример:

```json
{
  "intent": "run_remediation",
  "summary": "Нужно закрыть критерии C1 и C3.P2",
  "proposed_tools": [
    {
      "name": "get_warp_remediation",
      "input": {
        "criteria_ids": ["C1", "C3.P2"]
      }
    },
    {
      "name": "run_connector",
      "input": {
        "connector": "config_updater",
        "criteria_id": "C3.P2"
      }
    }
  ],
  "requires_human": false,
  "risk_level": "medium"
}
```

Application service должен проверить этот результат:

- все tools входят в список разрешённых;
- входные данные валидны;
- действие допустимо в текущем статусе;
- нет нарушения permissions;
- нет нарушения idempotency;
- результат можно записать в trace.

Только после этого tools могут быть выполнены.

## Реализация reasoning-слоя

Для MVP reasoning реализуем без обязательного LangGraph.

Базовая production-friendly схема:

```text
ApplicationService
  -> ContextBuilder
  -> ReasoningService
  -> StructuredReasoningResult
  -> PolicyValidator
  -> ToolExecutor
```

`ReasoningService` может быть реализован через обычный LLM client с structured output.

LLM provider подключается через общий порт:

```text
ReasoningService
  -> LlmPort
    -> GigaChatAdapter
      -> GigaChat API
```

`GigaChatAdapter` не хранит историю диалога и не принимает решений за агента. Он отвечает только за token management, HTTP-вызов, chat completions, embeddings и mapping ответа провайдера в наши контракты.

LangGraph можно добавить позже только внутри конкретного агента, если простого `ReasoningService` станет мало.

### Где лежит reasoning

У LLM-агента появляется папка:

```text
src/agents/{agent_name}/reasoning/
  service.py
  prompts.py
  schemas.py
  policy.py
  context_builder.py
  memory.py
```

### Что делает reasoning

Reasoning может:

- понять задачу;
- выбрать intent;
- предложить план;
- выбрать tools из разрешённого списка;
- сформировать объяснение;
- предложить human escalation.

Reasoning не может:

- выполнять tools напрямую;
- менять статусы;
- писать в repositories;
- вызывать adapters;
- обходить permissions;
- считать prompt history источником истины.

### Reasoning endpoints

Публичные endpoint-ы агентов не должны называться reasoning endpoint-ами.

Правильно:

```text
POST /requirements/check
POST /cr-manager/task
POST /ep-coordinator/task
```

Reasoning вызывается внутри application service.

Для разработки и диагностики допускаются внутренние preview endpoint-ы:

```text
POST /internal/requirements/reasoning/preview
POST /internal/cr-manager/reasoning/preview
```

Ограничения preview endpoint-ов:

- не выполняют tools;
- не меняют состояние;
- требуют авторизацию;
- не доступны публично;
- возвращают только proposed reasoning result;
- пишут audit/trace.

### Контекст и память

Reasoning получает только минимальный достаточный контекст.

Типы памяти:

#### Execution context

Обязательные идентификаторы текущего выполнения:

```text
correlation_id
agent_run_id
preorder_id или order_id
task_id
source_id
load_plan
attempt
current_status
```

#### Short-term memory

Память текущего agent run:

- proposed plan;
- выполненные tool calls;
- результаты tools;
- ошибки текущей попытки;
- промежуточные summaries.

Хранится в устойчивом состоянии:

```text
agent_runs
agent_run_steps
tool_executions
```

#### Long-term memory

Память между задачами:

- runbooks;
- remediation patterns;
- knowledge base;
- статистика успешности connectors;
- типовые escalation summaries.

Long-term memory может помогать reasoning, но не является authority.

#### Conversation memory

История общения с пользователем.

Используется для уточнений и объяснений, но не для смены статусов, READY, WARP, СДО или Jira.

### Что отправляем в LLM

Можно отправлять:

- роль агента;
- цель текущего шага;
- execution context без секретов;
- текущий статус;
- краткий trace summary;
- read-only результаты tools;
- список разрешённых tools;
- policy constraints.

Нельзя отправлять:

- tokens;
- credentials;
- секреты;
- лишние персональные данные;
- полный trace, если достаточно summary;
- внутренние данные других агентов без необходимости.

## Coordinator Agent

### Назначение

Координатор владеет жизненным циклом предзаказа.

Он отвечает за маршрут:

```text
DRAFT → REQUIREMENTS_CHECK → REQUIREMENTS_APPROVED → VALIDATING → WAITING_CR → READY / FAILED
```

После READY он передаёт работу ЕР-Координатору.

### Обязанности

- принять запрос от пользователя;
- создать предзаказ в статусе `DRAFT`;
- создать `order_id` / будущий `preorder_id`;
- создать `correlation_id`;
- сохранить предзаказ;
- поручить Requirements Agent проверку КЭ, атрибутов и согласование с СДО;
- обработать результат Requirements Agent;
- запросить WARP readiness;
- принять решение по WARP verdict;
- создать поручение для CR Manager при `NOT_READY`;
- принять callback от CR Manager;
- проверить принадлежность remediation-задачи предзаказу;
- выполнить final-check через WARP;
- перевести предзаказ в READY;
- передать задачу ЕР-Координатору;
- перевести предзаказ в FAILED при лимите попыток;
- подготовить escalation context.

### Что Координатор не должен делать

- чинить источник;
- знать remediation-инструкции;
- напрямую вызывать Confluence/config/db коннекторы;
- самостоятельно решать, что источник готов без WARP;
- менять статусы задач других агентов напрямую.
- создавать Jira/CR-задачи за CR Manager.

### Входные контракты

```text
POST /order
POST /order/{order_id}/task-completed
GET  /order/{order_id}
GET  /trace/{correlation_id}
```

### Зависимости через порты

- `WarpPort`;
- `RequirementsPort`;
- `CrManagerPort`;
- `EpCoordinatorPort`;
- `OrderRepositoryPort`;
- `TaskRepositoryPort`;
- `TracePort`;
- `EscalationPort`;
- будущий `CoordinatorReasoningPort`.

### State model

```text
DRAFT
REQUIREMENTS_CHECK
NEEDS_CLARIFICATION
REQUIREMENTS_APPROVED
VALIDATING
WAITING_CR
READY
FAILED
```

### Требования к ИИ-слою

Координатор может использовать LLM для:

- объяснения статуса;
- анализа trace;
- подготовки escalation summary;
- классификации нестандартных ошибок.

Координатор не должен позволять LLM напрямую менять статус.

## Requirements Agent

### Назначение

Requirements Agent проверяет качество входа до технической проверки источника.

Он отвечает на вопрос:

```text
"Можно ли этот пользовательский запрос безопасно отдать в работу Координатору дальше?"
```

### Обязанности

- проверить корректность КЭ источника;
- проверить выбранный атрибутный состав;
- проверить обязательные поля предзаказа;
- согласовать предзаказ с СДО;
- вернуть Координатору structured result;
- подготовить уточняющие вопросы, если данных не хватает;
- писать trace-события своего выполнения.

### Что Requirements Agent не должен делать

- менять статус предзаказа напрямую;
- проверять техническую готовность источника вместо WARP;
- создавать CR или Jira-задачи;
- запускать ЕР-фазу;
- владеть жизненным циклом предзаказа.

### Входные контракты

```text
POST /requirements/check
GET  /requirements/check/{task_id}
```

### Зависимости через порты

- `SdoPort`;
- `SourceCatalogPort`;
- `AttributeCatalogPort`;
- `TracePort`;
- будущий `RequirementsReasoningPort`.

### State model

```text
RECEIVED
CHECKING_SOURCE
CHECKING_ATTRIBUTES
WAITING_SDO
APPROVED
NEEDS_CLARIFICATION
REJECTED
HUMAN_REVIEW_REQUIRED
FAILED
```

### Что умеет

- понимать пользовательский запрос на естественном языке;
- находить недостающие данные до старта процесса;
- объяснять пользователю, что нужно уточнить;
- формировать структурированный результат для Координатора.

### Требования к ИИ-слою

Requirements Agent — хороший кандидат на LLM-agent.

LLM может помогать:

- разбирать свободный текст пользователя;
- сопоставлять смысл запроса с атрибутами;
- формулировать уточняющие вопросы;
- готовить краткое объяснение результата проверки.

LLM не может:

- подтверждать предзаказ без проверок через разрешённые tools;
- скрывать конфликт с СДО;
- менять статус предзаказа напрямую.

## WARP Integration

### Назначение

WARP — внешний сервис другой команды и единственный authority по готовности источника.

В нашем проекте WARP не разрабатывается как полноценный агентный модуль. Мы реализуем только:

- shared contracts;
- `WarpPort`;
- `MockWarpAdapter` для POC;
- `HttpWarpAdapter` для real API;
- contract/integration tests.

### Обязанности

- оценить источник по критериям готовности;
- вернуть `READY` или `NOT_READY`;
- вернуть score;
- вернуть failed criteria;
- вернуть audit hash при READY;
- предоставить remediation-инструкции по критериям;
- поддерживать контексты:
  - `initial_check`;
  - `self_check`;
  - `final_check`.

### Что WARP не должен делать

- менять состояние источника;
- создавать Jira-задачи;
- выполнять remediation;
- менять статус предзаказа;
- запускать реплику.

### Основные контракты

```text
POST /warp/readiness
POST /warp/get-remediation
```

### Требования к ответу readiness

Минимальные поля:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "status": "READY",
  "score": {
    "current": 100,
    "required": 100
  },
  "failed_criteria": [],
  "warp_check_id": "WARP-CHECK-123",
  "audit_hash": "abc123",
  "regression": false,
  "checked_at": "2026-05-03T12:00:00Z"
}
```

Если `load_plan` не передан в request, WARP должен проверить источник по плану по умолчанию и вернуть фактический `load_plan` в response.

Текущая договорённость: план по умолчанию — `PLAN_A`.

`failed_criteria` должны поддерживать детализацию до параметров критерия, если WARP умеет её отдавать.

Пример:

```json
{
  "criteria_id": "C1",
  "criteria_name": "Готовность описания источника",
  "failed_params": [
    {
      "param_id": "P1",
      "param_name": "Не заполнено описание",
      "severity": "blocking",
      "message": "Описание источника отсутствует"
    }
  ]
}
```

### Требования к remediation

Remediation-инструкции у WARP запрашивает CR Manager, а не Coordinator.

WARP должен вернуть машинно-интерпретируемые инструкции по конкретным `criteria_id` и `param_id`:

```json
{
  "criteria_id": "C3.P2",
  "param_id": "P1",
  "steps": [],
  "connector": "config-updater",
  "params": {},
  "expected_result": {}
}
```

## CR Manager Agent

### Назначение

CR Manager исполняет remediation-задачи.

### Обязанности

- принять failed criteria от Координатора;
- создать задачу в Jira;
- запросить remediation у WARP;
- выбрать нужные tools/connectors;
- выполнить исправления;
- зафиксировать результаты;
- выполнить self-check через WARP;
- отправить callback Координатору;
- выполнить retry или escalation при ошибке.

### Что CR Manager не должен делать

- выставлять предзаказу статус READY;
- обходить WARP;
- принимать финальное решение о готовности источника;
- менять глобальный статус предзаказа.

### Входные контракты

```text
POST /cr-manager/task
GET  /cr-manager/task/{task_id}
```

### Зависимости через порты

- `JiraPort`;
- `WarpPort`;
- `ConnectorPort`;
- `TaskRepositoryPort`;
- `CoordinatorCallbackPort`;
- `TracePort`;
- будущий `CrManagerReasoningPort`.

### State model

```text
RECEIVED
JIRA_CREATED
REMEDIATION_RECEIVED
EXECUTING
SELF_CHECKING
DONE
FAILED
ESCALATED
```

### Tools

Минимальный набор:

```text
create_jira_issue
get_warp_remediation
execute_connector
run_warp_self_check
complete_jira_issue
notify_coordinator
escalate_to_human
```

### Skills

Рекомендуемые skills для LLM-слоя:

```text
remediation_planning
jira_commenting
connector_selection
escalation_summary
```

Skills помогают LLM-слою понять, как действовать внутри роли CR Manager, но не заменяют state model, tools и проверки WARP.

### Возможные MCP adapters

CR Manager может использовать MCP как способ подключения внешних систем:

```text
JiraMcpAdapter
ConfluenceMcpAdapter
KnowledgeBaseMcpAdapter
```

MCP adapters должны вызываться через ports/tools и писать trace так же, как обычные adapters.

### Требования к ИИ-слою

CR Manager — основной кандидат на LLM-agent.

LLM может:

- интерпретировать remediation-план;
- выбирать connector;
- планировать порядок действий;
- формировать комментарии в Jira;
- готовить escalation note.

LLM не может:

- выполнять внешние вызовы напрямую;
- игнорировать разрешённые tools;
- скрывать ошибки connector execution.

## ЕР-Координатор / ЕР-Конфигуратор

### Назначение

ЕР-Координатор / ЕР-Конфигуратор начинает работу после READY.

Он переводит READY-предзаказ в заказ ЕР-контура и запускает процесс создания и настройки реплики.

### Обязанности

- принять задачу от Координатора после READY;
- создать заказ в другом Jira-пространстве;
- подобрать параметры реплики;
- сгенерировать конфиг для ЕР;
- передать работу Init Loader;
- писать trace;
- эскалировать ошибки конфигурации.

### Входные контракты

```text
POST /ep-configurator/task
GET  /ep-configurator/task/{task_id}
```

### Зависимости через порты

- `JiraPort`;
- `EpConfigPort`;
- `ReplicaParameterPort`;
- `LoaderPort`;
- `TracePort`;
- будущий `EpConfiguratorReasoningPort`.

### State model

```text
RECEIVED
JIRA_CREATED
PARAMETERS_SELECTED
CONFIG_GENERATED
CONFIG_READY
HANDOFF_TO_LOADER
FAILED
ESCALATED
```

### Требования к ИИ-слою

LLM может помогать:

- выбрать параметры реплики;
- объяснить выбранную конфигурацию;
- найти конфликт параметров;
- подготовить комментарий в Jira.

Критические изменения конфига должны проходить validation.

## Init Loader Agent

### Назначение

Init Loader запускает первичную загрузку реплики.

### Обязанности

- принять готовый ЕР-конфиг;
- запустить загрузку;
- отслеживать прогресс;
- обрабатывать retry;
- сообщить результат Публикатору;
- писать trace.

### State model

```text
RECEIVED
LOADING
LOAD_SUCCEEDED
LOAD_FAILED
ESCALATED
```

## Publisher Agent

### Назначение

Публикатор проверяет результат и делает реплику доступной.

### Обязанности

- принять результат загрузки;
- выполнить финальные проверки;
- опубликовать реплику;
- сообщить итоговый статус;
- писать trace.

### State model

```text
RECEIVED
VALIDATING_RESULT
PUBLISHING
PUBLISHED
PUBLICATION_FAILED
ESCALATED
```

## Каталог планируемых tools

Tools — это разрешённые действия, которые может вызвать LLM-слой агента.

Tool не должен напрямую содержать бизнес-оркестрацию всего агента. Он выполняет одно понятное действие, валидирует вход, вызывает нужный port и возвращает структурированный результат.

Правильная цепочка:

```text
LLM reasoning
  -> typed tool
    -> port
      -> adapter
        -> external system
```

### Coordinator tools

Coordinator остаётся преимущественно детерминированным. Его tools в MVP не обязательны и могут появиться позже для объяснений и эскалаций.

#### `explain_preorder_status`

Назначение: объяснить пользователю текущий статус предзаказа простым языком.

Использует:

- `OrderRepositoryPort`;
- `TracePort`.

Вход:

```json
{
  "preorder_id": "PRE-123",
  "correlation_id": "CORR-001"
}
```

Выход:

```json
{
  "status": "WAITING_CR",
  "explanation": "Источник пока не готов. CR Manager закрывает критерии C1/P1 и C1/P5."
}
```

Ограничение: tool не меняет статус и не запускает новые действия.

#### `summarize_trace`

Назначение: собрать краткую историю процесса по `correlation_id`.

Использует:

- `TracePort`.

Выход:

```json
{
  "summary": "Предзаказ создан, требования подтверждены, WARP вернул NOT_READY, CR Manager получил remediation-задачу.",
  "events_count": 12
}
```

#### `prepare_escalation_summary`

Назначение: подготовить понятное описание проблемы для человека.

Использует:

- `OrderRepositoryPort`;
- `TaskRepositoryPort`;
- `TracePort`.

Выход:

```json
{
  "reason": "validation_retry_limit_exceeded",
  "summary": "После трёх попыток источник CM12345 всё ещё не прошёл WARP final-check.",
  "failed_criteria": ["C1/P5"],
  "trace_ref": "CORR-001"
}
```

#### `classify_error`

Назначение: помочь классифицировать нестандартную ошибку для маршрутизации или эскалации.

Выход:

```json
{
  "error_type": "retryable_external_timeout",
  "recommended_action": "retry",
  "requires_human": false
}
```

Ограничение: финальное решение о retry/escalation принимает application workflow.

### Requirements Agent tools

#### `check_source_ke`

Назначение: проверить, что КЭ источника существует и может использоваться в предзаказе.

Использует:

- `SourceCatalogPort`;
- возможно `SdoPort`.

Вход:

```json
{
  "source_ke": "CM12345",
  "correlation_id": "CORR-001"
}
```

Выход:

```json
{
  "exists": true,
  "source_id": "CM12345",
  "source_name": "Customer Accounts",
  "allowed": true
}
```

#### `validate_attributes`

Назначение: проверить выбранный пользователем атрибутный состав.

Использует:

- `AttributeCatalogPort`;
- `SourceCatalogPort`.

Вход:

```json
{
  "source_id": "CM12345",
  "attributes": ["client_id", "account_num", "balance"]
}
```

Выход:

```json
{
  "valid": true,
  "missing_attributes": [],
  "unknown_attributes": [],
  "normalized_attributes": ["client_id", "account_num", "balance"]
}
```

#### `ask_sdo`

Назначение: согласовать предзаказ или проверить ограничения через СДО.

Использует:

- `SdoPort`.

Вход:

```json
{
  "source_id": "CM12345",
  "attributes": ["client_id", "account_num", "balance"],
  "request_text": "Нужна реплика по клиентским счетам"
}
```

Выход:

```json
{
  "approved": true,
  "decision_id": "SDO-DECISION-123",
  "comments": []
}
```

#### `build_clarification_questions`

Назначение: сформировать уточняющие вопросы пользователю, если вход неполный.

Вход:

```json
{
  "missing_fields": ["source_ke", "attributes"],
  "invalid_fields": []
}
```

Выход:

```json
{
  "questions": [
    "Укажите КЭ источника, например CM12345.",
    "Какие атрибуты нужно включить в предзаказ?"
  ]
}
```

#### `summarize_requirements_result`

Назначение: объяснить результат проверки требований простым языком.

Выход:

```json
{
  "result": "APPROVED",
  "summary": "КЭ источника найден, атрибуты корректны, СДО подтвердило предзаказ."
}
```

### CR Manager tools

#### `create_jira_issue`

Назначение: создать Jira/CR-задачу на remediation.

Использует:

- `JiraPort`.

Вход:

```json
{
  "preorder_id": "PRE-123",
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "warp_check_id": "WARP-CHECK-123",
  "failed_items": [
    {
      "criteria_id": "C1",
      "param_id": "P1",
      "title": "Не заполнено описание",
      "instructions": ["Открыть карточку источника", "Заполнить описание"]
    }
  ]
}
```

Выход:

```json
{
  "jira_issue_id": "TASK-123",
  "jira_url": "https://jira.example/browse/TASK-123",
  "created": true
}
```

Ограничение: tool должен быть идемпотентным и не создавать дубли при повторном вызове.

#### `get_warp_remediation`

Назначение: получить у WARP инструкции по исправлению критериев и параметров.

Использует:

- `WarpPort`.

Вход:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "warp_check_id": "WARP-CHECK-123",
  "criteria_params": [
    {
      "criteria_id": "C1",
      "param_ids": ["P1", "P5"]
    }
  ]
}
```

Выход:

```json
{
  "items": [
    {
      "criteria_id": "C1",
      "param_id": "P1",
      "title": "Заполнить описание источника",
      "steps": ["Открыть карточку источника", "Заполнить описание", "Сохранить"],
      "recommended_connector": "source_catalog",
      "automation_possible": false
    }
  ]
}
```

#### `run_connector`

Назначение: выполнить разрешённый connector для remediation.

Использует:

- `ConnectorPort`;
- конкретный adapter или MCP adapter.

Вход:

```json
{
  "connector": "config_updater",
  "criteria_id": "C3",
  "param_id": "P2",
  "params": {
    "source_id": "CM12345"
  }
}
```

Выход:

```json
{
  "status": "SUCCEEDED",
  "execution_id": "CONN-RUN-123",
  "details": {}
}
```

Ограничение: unsafe connectors должны требовать отдельного разрешения или human approval.

#### `run_warp_self_check`

Назначение: проверить результат remediation через WARP.

Использует:

- `WarpPort`.

Вход:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "context": "self_check",
  "criteria_params": [
    {
      "criteria_id": "C1",
      "param_ids": ["P1", "P5"]
    }
  ]
}
```

Выход:

```json
{
  "status": "READY",
  "score": {
    "current": 100,
    "required": 100
  },
  "failed_criteria": []
}
```

Ограничение: self-check не переводит предзаказ в READY.

#### `complete_jira_issue`

Назначение: закрыть или обновить Jira/CR после успешного self-check.

Использует:

- `JiraPort`.

Выход:

```json
{
  "jira_issue_id": "TASK-123",
  "status": "DONE"
}
```

#### `notify_coordinator`

Назначение: отправить callback Coordinator о результате remediation-задачи.

Использует:

- `CoordinatorCallbackPort`.

Выход:

```json
{
  "accepted": true,
  "coordinator_status": "VALIDATING"
}
```

#### `escalate_to_human`

Назначение: передать человеку remediation-задачу с контекстом, если агент не может продолжить.

Использует:

- `EscalationPort` или `NotificationPort`;
- возможно `JiraPort`.

Выход:

```json
{
  "escalation_id": "ESC-123",
  "notified": true
}
```

### EP Coordinator tools

#### `create_ep_order`

Назначение: создать заказ в ЕР/Jira-контуре после READY.

Использует:

- `JiraPort`;
- `EpOrderPort`.

Ограничение: tool может быть вызван только для READY-предзаказа.

#### `select_replica_parameters`

Назначение: подобрать параметры реплики.

Использует:

- `ReplicaParameterPort`;
- возможно LLM reasoning для анализа конфликта параметров.

#### `generate_ep_config`

Назначение: сформировать конфиг для ЕР.

Использует:

- `EpConfigPort`.

Ограничение: результат должен пройти validation.

#### `validate_ep_config`

Назначение: проверить конфиг перед передачей дальше.

Использует:

- `EpConfigPort`;
- validation rules.

#### `handoff_to_loader`

Назначение: передать готовый конфиг Init Loader.

Использует:

- `LoaderPort`.

#### `prepare_ep_escalation`

Назначение: подготовить контекст эскалации по ЕР-фазе.

Использует:

- `TracePort`;
- `EpTaskRepositoryPort`;

### Init Loader tools

#### `start_initial_load`

Назначение: запустить первичную загрузку реплики.

Использует:

- `LoaderPort`.

#### `check_load_status`

Назначение: проверить состояние загрузки.

Использует:

- `LoaderPort`.

#### `prepare_load_failure_summary`

Назначение: подготовить summary ошибки загрузки для человека или следующего агента.

Использует:

- `TracePort`;
- `LoaderPort`.

### Publisher tools

#### `validate_loaded_replica`

Назначение: проверить результат загрузки перед публикацией.

Использует:

- `PublisherPort`;
- validation rules.

#### `publish_replica`

Назначение: опубликовать реплику.

Использует:

- `PublisherPort`.

Ограничение: tool нельзя вызывать без успешной загрузки и финальной проверки.

#### `notify_publication_result`

Назначение: уведомить пользователя или downstream-системы о результате публикации.

Использует:

- `NotificationPort`.

## Требования к безопасности

- Все реальные внешние вызовы выполняются через service accounts.
- Права service accounts минимальны.
- Секреты не попадают в prompt, trace и тестовые fixtures.
- Tool access задаётся явно для каждого агента.
- Любые действия LLM проходят через typed tools.

## Требования к тестированию

Для каждого агента нужны:

- unit tests domain/application logic;
- contract tests для портов;
- integration tests с mock adapters;
- idempotency tests;
- retry tests;
- failure/escalation tests;
- trace tests.

## Требования к наблюдаемости

Минимум:

- trace по `correlation_id`;
- logs по `agent_run_id`;
- metrics по статусам;
- latency внешних вызовов;
- количество retry;
- количество escalation;
- success/failure rate по агентам.

## Definition of Ready для нового агента

Новый агент можно начинать реализовывать, если определены:

- роль агента;
- входной контракт;
- выходной контракт;
- state model;
- список tools;
- список skills, если агент использует LLM;
- список внешних систем;
- способ подключения внешних систем: HTTP adapter, queue adapter, MCP adapter или другой transport;
- trace events;
- retry policy;
- escalation policy;
- security constraints;
- тестовые сценарии.

## Definition of Done для агента

Агент считается готовым к пилоту, если:

- реализован основной happy path;
- реализованы error paths;
- есть mock и real adapter strategy;
- есть trace events;
- есть tests;
- есть документация API;
- есть runbook;
- агент не зависит напрямую от внутреннего кода других агентов;
- агент может быть вынесен в отдельный сервис.
