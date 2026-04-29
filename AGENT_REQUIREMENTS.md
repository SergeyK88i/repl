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
  -> typed tools
    -> ports
      -> adapters
        -> external systems
```

LLM не должен напрямую ходить во внешние системы.

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

## Coordinator Agent

### Назначение

Координатор владеет жизненным циклом предзаказа.

Он отвечает за маршрут:

```text
CREATED → VALIDATING → WAITING_CR → READY / FAILED
```

После READY он передаёт работу ЕР-Конфигуратору.

### Обязанности

- принять предзаказ от пользователя;
- создать `order_id` / будущий `preorder_id`;
- создать `correlation_id`;
- сохранить предзаказ;
- запросить WARP readiness;
- принять решение по WARP verdict;
- создать CR-задачу при `NOT_READY`;
- принять callback от CR Manager;
- проверить принадлежность CR-задачи предзаказу;
- выполнить final-check через WARP;
- перевести предзаказ в READY;
- передать задачу ЕР-Конфигуратору;
- перевести предзаказ в FAILED при лимите попыток;
- подготовить escalation context.

### Что Координатор не должен делать

- чинить источник;
- знать remediation-инструкции;
- напрямую вызывать Confluence/config/db коннекторы;
- самостоятельно решать, что источник готов без WARP;
- менять статусы задач других агентов напрямую.

### Входные контракты

```text
POST /order
POST /order/{order_id}/task-completed
GET  /order/{order_id}
GET  /trace/{correlation_id}
```

### Зависимости через порты

- `WarpPort`;
- `CrManagerPort`;
- `ReplicaInitPort` / будущий `EpConfiguratorPort`;
- `OrderRepositoryPort`;
- `TaskRepositoryPort`;
- `TracePort`;
- `EscalationPort`;
- будущий `CoordinatorReasoningPort`.

### State model

```text
CREATED
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

## WARP Agent

### Назначение

WARP — единственный authority по готовности источника.

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
  "status": "READY",
  "score": {
    "current": 40,
    "required": 40
  },
  "failed_criteria": [],
  "audit_hash": "abc123",
  "regression": false
}
```

### Требования к remediation

WARP должен вернуть машинно-интерпретируемые инструкции:

```json
{
  "criteria_id": "C3.P2",
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

## ЕР-Конфигуратор

### Назначение

ЕР-Конфигуратор начинает работу после READY.

Он переводит READY-предзаказ в процесс создания и настройки реплики.

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
- список внешних систем;
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

