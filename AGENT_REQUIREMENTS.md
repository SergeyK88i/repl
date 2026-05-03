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

## Матрица LLM reasoning по агентам

Эта таблица фиксирует, где в системе нужен LLM reasoning, а где агент должен оставаться преимущественно детерминированным.

Главное правило: LLM может предлагать намерения, планы, объяснения и выбор разрешённых tools. Критичные статусы, финальные решения готовности, права, idempotency и внешние вызовы контролирует backend-система.

| Агент | Нужен ли LLM | Что делает LLM | Что делает система | Доступные tools | Что LLM запрещено |
| --- | --- | --- | --- | --- | --- |
| Coordinator | Позже, минимально | Объясняет статус предзаказа пользователю; делает summary trace; готовит текст эскалации; помогает классифицировать нестандартную ошибку | Создаёт `DRAFT`; меняет статусы; вызывает Requirements Agent, WARP, CR Manager и ЕР-Координатор; контролирует retry; ставит `READY` только после WARP final-check | `explain_preorder_status`, `summarize_trace`, `prepare_escalation_summary`, `classify_error` | Менять статус; ставить `READY`; обходить WARP; создавать Jira/CR; запускать ЕР-заказ без READY; менять retry/idempotency rules |
| Requirements Agent | Да, один из первых | Понимает свободный текст пользователя; извлекает КЭ источника; понимает выбранные атрибуты; находит недостающие данные; формулирует уточняющие вопросы; объясняет причину отказа или human review | Проверяет КЭ через СДО/каталог; валидирует обязательные поля; проверяет атрибутный состав; решает, можно ли вернуть `APPROVED`; сохраняет результат и trace | `check_source_ke`, `validate_attributes`, `ask_sdo`, `build_clarification_questions`, `summarize_requirements_result` | Подтверждать предзаказ без СДО/каталогов; менять статус предзаказа напрямую; проверять readiness вместо WARP; создавать CR; запускать ЕР-фазу |
| WARP | Обычно нет | Не требуется для базовой архитектуры. Позже LLM может помогать объяснять критерии простым языком, но не считать readiness | Оценивает готовность источника; возвращает `READY`/`NOT_READY`; считает score; возвращает failed criteria; выдаёт remediation-инструкции; формирует audit hash | `explain_failed_criteria` как необязательный read-only tool | Менять статус предзаказа; создавать CR; исправлять источник; объявлять readiness без правил WARP; подменять score |
| CR Manager | Да, основной LLM-агент | Анализирует remediation-инструкции; предлагает план исправлений; выбирает разрешённые connectors/tools; готовит комментарии в Jira; решает, нужен retry или escalation в рамках policy; готовит escalation summary | Создаёт Jira/CR через tool; вызывает WARP remediation; запускает connectors; делает self-check; сохраняет task state; отправляет callback Coordinator; контролирует idempotency | `create_jira_issue`, `get_warp_remediation`, `run_connector`, `run_warp_self_check`, `complete_jira_issue`, `notify_coordinator`, `escalate_to_human` | Ставить предзаказу `READY`; обходить WARP; считать self-check успешным без WARP; напрямую вызывать API без tools; скрывать ошибки connector; создавать дубли Jira/CR |
| EP Coordinator | Да, но позже | Помогает подобрать параметры реплики; объясняет выбранную конфигурацию; находит конфликт параметров; готовит комментарии в ЕР/Jira; предлагает escalation при конфликте | Создаёт заказ в ЕР/Jira-контуре; валидирует конфиг; запускает loader; контролирует статусы ЕР-фазы; сохраняет trace | `create_ep_order`, `select_replica_parameters`, `generate_ep_config`, `validate_ep_config`, `handoff_to_loader`, `prepare_ep_escalation` | Стартовать до `READY`; создавать заказ без входного READY-предзаказа; применять невалидный конфиг; обходить approvals; менять статусы предзаказа |
| Init Loader | Скорее нет в MVP | Позже может объяснять ошибки загрузки и предлагать retry/escalation summary | Запускает загрузку; проверяет прогресс; делает retry по правилам; пишет trace; сообщает результат дальше | `start_initial_load`, `check_load_status`, `prepare_load_failure_summary` | Самостоятельно менять бизнес-статус заказа; скрывать ошибки загрузки; повторять unsafe operations без разрешения |
| Publisher | Скорее нет в MVP | Позже может объяснять результат публикации и готовить пользовательское summary | Проверяет результат загрузки; публикует реплику; фиксирует финальный статус; отправляет уведомления | `validate_loaded_replica`, `publish_replica`, `notify_publication_result` | Публиковать без успешной загрузки; обходить финальные проверки; менять исходные статусы предзаказа |

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
