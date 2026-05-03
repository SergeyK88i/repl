# CR Manager requirements

Этот документ фиксирует целевое поведение CR Manager Agent.

CR Manager — агент, который получает от Coordinator remediation-поручение, создаёт Jira/CR, получает инструкции от WARP, организует исправление критериев и возвращает Coordinator результат.

CR Manager не является владельцем статуса предзаказа и не принимает финальное решение о готовности источника.

## Роль

CR Manager отвечает за управляемую доработку источника, если WARP вернул готовность ниже 100%.

Он превращает технический результат проверки WARP в понятную и отслеживаемую работу:

```text
failed criteria/params
  -> remediation task
  -> Jira/CR
  -> remediation instructions
  -> tools/connectors/subagents
  -> WARP self-check
  -> callback Coordinator
```

## Что CR Manager делает

- принимает remediation-поручение от Coordinator;
- создаёт внутреннюю task record;
- создаёт Jira/CR-задачу;
- запрашивает remediation-инструкции у WARP;
- сохраняет связь task -> Jira/CR -> WARP check;
- выбирает разрешённые tools/connectors/subagents;
- организует исправление невыполненных критериев и параметров;
- делает self-check через WARP;
- закрывает или обновляет Jira/CR;
- отправляет callback Coordinator;
- эскалирует человеку, если remediation не может быть выполнена автоматически.

## Что CR Manager не делает

- не выставляет предзаказу статус `READY`;
- не меняет глобальный статус предзаказа;
- не обходит WARP;
- не объявляет источник готовым на основании Jira-комментария или LLM-ответа;
- не создаёт заказ в ЕР-контуре;
- не принимает пользовательский предзаказ напрямую;
- не запрашивает Requirements/СДО вместо Requirements Agent;
- не вызывает внешние API напрямую из LLM.

## Вход от Coordinator

Coordinator передаёт CR Manager не инструкции, а контекст remediation-задачи.

Текущий POC-compatible контракт:

```json
{
  "order_id": "ORD-123",
  "source_id": "SRC-123",
  "correlation_id": "CORR-001",
  "failed_criteria": ["C1", "C3.P2"],
  "attempt": 1,
  "action": "remediate"
}
```

Промежуточный F-004 контракт:

```json
{
  "order_id": "ORD-123",
  "source_id": "SRC-123",
  "correlation_id": "CORR-001",
  "load_plan": "PLAN_A",
  "warp_check_id": "WARP-CHECK-123",
  "failed_criteria": ["C1", "C3.P2"],
  "failed_items": [
    {
      "criteria_id": "C1",
      "failed_params": ["P1", "P5"]
    }
  ],
  "attempt": 1,
  "action": "remediate"
}
```

В F-004 `failed_criteria: list[str]` остаётся для обратной совместимости с текущим Coordinator.

Новые поля:

- `load_plan` — optional;
- `warp_check_id` — optional;
- `failed_items` — optional structured representation.

Если пришёл legacy-формат, CR Manager работает по `failed_criteria`.

Если пришёл structured-формат, CR Manager использует `failed_items`, `load_plan` и `warp_check_id` для Jira/CR и WARP remediation.

Целевой контракт:

```json
{
  "preorder_id": "PRE-123",
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "warp_check_id": "WARP-CHECK-123",
  "failed_criteria": [
    {
      "criteria_id": "C1",
      "failed_params": ["P1", "P5"]
    }
  ],
  "attempt": 1,
  "action": "remediate"
}
```

В целевом контракте legacy `failed_criteria: list[str]` будет удалён после migration cleanup.

Обязательные поля:

- `preorder_id` или временный POC `order_id`;
- `source_id`;
- `correlation_id`;
- `failed_criteria`;
- `attempt`;
- `action`.

Целевые обязательные поля после WARP integration:

- `load_plan`;
- `warp_check_id`;
- `failed_criteria[].criteria_id`;
- `failed_criteria[].failed_params[]`.

Migration cleanup:

```text
F-012 - Remove Legacy Failed Criteria Contract
```

Эта фича удалит legacy строковый формат после того, как Coordinator и WARP adapter начнут передавать structured failed criteria.

## API

Текущий F-002 API:

```text
POST /cr-manager/task
GET  /cr-manager/task/{task_id}
```

Будущие endpoint-ы могут появиться позже:

```text
GET  /cr-manager/task/{task_id}/events
POST /cr-manager/task/{task_id}/retry
POST /cr-manager/task/{task_id}/escalate
```

Публичные endpoint-ы не должны называться reasoning endpoint-ами.

Если нужны debug endpoint-ы reasoning, они должны быть внутренними:

```text
POST /internal/cr-manager/reasoning/preview
```

## Task lifecycle

CR Manager task проходит собственный жизненный цикл.

```text
RECEIVED
  -> JIRA_CREATED
  -> REMEDIATION_RECEIVED
  -> EXECUTING
  -> SELF_CHECKING
  -> DONE

RECEIVED
  -> FAILED

EXECUTING
  -> SELF_CHECKING
  -> FAILED

FAILED
  -> ESCALATED
```

Статусы:

### `RECEIVED`

CR Manager принял поручение от Coordinator и создал внутреннюю task record.

Это реализовано в `F-002`.

### `JIRA_CREATED`

CR Manager создал Jira/CR-задачу или нашёл уже существующую задачу по idempotency key.

Это реализовано в `F-003`.

### `REMEDIATION_RECEIVED`

CR Manager получил от WARP remediation-инструкции по критериям и параметрам.

Это реализовано в `F-004` через `MockWarpRemediationAdapter`.

### `EXECUTING`

CR Manager выполняет remediation через разрешённые tools/connectors/subagents или координирует ручную доработку через Jira/CR.

Добавляется после базовой Jira/WARP интеграции.

### `SELF_CHECKING`

CR Manager вызывает WARP readiness с context `self_check`.

Self-check не переводит предзаказ в `READY`.

### `DONE`

CR Manager считает свою remediation-задачу завершённой и отправляет callback Coordinator.

Coordinator после этого делает official WARP `final_check`.

### `FAILED`

CR Manager не смог выполнить remediation или self-check вернул `NOT_READY`.

В зависимости от policy задача может перейти в retry или escalation.

### `ESCALATED`

CR Manager передал задачу человеку с контекстом:

- источник;
- plan;
- failed criteria/params;
- Jira/CR;
- remediation instructions;
- выполненные steps;
- ошибки tools/connectors;
- результат WARP self-check.

## State authority

CR Manager владеет только своим task status.

Coordinator владеет preorder status.

WARP владеет readiness verdict.

```text
CR Manager DONE != preorder READY
CR Manager self-check READY != preorder READY
Coordinator final-check READY == основание для preorder READY
```

## Jira/CR

В MVP CR Manager создаёт одну Jira/CR-задачу на remediation-поручение.

В Jira/CR должны фиксироваться:

- preorder/order id;
- source id;
- load plan;
- correlation id;
- WARP check id;
- failed criteria;
- failed params;
- remediation instructions;
- ссылки на trace;
- текущий статус CR Manager task;
- результат self-check.

Пример описания:

```text
Источник: CM12345
План проверки: PLAN_A
WARP check: WARP-CHECK-123
Correlation: CORR-001

Не выполнено:
- C1 / P1: Не заполнено описание
  Инструкция:
  1. Открыть карточку источника
  2. Заполнить обязательное описание
  3. Сохранить изменения

- C1 / P5: Не указан владелец источника
  Инструкция:
  1. Указать владельца источника
  2. Запустить self-check
```

Subtasks можно добавить позже, если remediation нужно распределять по разным исполнителям или субагентам.

## WARP remediation

CR Manager сам запрашивает remediation-инструкции у WARP.

Coordinator не запрашивает remediation-инструкции.

Запрос:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "warp_check_id": "WARP-CHECK-123",
  "criteria_params": [
    {
      "criteria_id": "C1",
      "param_ids": ["P1", "P5"]
    }
  ]
}
```

Ответ:

```json
{
  "items": [
    {
      "criteria_id": "C1",
      "param_id": "P1",
      "title": "Заполнить описание источника",
      "steps": [
        "Открыть карточку источника",
        "Заполнить обязательное описание",
        "Сохранить изменения"
      ],
      "recommended_owner": "source_team",
      "recommended_connector": "source_catalog",
      "automation_possible": false,
      "required_inputs": ["source_description"],
      "expected_result": "Описание источника заполнено"
    }
  ]
}
```

## Self-check

После remediation CR Manager вызывает WARP readiness с context `self_check`.

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "context": "self_check",
  "criteria_params": [
    {
      "criteria_id": "C1",
      "param_ids": ["P1", "P5"]
    }
  ]
}
```

Если WARP self-check возвращает `READY`, CR Manager:

1. обновляет Jira/CR;
2. переводит свою task в `DONE`;
3. отправляет callback Coordinator.

Если WARP self-check возвращает `NOT_READY`, CR Manager:

1. сохраняет оставшиеся failed criteria/params;
2. вычисляет, какие criteria/params были исправлены относительно предыдущей проверки;
3. добавляет комментарий в Jira/CR с результатом self-check:
   - что исправлено;
   - что осталось исправить;
   - текущий WARP score/status;
   - следующий шаг: retry, продолжение remediation или escalation;
4. пишет trace event `self_check_failed` или `remediation_progress_updated`;
5. решает retry или escalation по policy;
6. не сообщает Coordinator, что источник READY.

Частичный прогресс не считается успешным завершением remediation-задачи.
Если было 5 невыполненных criteria/params, а после self-check осталось 2, источник всё ещё `NOT_READY`.
CR Manager фиксирует прогресс в Jira/CR и trace, но не отправляет Coordinator успешный `task-completed`.

Для MVP Coordinator не получает промежуточные partial updates от CR Manager.
Coordinator интересует только финальный outcome remediation-задачи:

- `done` + `self_check_passed=true` — можно запускать WARP official final-check;
- `failed` или `escalated` + `self_check_passed=false` — Coordinator решает retry или переводит предзаказ в `FAILED`.

Coordinator получает callback только в двух случаях:

1. remediation-задача завершена успешно, WARP self-check вернул `READY`;
2. remediation-задача окончательно не может быть выполнена и требует retry/escalation на уровне Coordinator.

## Callback Coordinator

CR Manager сообщает Coordinator только результат своей remediation-задачи.

Текущий POC-compatible callback:

```json
{
  "cr_id": "TASK-123",
  "status": "done",
  "self_check_passed": true,
  "failed_criteria": []
}
```

Coordinator обязан:

- проверить, что task принадлежит preorder/order;
- обработать duplicate callback идемпотентно;
- выполнить official WARP final-check;
- только после final-check менять preorder status.

## Tools

CR Manager tools — это разрешённые действия, которые агент может выполнить.

Tools не должны содержать бизнес-хаос внутри LLM. Tool валидирует вход, вызывает application service, port или adapter и пишет trace.

Минимальный набор:

```text
create_jira_issue
get_warp_remediation
run_connector
run_warp_self_check
complete_jira_issue
notify_coordinator
escalate_to_human
```

### `create_jira_issue`

Создаёт Jira/CR-задачу.

Использует:

- `JiraPort`.

Ограничение:

- idempotency key обязателен;
- повторный вызов не должен создавать дубль.

### `get_warp_remediation`

Получает инструкции WARP по критериям и параметрам.

Использует:

- `WarpPort`.

### `run_connector`

Выполняет разрешённый connector или subagent.

Использует:

- `ConnectorPort`;
- adapter или MCP adapter.

Unsafe operations должны требовать human approval.

### `run_warp_self_check`

Проверяет результат remediation через WARP.

Использует:

- `WarpPort`.

Ограничение:

- self-check не переводит preorder в `READY`.

### `complete_jira_issue`

Обновляет или закрывает Jira/CR после успешного self-check.

Использует:

- `JiraPort`.

### `notify_coordinator`

Отправляет callback Coordinator.

Использует:

- `CoordinatorCallbackPort`.

### `escalate_to_human`

Передаёт задачу человеку с полным контекстом.

Использует:

- `EscalationPort` или `NotificationPort`;
- возможно `JiraPort`.

## Ports and adapters

Порты CR Manager:

```text
TaskRepositoryPort
JiraPort
WarpPort
ConnectorPort
CoordinatorCallbackPort
TracePort
ReasoningPort
EscalationPort
```

Adapters:

```text
InMemoryTaskRepository
MockJiraAdapter
JiraCloudAdapter
MockWarpRemediationAdapter
HttpWarpAdapter
MockConnectorAdapter
HttpConnectorAdapter
McpConnectorAdapter
HttpCoordinatorCallbackAdapter
```

## LLM reasoning

CR Manager — основной кандидат на LLM-agent.

LLM может:

- анализировать remediation-инструкции;
- предложить remediation plan;
- выбрать разрешённые tools;
- подготовить текст Jira-комментария;
- подготовить escalation summary;
- объяснить человеку, что произошло.

LLM не может:

- напрямую менять task status;
- напрямую менять preorder status;
- напрямую вызывать Jira/WARP/DB/API;
- объявлять self-check успешным без WARP;
- скрывать ошибки tools/connectors;
- обходить policy validation.

Production-friendly схема:

```text
CrManagerService
  -> ContextBuilder
  -> ReasoningService
  -> StructuredReasoningResult
  -> PolicyValidator
  -> ToolExecutor
  -> typed tools
  -> ports/adapters
```

LangGraph не обязателен для MVP.

Его можно добавить позже внутри CR Manager reasoning layer, если появятся сложные ветвления, parallel tool execution, retry graph или длинные remediation workflows.

## Memory and context

CR Manager должен разделять:

- execution context — task id, preorder/order id, source id, correlation id, attempt;
- short-term memory — текущий remediation plan и результаты tools;
- long-term memory — успешные remediation patterns, runbooks, known issues;
- conversation memory — диалоговые объяснения для человека.

Long-term memory не является authority.

Если память говорит “обычно это чинится так”, CR Manager всё равно должен проверить:

- WARP remediation;
- policy;
- permissions;
- self-check.

## Trace events

CR Manager пишет свои события сам.

Базовые события:

```text
cr_task_received
jira_issue_created
remediation_requested
remediation_received
remediation_plan_created
tool_execution_started
tool_execution_finished
self_check_started
self_check_finished
cr_task_done
coordinator_notified
cr_task_failed
cr_task_escalated
```

Trace event должен содержать:

- `correlation_id`;
- `agent = cr-manager`;
- `task_id`;
- `agent_run_id`;
- `order_id` или `preorder_id`;
- `source_id`;
- action;
- payload.

## Idempotency

CR Manager должен быть идемпотентным.

Обязательные правила:

- повторный `POST /cr-manager/task` с тем же idempotency key не создаёт дубль;
- повторный `create_jira_issue` не создаёт второй Jira/CR;
- повторный callback Coordinator не ломает состояние;
- повторное закрытие Jira/CR не должно ломать task lifecycle;
- retry должен создавать понятную новую попытку или новый execution run.

В F-002 idempotency key ещё не реализован. Он нужен до real Jira integration.

## Error handling

Ошибки должны классифицироваться:

```text
VALIDATION_ERROR
JIRA_ERROR
WARP_ERROR
CONNECTOR_ERROR
POLICY_DENIED
SELF_CHECK_FAILED
TIMEOUT
UNKNOWN
```

Каждая ошибка должна:

- сохраняться в task state;
- писаться в trace;
- быть видимой в Jira/CR;
- иметь retry/escalation decision.

## Current implementation

Реализовано в F-002:

- `src/agents/cr_manager/`;
- `POST /cr-manager/task`;
- `GET /cr-manager/task/{task_id}`;
- `CrManagerTask`;
- task lifecycle enum;
- `CrManagerTaskRepositoryPort`;
- `InMemoryCrManagerTaskRepository`;
- `CrManagerService`;
- trace event `cr_task_received`;
- unit tests.

Реализовано в F-003:

- `JiraPort`;
- `CreateJiraIssueRequest`;
- `CreateJiraIssueResult`;
- `MockJiraAdapter`;
- idempotency key в `DispatchCrTaskRequest`;
- автоматическое создание mock Jira/CR при создании task;
- task status `JIRA_CREATED`;
- сохранение `jira_issue_id`;
- сохранение `jira_issue_url`;
- trace event `jira_issue_created`;
- idempotency test.

Реализовано в F-004:

- `failed_items` в `DispatchCrTaskRequest`;
- optional `load_plan`;
- optional `warp_check_id`;
- legacy `failed_criteria: list[str]` оставлен для совместимости;
- `WarpRemediationPort`;
- `MockWarpRemediationAdapter`;
- `remediation_items` в task;
- `jira_summary`;
- `jira_description`;
- Jira/CR description с source, preorder/order, load_plan, warp_check_id, failed criteria/params и remediation steps;
- trace event `remediation_received`;
- tests для legacy и structured входа.
- in-process adapter для вызова CR Manager из Coordinator module;
- Coordinator отправляет remediation-поручение в реальный `CrManagerService`, а не в standalone mock;
- tests покрывают Coordinator -> CR Manager flow.

Не реализовано пока:

- connector execution;
- self-check;
- callback Coordinator;
- LLM reasoning;

## Feature mapping

```text
F-002 - CR Manager Agent Skeleton
F-003 - Mock Jira Adapter
F-004 - CR Manager creates Jira/CR from WARP failed criteria
F-005 - Coordinator dispatches to real CR Manager module
F-006 - Real WARP Adapter
```
