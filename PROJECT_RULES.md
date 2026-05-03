# Правила реализации проекта

## Цель

Проект должен быть реализован как production-oriented система ИИ-агентов для подготовки источника данных к созданию реплики.

Бизнесовая цель системы шире, чем одна readiness-проверка: Coordinator принимает пользовательский запрос, создаёт предзаказ, доводит источник до официальной готовности, а после READY передаёт работу агентам ЕР-контура для создания и настройки реплики.

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

- жизненный цикл предзаказа;
- момент превращения предзаказа в заказ после READY;
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
Agent = application service + domain logic + ports/adapters + optional LLM
LLM = reasoning + skills + typed tools
Tool = safe wrapper around a port
Port = stable interface
Adapter = mock or real implementation
MCP server = optional implementation detail for tools/adapters
Skill = instruction/playbook for LLM behavior, not system state
```

LLM reasoning может использоваться внутри агентов, но LLM должен действовать только через разрешённые tools.

LLM не должен напрямую вызывать Jira, WARP, базы данных, shell-скрипты или внешние API. Он должен вызывать типизированные tools, которые работают поверх портов и адаптеров.

MCP servers и skills можно использовать в LLM-агентах, но они не должны заменять domain logic, state machine, contracts, ports и adapters.

MCP server — это способ дать LLM или tool доступ к внешней системе. В нашей архитектуре MCP рассматривается как возможная реализация adapter или tool execution, например `JiraMcpAdapter`, `ConfluenceMcpAdapter`, `KnowledgeBaseMcpAdapter`.

Skill — это инструкция или playbook для LLM-слоя агента: как анализировать задачу, как выбирать tool, когда делать self-check, когда эскалировать человеку. Skill не является источником истины по статусам, правам, контрактам и бизнес-правилам.

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

- Coordinator: сначала детерминированная оркестрация и state machine вокруг предзаказа.
- Requirements Agent: ранний кандидат на LLM-слой, потому что он понимает пользовательский запрос, КЭ, атрибутный состав и согласование с СДО.
- WARP: внешний авторитетный валидатор другой команды; в нашем проекте реализуется только порт, mock adapter для POC и HTTP adapter для real API.
- CR Manager: основной кандидат на роль ИИ-агента, потому что он интерпретирует remediation-планы и выполняет tools.
- Агенты replica-фазы: могут стать ИИ-агентами позже, когда будут определены их зоны ответственности.

## Границы ответственности агентов

### Coordinator Agent

Coordinator владеет жизненным циклом предзаказа и общей целью процесса.

Пользовательский запрос сначала попадает к Coordinator. Coordinator создаёт предзаказ в статусе `DRAFT`, назначает идентификаторы и дальше сам решает, какого специализированного агента подключить.

Он может:

- создавать предзаказы;
- назначать correlation ID;
- поручать Requirements Agent проверку КЭ, атрибутного состава и согласование с СДО;
- запрашивать readiness-проверки у WARP;
- менять статус предзаказа;
- делегировать remediation-работу в CR Manager;
- принимать callback-и о завершении задач;
- выполнять финальные readiness-проверки;
- передавать READY-предзаказ в ЕР-контур;
- контролировать лимит ретраев;
- эскалировать failed-предзаказы.

Он не должен:

- исправлять проблемы источника;
- знать, как чинить конкретные WARP-критерии;
- напрямую вызывать низкоуровневые коннекторы источника;
- дублировать readiness-логику WARP;
- создавать Jira-задачи за CR Manager.

### Requirements Agent

Requirements Agent отвечает за качество входа до технической проверки источника.

Он может:

- проверять корректность выбранного КЭ источника;
- проверять атрибутный состав предзаказа;
- общаться с СДО или его API для согласования;
- возвращать Coordinator результат проверки: approved, needs clarification, rejected, human review required;
- формировать список уточняющих вопросов пользователю.

Он не должен:

- владеть жизненным циклом предзаказа;
- менять статус предзаказа напрямую;
- проверять техническую готовность источника вместо WARP;
- создавать CR или Jira-задачи;
- запускать ЕР-фазу.

### WARP Integration

WARP — авторитетный валидатор готовности.

В production WARP является внешним сервисом другой команды. В нашем проекте WARP представлен через `WarpPort`, mock adapter для POC и HTTP adapter для real API.

Он может:

- оценивать готовность;
- возвращать READY или NOT_READY;
- возвращать score и failed criteria;
- предоставлять remediation-инструкции по критериям;
- поддерживать контексты self-check и final-check.

Он не должен:

- менять состояние источника;
- создавать Jira-задачи;
- принимать решение о статусе предзаказа;
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

- напрямую выставлять финальный статус предзаказа READY;
- обходить WARP-проверки;
- решать, что источник официально готов;
- владеть глобальным жизненным циклом предзаказа;
- ожидать, что Coordinator создаст Jira-задачу за него.

### Trace Collector

Trace Collector владеет историей наблюдаемости.

Он может:

- принимать trace-события от всех агентов;
- хранить события по correlation ID;
- возвращать хронологический trace;
- предоставлять audit history.

Он не должен:

- содержать бизнес-логику принятия решений;
- менять статус предзаказа;
- выводить readiness самостоятельно;
- оркестрировать агентов.

## Память и состояние

Агенты не должны полагаться на prompt memory как на источник истины.

Всё важное состояние должно храниться в устойчивом application state:

- предзаказы;
- заказы ЕР-контура после READY;
- задачи;
- попытки;
- запуски агентов;
- readiness-проверки;
- remediation-планы;
- выполнения коннекторов;
- trace-события.

Каждая задача должна содержать достаточно идентификаторов, чтобы агенты не путались при параллельной обработке большого количества задач:

- `preorder_id` или временный `order_id` POC;
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
  "preorder_id": "PRE-456",
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
- preorder_created
- status_changed
- decision_delegate_to_cr
- ep_task_requested

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

Начальные статусы предзаказа:

- `DRAFT`: предзаказ создан, но ещё не проверен;
- `REQUIREMENTS_CHECK`: Requirements Agent проверяет КЭ, атрибутный состав и СДО;
- `NEEDS_CLARIFICATION`: нужны уточнения от пользователя;
- `REQUIREMENTS_APPROVED`: предзаказ корректен и может идти на техническую проверку;
- `VALIDATING`: Coordinator запросил readiness-проверку у WARP;
- `WAITING_CR`: источник не готов, CR Manager выполняет исправления;
- `READY`: источник прошёл официальный final-check WARP;
- `FAILED`: превышен лимит ретраев или произошла критическая ошибка.

Только Coordinator может менять статус предзаказа.

WARP может возвращать readiness-вердикты, но не обновляет статус предзаказа.

CR Manager может завершать remediation-задачи и создавать Jira/CR, но не обновляет финальный статус предзаказа.

После `READY` может появиться отдельный `order_id` в ЕР/Jira-контуре. До `READY` системная сущность является предзаказом, даже если в текущем POC поле технически называется `order_id`.

## Ретраи и эскалация

Логика ретраев должна быть явной и настраиваемой.

Лимит ретраев validation cycle по умолчанию равен 3.

Попытка ретрая должна быть отражена в сохранённом состоянии и trace.

Когда лимит ретраев превышен, Coordinator должен перевести предзаказ в `FAILED` и запустить эскалацию.

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
  JiraMcpAdapter

TracePort:
  FileTraceAdapter
  TraceCollectorHttpAdapter

OrderRepositoryPort:
  InMemoryOrderRepository
  PostgresOrderRepository

ConnectorPort:
  MockConnectorAdapter
  RealConfluenceAdapter
  ConfluenceMcpAdapter
  RealConfigUpdaterAdapter
  RealDbMigrationAdapter
```

Замена адаптера не должна требовать изменений domain-кода или application workflow-кода.

## Tools для ИИ-агентов

Если агент использует LLM, его tools должны быть типизированными обёртками вокруг портов.

Tool и adapter не являются одним и тем же уровнем.

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
LLM reasoning
  -> tool create_jira_issue
    -> JiraPort
      -> JiraCloudAdapter
        -> Jira API
```

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

Если tool работает через MCP server, он всё равно должен сохранять тот же контракт безопасности:

```text
LLM reasoning
  -> typed tool
    -> port
      -> MCP adapter
        -> MCP server
          -> external system
```

Пример:

```text
create_jira_issue
  -> JiraPort.create_issue(...)
    -> JiraMcpAdapter
      -> Jira MCP server
        -> Jira API
```

MCP server не должен становиться скрытым обходом permissions, trace, validation или state machine.

## Границы решений LLM

LLM может принимать решения внутри своей роли, но не должна быть единственным контролёром критичных переходов и прав.

LLM может:

- понимать свободный текст;
- выбирать следующий tool из разрешённых;
- объяснять статус;
- готовить вопросы пользователю;
- планировать remediation-шаги;
- готовить комментарии и escalation summary.

LLM не должна самостоятельно:

- переводить предзаказ в `READY`;
- обходить WARP;
- игнорировать readiness меньше 100%;
- создавать заказ без обязательных проверок;
- повторно создавать один и тот же Jira ticket;
- отправлять секреты в trace или prompt;
- обходить state machine, permissions и idempotency rules.

Правильная модель:

```text
LLM предлагает намерение
  -> tool валидирует действие
    -> workflow проверяет правила
      -> port вызывает adapter
        -> state machine контролирует статус
          -> trace фиксирует результат
```

## Skills для LLM-агентов

Skills можно использовать как инструкции для LLM-слоя конкретного агента.

Примеры skills для CR Manager:

```text
skills/
  remediation.md
  escalation.md
  jira_commenting.md
```

Skill может описывать:

- как читать remediation-инструкции;
- как выбирать connector;
- как формулировать комментарий в Jira;
- когда запускать self-check;
- когда готовить escalation summary.

Skill не должен:

- менять статус предзаказа;
- объявлять источник READY;
- обходить WARP;
- обходить typed tools;
- хранить секреты;
- подменять domain rules или application workflow.

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
- `preorder_id` или временный `order_id` POC;
- `task_id`;
- `agent_run_id`;
- external request IDs.

Примеры:

- CR Manager не должен создавать один и тот же Jira-тикет дважды;
- повторное завершение одной и той же задачи не должно ломать состояние предзаказа;
- дублирующиеся trace-события должны быть обнаруживаемыми;
- повторный запуск connector execution должен быть безопасным или явно помеченным как unsafe.

## API-дизайн

Все API должны использовать явные request/response-схемы.

Все API должны принимать или прокидывать `correlation_id`.

Начальная поверхность API:

```text
POST /order                      # POC-совместимое создание предзаказа
POST /preorders                  # целевое создание предзаказа
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
POST /requirements/check
POST /warp/readiness
POST /warp/get-remediation
POST /cr-manager/task
POST /ep-coordinator/task
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

После READY Coordinator должен вызвать порт передачи задачи в ЕР-контур:

```text
EpCoordinatorPort.start(preorder_id, source_id, correlation_id)
```

Для POC здесь может использоваться mock adapter.

Позже это должно подключаться к следующей группе агентов, например:

- EP Coordinator / EP Configurator;
- Init Loader;
- Publisher;
- monitoring или reconciliation agents;
- rollback или recovery agents.

Validation-фаза не должна hardcode-ить внутренние детали replica-фазы.

## Структура Python-пакетов

Целевая структура проекта должна быть agent-oriented.

Каждый агент должен жить в собственной папке внутри `src/agents/{agent_name}/` и иметь свою внутреннюю архитектуру: `api`, `domain`, `application`, `ports`, `adapters`, а для LLM-агентов также `tools`.

Такой подход нужен, чтобы разные команды могли независимо разрабатывать разных агентов:

- команда Coordinator работает преимущественно в `src/agents/coordinator/`;
- команда Requirements Agent работает преимущественно в `src/agents/requirements/`;
- команда CR Manager работает преимущественно в `src/agents/cr_manager/`;
- команда EP Coordinator работает преимущественно в `src/agents/ep_coordinator/`;
- общие контракты и базовые типы согласуются через `src/shared/`.

Агенты не должны импортировать внутренний application/domain-код друг друга.

Взаимодействие между агентами должно идти через:

- shared contracts;
- порты;
- adapters;
- HTTP API;
- task queue или event bus в будущей production-версии.

Для POC агент может вызывать другой агент через in-process adapter. Для production тот же порт должен уметь работать через HTTP, gRPC, очередь или другой межсервисный транспорт.

Запрещённый пример:

```python
from agents.warp.application.service import WarpService
```

Разрешённая модель:

```python
from shared.contracts.readiness import ReadinessRequest, ReadinessResponse
from agents.coordinator.ports.warp import WarpPort
```

Дальше конкретная реализация `WarpPort` выбирается конфигурацией:

```text
WarpPort
  -> HttpWarpAdapter
  -> MockWarpAdapter
```

Цель: каждый агент должен быть достаточно самодостаточным, чтобы позже его можно было вынести из монолита в отдельное приложение без переписывания бизнес-логики.

Эволюционный путь:

```text
1. Один репозиторий, один процесс, mock adapters для POC.
2. Подключение real adapters к уже существующим внешним сервисам, включая WARP.
3. CR Manager выносится в отдельный сервис.
4. EP Coordinator выносится в отдельный сервис.
5. Добавляется очередь или event bus между агентами.
6. Агенты масштабируются независимо.
```

Рекомендуемая структура:

```text
src/
  app/
    main.py
    config/
      settings.py
      container.py

  shared/
    contracts/
      orders.py
      readiness.py
      remediation.py
      tasks.py
      trace.py
      replica.py
    domain/
      ids.py
      errors.py
      timestamps.py
    ports/
      trace.py
      event_bus.py
    telemetry/
      correlation.py
      trace_events.py
    security/
      permissions.py
      service_accounts.py

  agents/
    requirements/
      api/
        routes.py
      domain/
        preorder_requirements.py
        validation_result.py
      application/
        service.py
        agent.py
      ports/
        sdo.py
        source_catalog.py
        attribute_catalog.py
        trace.py
      adapters/
        mock/
          sdo.py
          source_catalog.py
          attribute_catalog.py
        http/
          sdo.py
          source_catalog.py
      tools/
        check_source_ke.py
        validate_attributes.py
        ask_sdo.py

    coordinator/
      api/
        routes.py
      domain/
        order.py
        statuses.py
        state_machine.py
      application/
        service.py
        workflow.py
      ports/
        order_repository.py
        requirements.py
        warp.py
        cr_manager.py
        ep_coordinator.py
        trace.py
      adapters/
        in_process/
          requirements.py
          warp.py
          cr_manager.py
          ep_coordinator.py
        http/
          requirements.py
          warp.py
          cr_manager.py
          ep_coordinator.py
        persistence/
          in_memory_orders.py
          postgres_orders.py

    cr_manager/
      api/
        routes.py
      domain/
        task.py
        statuses.py
        remediation_execution.py
      application/
        service.py
        agent.py
      ports/
        task_repository.py
        jira.py
        warp.py
        connector.py
        coordinator_callback.py
        trace.py
      adapters/
        mock/
          jira.py
          warp.py
          connectors.py
          coordinator_callback.py
          task_repository.py
        mcp/
          jira.py
          confluence.py
        http/
          warp.py
          coordinator_callback.py
        jira/
          jira_cloud.py
        connectors/
          confluence.py
          config_updater.py
          db_migration.py
      tools/
        create_jira_issue.py
        get_warp_remediation.py
        run_connector.py
        run_warp_self_check.py
      skills/
        remediation.md
        escalation.md

    ep_coordinator/
      api/
        routes.py
      domain/
        ep_task.py
        statuses.py
      application/
        service.py
        agent.py
      ports/
        jira.py
        configurator.py
        loader.py
        trace.py
      adapters/
        mock/
          jira.py
          configurator.py
          loader.py
      tools/
        create_ep_order.py
        select_replica_parameters.py
        generate_ep_config.py

  tests/
    coordinator/
    requirements/
    warp/
    cr_manager/
    ep_coordinator/
    contract/
    integration/
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
- Coordinator — единственный authority по статусу предзаказа.
- CR Manager — исполнитель, а не финальный судья готовности.
- CR Manager, а не Coordinator, создаёт Jira/CR-задачи и оркестрирует remediation.
- Каждый агент пишет свои trace-события.
- Каждое важное действие несёт `correlation_id`.
- Моки должны жить за портами.
- LLM-агенты должны действовать только через типизированные tools.
- Prompt memory не является system memory.
- Бизнес-логика не должна зависеть от конкретного внешнего провайдера.
- POC с первого дня должен иметь форму production-решения.
