# Правила реализации проекта

## Цель

Проект должен быть реализован как production-oriented система ИИ-агентов для подготовки источника данных к созданию реплики.

Первая запускаемая версия может использовать моки и заглушки, но архитектура должна быть спроектирована так, чтобы любую заглушку можно было заменить реальной реализацией без переписывания основной бизнес-логики.

Систему нельзя реализовывать как временный demo-скрипт. С самого начала это должно быть приложение, форма которого соответствует production-решению.

## Язык и runtime

- Проект должен быть написан на Python.
- Предпочтительный API-фреймворк: FastAPI.
- Контракты данных должны описываться через Pydantic-модели.
- Бизнес-логика по возможности должна быть независима от фреймворка.
- Для IO-bound операций нужно использовать async-подход: HTTP-вызовы, очереди, базы данных, внешние коннекторы, сбор trace-событий.
- Проект должен быть структурирован так, чтобы в будущем он мог работать как один модульный сервис или быть разделён на несколько отдельных сервисов.

## Основной архитектурный стиль

Проект должен использовать архитектуру ports-and-adapters, также известную как hexagonal architecture.

Domain-слой и application-слой не должны напрямую зависеть от внешних систем: Jira, WARP, Confluence, баз данных, очередей, файлов или LLM-провайдеров.

Доступ к внешним системам должен выполняться только через явные интерфейсы, которые называются портами.

Конкретные реализации этих портов называются адаптерами.

Пример:

```text
CR Manager Agent
  -> JiraPort
    -> MockJiraAdapter
    -> RealJiraAdapter

Coordinator Agent
  -> WarpPort
    -> MockWarpAdapter
    -> HttpWarpAdapter

Any Agent
  -> TracePort
    -> FileTraceAdapter
    -> HttpTraceCollectorAdapter
    -> PostgresTraceAdapter
```

Приложение должно зависеть от абстракций. Адаптеры должны зависеть от внешних систем.

## Правило production-first MVP

Моки разрешены только как заменяемые адаптеры.

Так можно:

```text
WarpPort -> MockWarpAdapter
WarpPort -> HttpWarpAdapter
```

Так нельзя:

```text
Coordinator has hardcoded fake WARP logic inside its workflow.
CR Manager directly writes fake Jira data inside business logic.
```

Даже в POC следующие элементы должны быть настоящими архитектурными концепциями:

- жизненный цикл заказа;
- жизненный цикл задачи;
- жизненный цикл запуска агента;
- переходы состояний;
- trace-события;
- correlation ID;
- ретраи;
- обработка ошибок;
- интерфейсы адаптеров;
- request/response-схемы.

## Модель ИИ-агента

Система является системой ИИ-агентов, но агенты не должны быть неконтролируемыми чат-промптами.

Агент — это сервисный компонент, у которого есть:

- роль;
- входной контракт;
- выходной контракт;
- разрешённые tools;
- состояние, хранящееся вне промпта;
- trace-логирование;
- обработка ошибок;
- правила ретраев и эскалации.

Правильная модель:

```text
Agent = reasoning layer + tools + memory access + trace
Tool = safe wrapper around a port
Port = stable interface
Adapter = mock or real implementation
```

LLM reasoning может использоваться внутри агентов, но LLM должен действовать только через разрешённые tools.

LLM не должен напрямую вызывать Jira, WARP, базы данных, shell-скрипты или внешние API. Он должен вызывать типизированные tools, которые работают поверх портов и адаптеров.

## LangGraph и агентные фреймворки

LangGraph или другой агентный фреймворк может быть добавлен позже, но он не должен становиться фундаментом всей бизнес-архитектуры.

Основной workflow должен быть выражен через:

- domain-модели;
- application-сервисы;
- state machine;
- порты;
- адаптеры;
- trace-события.

LangGraph можно использовать внутри конкретного агента, если этому агенту нужны сложное reasoning-поведение, планирование, выбор tools, ретраи или ветвление.

Рекомендуемый начальный подход:

- Coordinator: сначала детерминированная оркестрация и state machine.
- WARP: авторитетный валидатор, не обязательно LLM-based.
- CR Manager: основной кандидат на роль ИИ-агента, потому что он интерпретирует remediation-планы и выполняет tools.
- Агенты replica-фазы: могут стать ИИ-агентами позже, когда будут определены их зоны ответственности.

## Границы ответственности агентов

### Coordinator Agent

Coordinator владеет жизненным циклом заказа.

Он может:

- создавать заказы;
- назначать correlation ID;
- запрашивать readiness-проверки у WARP;
- менять статус заказа;
- делегировать remediation-работу в CR Manager;
- принимать callback-и о завершении задач;
- выполнять финальные readiness-проверки;
- запускать replica-фазу после READY;
- контролировать лимит ретраев;
- эскалировать failed-заказы.

Он не должен:

- исправлять проблемы источника;
- знать, как чинить конкретные WARP-критерии;
- напрямую вызывать низкоуровневые коннекторы источника;
- дублировать readiness-логику WARP.

### WARP Agent

WARP — авторитетный валидатор готовности.

Он может:

- оценивать готовность;
- возвращать READY или NOT_READY;
- возвращать score и failed criteria;
- предоставлять remediation-инструкции по критериям;
- поддерживать контексты self-check и final-check.

Он не должен:

- менять состояние источника;
- создавать Jira-задачи;
- принимать решение о статусе заказа;
- запускать инициализацию реплики;
- владеть бизнес-решениями workflow.

### CR Manager Agent

CR Manager владеет исполнением remediation.

Он может:

- получать failed criteria от Coordinator;
- создавать или обновлять Jira-тикеты;
- запрашивать remediation-инструкции у WARP;
- выбирать и выполнять разрешённые коннекторы/tools;
- запускать self-check через WARP;
- повторять неуспешные remediation-шаги;
- сообщать Coordinator об успешном завершении или необходимости эскалации.

Он не должен:

- напрямую выставлять финальный статус заказа READY;
- обходить WARP-проверки;
- решать, что источник официально готов;
- владеть глобальным жизненным циклом заказа.

### Trace Collector

Trace Collector владеет историей наблюдаемости.

Он может:

- принимать trace-события от всех агентов;
- хранить события по correlation ID;
- возвращать хронологический trace;
- предоставлять audit history.

Он не должен:

- содержать бизнес-логику принятия решений;
- менять статус заказа;
- выводить readiness самостоятельно;
- оркестрировать агентов.

## Память и состояние

Агенты не должны полагаться на prompt memory как на источник истины.

Всё важное состояние должно храниться в устойчивом application state:

- заказы;
- задачи;
- попытки;
- запуски агентов;
- readiness-проверки;
- remediation-планы;
- выполнения коннекторов;
- trace-события.

Каждая задача должна содержать достаточно идентификаторов, чтобы агенты не путались при параллельной обработке большого количества задач:

- `order_id`;
- `task_id`;
- `source_id`;
- `correlation_id`;
- `agent_run_id`;
- `attempt`;
- `status`;
- `created_at`;
- `updated_at`.

Агент всегда должен работать внутри явного execution context.

Пример:

```json
{
  "task_id": "TASK-789",
  "order_id": "ORD-456",
  "source_id": "SRC-123",
  "correlation_id": "CORR-001",
  "agent": "cr-manager",
  "attempt": 2,
  "failed_criteria": ["C3.P2"]
}
```

## Correlation и Trace

Каждая внешняя и внутренняя операция должна содержать `correlation_id`.

Каждый агент должен напрямую писать свои trace-события.

Coordinator не должен делать вид, что знает детали внутренней работы других агентов.

Примеры:

```text
Coordinator writes:
- order_created
- status_changed
- decision_delegate_to_cr
- replica_init_requested

WARP writes:
- readiness_check_started
- readiness_check_finished
- remediation_requested

CR Manager writes:
- jira_ticket_created
- remediation_plan_received
- connector_execution_started
- connector_execution_finished
- self_check_passed
- task_completed

Trace Collector writes:
- trace_event_received
```

Trace-события должны быть append-only.

## Модель статусов

Начальные статусы заказа:

- `CREATED`: заказ принят;
- `VALIDATING`: Coordinator запросил readiness-проверку у WARP;
- `WAITING_CR`: источник не готов, CR Manager выполняет исправления;
- `READY`: источник прошёл официальный final-check WARP;
- `FAILED`: превышен лимит ретраев или произошла критическая ошибка.

Только Coordinator может менять статус заказа.

WARP может возвращать readiness-вердикты, но не обновляет статус заказа.

CR Manager может завершать remediation-задачи, но не обновляет финальный статус заказа.

## Ретраи и эскалация

Логика ретраев должна быть явной и настраиваемой.

Лимит ретраев validation cycle по умолчанию равен 3.

Попытка ретрая должна быть отражена в сохранённом состоянии и trace.

Когда лимит ретраев превышен, Coordinator должен перевести заказ в `FAILED` и запустить эскалацию.

Эскалация должна содержать достаточно контекста, чтобы человек мог продолжить работу:

- order ID;
- source ID;
- correlation ID;
- failed criteria;
- последний результат WARP;
- выполненные remediation-шаги;
- ошибки коннекторов;
- ссылки или ID Jira-тикетов;
- ссылка на trace.

## Правило замены адаптеров

У каждой интеграции должно быть минимум две запланированные реализации:

- mock adapter для локального POC;
- real adapter для production-интеграции.

Примеры:

```text
WarpPort:
  MockWarpAdapter
  HttpWarpAdapter

JiraPort:
  MockJiraAdapter
  JiraCloudAdapter

TracePort:
  FileTraceAdapter
  TraceCollectorHttpAdapter

OrderRepositoryPort:
  InMemoryOrderRepository
  PostgresOrderRepository

ConnectorPort:
  MockConnectorAdapter
  RealConfluenceAdapter
  RealConfigUpdaterAdapter
  RealDbMigrationAdapter
```

Замена адаптера не должна требовать изменений domain-кода или application workflow-кода.

## Tools для ИИ-агентов

Если агент использует LLM, его tools должны быть типизированными обёртками вокруг портов.

Пример:

```text
LLM tool: create_jira_issue
  -> JiraPort.create_issue(...)
    -> MockJiraAdapter or RealJiraAdapter

LLM tool: run_warp_self_check
  -> WarpPort.check_readiness(context="self_check")
    -> MockWarpAdapter or HttpWarpAdapter
```

Tools должны:

- валидировать входные данные;
- возвращать структурированный результат;
- писать trace-события там, где это уместно;
- предсказуемо обрабатывать ошибки;
- не раскрывать секреты в промптах;
- соблюдать permissions.

## Безопасность

Все реальные внешние вызовы должны использовать service accounts с минимально необходимыми правами.

Секреты нельзя хранить в коде, промптах, trace-событиях или test fixtures.

Секреты должны загружаться из secret manager или environment configuration.

LLM prompts не должны содержать raw credentials, tokens, private keys или лишние sensitive data.

Доступ к tools должен быть явным. Агент может использовать только tools, назначенные его роли.

## Обработка ошибок

Ошибки должны быть смоделированы явно.

Ошибки внешних адаптеров должны преобразовываться в application-level errors до попадания в workflow.

Система должна различать:

- validation failure;
- remediation failure;
- connector failure;
- timeout;
- authentication или authorization failure;
- malformed response;
- retryable error;
- non-retryable error;
- human escalation required.

## Идемпотентность

Операции, которые могут повторяться, должны быть идемпотентными или защищёнными idempotency keys.

Важные idempotency keys:

- `correlation_id`;
- `order_id`;
- `task_id`;
- `agent_run_id`;
- external request IDs.

Примеры:

- нельзя создавать один и тот же Jira-тикет дважды;
- повторное завершение одной и той же задачи не должно ломать состояние заказа;
- дублирующиеся trace-события должны быть обнаруживаемыми;
- повторный запуск connector execution должен быть безопасным или явно помеченным как unsafe.

## API-дизайн

Все API должны использовать явные request/response-схемы.

Все API должны принимать или прокидывать `correlation_id`.

Начальная поверхность API:

```text
POST /order
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
POST /warp/readiness
POST /warp/get-remediation
POST /cr-manager/task
POST /replica/init
```

Для POC некоторые endpoints могут быть внутренними или mocked, но их контракты всё равно должны быть представлены.

## Persistence

Первая версия может использовать in-memory storage или SQLite.

Архитектура должна позволять заменить storage на PostgreSQL.

Repositories должны быть портами.

Бизнес-логика не должна зависеть от конкретной database library.

## Очереди и async execution

Первая версия для простоты может работать синхронно.

Архитектура должна позволять позже заменить прямые вызовы асинхронными очередями.

Коммуникация Coordinator-to-CR должна проектироваться как task dispatch, даже если в POC она реализована как in-process call.

Будущие production-варианты:

- Redis Queue;
- Celery;
- RabbitMQ;
- Kafka;
- cloud task queues.

Workflow не должен предполагать, что все агенты работают в одном процессе.

## Расширение replica-фазы

Validation-фаза заканчивается, когда Coordinator получает READY-вердикт от WARP во время официального final-check.

После READY Coordinator должен вызвать порт инициализации реплики:

```text
ReplicaInitPort.start(order_id, source_id, correlation_id)
```

Для POC здесь может использоваться mock adapter.

Позже это должно подключаться к следующей группе агентов, например:

- EP Configurator;
- Init Loader;
- Publisher;
- monitoring или reconciliation agents;
- rollback или recovery agents.

Validation-фаза не должна hardcode-ить внутренние детали replica-фазы.

## Предлагаемая структура Python-пакетов

```text
src/
  app/
    main.py
    api/
      order_routes.py
      trace_routes.py
      cr_manager_routes.py
      warp_routes.py
    config/
      settings.py
      container.py

  domain/
    orders/
      models.py
      statuses.py
      state_machine.py
    readiness/
      models.py
      criteria.py
    tasks/
      models.py
      statuses.py
    trace/
      models.py

  application/
    coordinator/
      service.py
      workflow.py
    cr_manager/
      service.py
      agent.py
    warp/
      service.py
    replica/
      service.py

  ports/
    order_repository.py
    task_repository.py
    warp.py
    jira.py
    trace.py
    connector.py
    replica_init.py

  adapters/
    mock/
      warp.py
      jira.py
      trace.py
      connectors.py
      replica_init.py
      repositories.py
    http/
      warp.py
      trace.py
    jira/
      jira_cloud.py
    persistence/
      postgres_orders.py
      postgres_tasks.py

  agents/
    coordinator.py
    cr_manager.py
    warp.py

  tests/
    unit/
    integration/
    contract/
```

## Правила тестирования

Проект должен включать тесты на:

- переходы состояний;
- workflow Coordinator;
- remediation flow CR Manager;
- контракты WARP-адаптеров;
- retry behavior;
- создание trace-событий;
- идемпотентность;
- совместимость контрактов mock-to-real adapter.

Моки должны тестироваться через те же port contracts, что и реальные адаптеры.

## Непереговорные принципы

- WARP — единственный authority по readiness.
- Coordinator — единственный authority по статусу заказа.
- CR Manager — исполнитель, а не финальный судья готовности.
- Каждый агент пишет свои trace-события.
- Каждое важное действие несёт `correlation_id`.
- Моки должны жить за портами.
- LLM-агенты должны действовать только через типизированные tools.
- Prompt memory не является system memory.
- Бизнес-логика не должна зависеть от конкретного внешнего провайдера.
- POC с первого дня должен иметь форму production-решения.
