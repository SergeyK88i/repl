# Roadmap внедрения агентной системы

## Цель roadmap

Цель — перейти от текущего POC на заглушках к production-системе, где агенты постепенно подключаются к реальным API, Jira-пространствам, WARP, ЕР и коннекторам.

Подход:

```text
Сначала устойчивый каркас процесса
→ потом реальные интеграции
→ потом ИИ-слой и расширение агентной сети
```

## Фаза 0. Согласование концепции

### Что уже сделано

- Описана агентная архитектура.
- Выделены ключевые агенты:
  - Координатор;
  - Агент управления требованиями;
  - WARP;
  - CR Manager;
  - ЕР-Координатор / ЕР-Конфигуратор;
  - будущие Init Loader и Публикатор.
- Зафиксирован рубеж `READY`.
- Создан POC backend.
- Создан UI для демонстрации агентного процесса.
- Созданы сценарии и архитектурные правила.

### Цель фазы

Получить согласование:

- что предзаказ до `READY` — отдельный управляемый процесс;
- что пользовательский запрос сначала принимает Координатор и создаёт `DRAFT`-предзаказ;
- что Агент управления требованиями проверяет КЭ, атрибуты и СДО по поручению Координатора;
- что WARP — единственный источник истины по готовности;
- что CR Manager сам создаёт Jira/CR и оркестрирует remediation;
- что после `READY` стартует ЕР-Координатор;
- что агенты внедряются поэтапно.

### Артефакты

- `PROJECT_RULES.md`;
- `SCENARIOS.md`;
- `FEATURE_BACKLOG.md` с историческим блоком `FR-0`;
- `architecture.html`;
- UI console.

## Фаза 1. Укрепление ядра Координатора

### Цель

Сделать Координатор production-ready как владельца жизненного цикла предзаказа.

### Работы

- Перейти от in-memory storage к PostgreSQL.
- Добавить миграции БД.
- Добавить таблицы:
  - `preorders`;
  - `requirements_checks`;
  - `agent_tasks`;
  - `agent_runs`;
  - `readiness_checks`;
  - `trace_events`.
- Добавить idempotency keys для повторных запросов.
- Добавить полноценную error model.
- Добавить настройки через environment/config.
- Добавить OpenAPI-схемы и contract tests.
- Добавить API для получения детального состояния предзаказа.
- Разделить целевую терминологию `preorder_id` и будущий `order_id` ЕР-контура.
- Добавить целевую state machine:
  - `DRAFT`;
  - `REQUIREMENTS_CHECK`;
  - `NEEDS_CLARIFICATION`;
  - `REQUIREMENTS_APPROVED`;
  - `VALIDATING`;
  - `WAITING_CR`;
  - `READY`;
  - `FAILED`.

### Критерии готовности

- Предзаказы и задачи переживают рестарт сервиса.
- Повторный callback CR Manager не ломает состояние.
- Каждый переход статуса проходит через state machine.
- Все действия пишут trace.
- Есть тесты на основные переходы и ошибки.

## Фаза 2. CR Manager Agent и Jira

### Цель

Реализовать CR Manager как отдельный агентный модуль, который получает remediation-поручение от Coordinator, создаёт Jira/CR и готовит основу для дальнейшей оркестрации исправлений.

### Работы

- Создать `src/agents/cr_manager/`.
- Реализовать API:
  - `POST /cr-manager/task`;
  - `GET /cr-manager/task/{task_id}`.
- Добавить task lifecycle:
  - `RECEIVED`;
  - `JIRA_CREATED`;
  - `REMEDIATION_RECEIVED`;
  - `EXECUTING`;
  - `SELF_CHECKING`;
  - `DONE`;
  - `FAILED`;
  - `ESCALATED`.
- Реализовать Jira adapter:
  - сначала mock;
  - затем real Jira adapter.
- Реализовать WARP remediation adapter.
- Реализовать создание Jira/CR с критериями, параметрами и инструкциями WARP.
- Добавить callback в Coordinator.
- Зафиксировать правило: Coordinator только поручает remediation, а Jira/CR создаёт CR Manager.

### Критерии готовности

- Coordinator создаёт remediation-поручение при WARP `NOT_READY`.
- CR Manager принимает задачу от Coordinator.
- CR Manager создаёт Jira/CR.
- CR Manager получает remediation-инструкции от WARP или mock WARP.
- CR Manager сообщает Coordinator результат.
- Все действия пишут trace.

## Фаза 3. Реальный WARP adapter

### Цель

Заменить `MockWarpAdapter` на реальную интеграцию с WARP.

### Работы

- Зафиксировать финальный контракт WARP:
  - readiness request;
  - readiness response;
  - score;
  - failed criteria;
  - audit hash;
  - remediation request;
  - remediation response.
- Реализовать `HttpWarpAdapter`.
- Добавить обработку timeout/retry.
- Добавить mapping внешнего WARP-контракта во внутренние Pydantic-модели.
- Добавить contract tests.
- Добавить mock server или recorded fixtures для тестов.

### Критерии готовности

- Координатор может выполнять initial-check и final-check через настоящий WARP API.
- Формат WARP можно менять внутри adapter без переписывания Координатора.
- Ошибки WARP корректно классифицируются.

## Фаза 4. CR Manager remediation orchestration

### Цель

Расширить CR Manager от создания Jira/CR до реального исполнения remediation через tools/connectors/subagents.

### Работы

- Реализовать connector registry:
  - Confluence connector;
  - config-updater connector;
  - db-migration connector.
- Добавить self-check через WARP.
- Добавить retry/escalation policy.
- Добавить LLM reasoning для планирования remediation, когда появятся реальные инструкции и tools.

### Критерии готовности

- Выполняет mock/real коннекторы.
- Делает self-check.
- Делает retry или escalation по policy.
- Пишет детальные trace-события tool execution.

## Фаза 5. Requirements Agent

### Цель

Реализовать агента, который проверяет качество пользовательского входа до технической проверки WARP.

### Работы

- Создать `src/agents/requirements/`.
- Определить контракт проверки:
  - КЭ источника;
  - выбранные атрибуты;
  - текст запроса пользователя;
  - контекст СДО.
- Реализовать API:
  - `POST /requirements/check`;
  - получение статуса проверки.
- Реализовать mock adapters:
  - СДО;
  - каталог источников;
  - каталог атрибутов.
- Реализовать result model:
  - `APPROVED`;
  - `NEEDS_CLARIFICATION`;
  - `REJECTED`;
  - `HUMAN_REVIEW_REQUIRED`.
- Подключить Coordinator через `RequirementsPort`.
- Добавить trace-события Requirements Agent.

### Критерии готовности

- Координатор создаёт `DRAFT`-предзаказ и поручает проверку Requirements Agent.
- Предзаказ не идёт в WARP, пока требования не подтверждены.
- Если данных не хватает, система возвращает пользователю понятные уточнения.
- Mock-адаптеры можно заменить реальными API СДО и каталогов без переписывания workflow.

## Фаза 6. Trace Collector

### Цель

Вынести trace из in-memory adapter в отдельный устойчивый сервис или storage.

### Работы

- Определить trace event schema.
- Реализовать `TraceCollector`:
  - `POST /trace/event`;
  - `GET /trace/{correlation_id}`.
- Добавить batch/async запись событий.
- Добавить хранение в PostgreSQL или специализированном хранилище.
- Добавить UI-представление trace.
- Добавить correlation across agents.

### Критерии готовности

- Каждый агент пишет свои события напрямую.
- Trace не теряется при падении одного агента.
- Можно восстановить хронологию предзаказа по `correlation_id`.

## Фаза 7. ЕР-Координатор / ЕР-Конфигуратор

### Цель

Реализовать следующий агент после READY.

### Работы

- Создать `src/agents/ep_coordinator/`.
- Заменить `MockReplicaInitAdapter` на `EpCoordinatorAdapter`.
- Определить контракт передачи READY-предзаказа.
- Реализовать создание заказа в другом Jira-пространстве.
- Реализовать подбор параметров реплики.
- Реализовать генерацию конфига для ЕР.
- Добавить статусы после READY:
  - `EP_TASK_CREATED`;
  - `CONFIGURING`;
  - `CONFIG_READY`;
  - `FAILED`;
  - `ESCALATED`.
- Добавить trace-события ЕР-Координатора.

### Критерии готовности

- После READY Координатор передаёт задачу ЕР-Координатору.
- Создаётся заказ в нужном Jira-пространстве.
- Формируется конфиг для ЕР.
- Ошибки конфигурации эскалируются с контекстом.

## Фаза 8. Init Loader и Публикатор

### Цель

Довести процесс после READY до фактической загрузки и публикации реплики.

### Работы

- Реализовать Init Loader:
  - запуск первичной загрузки;
  - контроль состояния загрузки;
  - retry;
  - trace.
- Реализовать Публикатор:
  - проверка результата;
  - публикация;
  - финальный статус;
  - уведомления.
- Добавить статусы:
  - `LOADING`;
  - `LOAD_FAILED`;
  - `LOADED`;
  - `PUBLISHING`;
  - `PUBLISHED`;
  - `PUBLICATION_FAILED`.

### Критерии готовности

- Реплика создаётся, загружается и публикуется.
- Каждый шаг имеет владельца-агента.
- Есть trace от предзаказа до публикации.

## Фаза 9. ИИ-слой агентов

### Цель

Добавить LLM reasoning там, где он реально полезен, не ломая deterministic workflow.

### Где нужен ИИ

Координатор:

- объяснение статуса пользователю;
- анализ trace;
- подготовка human escalation summary;
- классификация нестандартных ошибок.

Requirements Agent:

- разбор свободного текста пользователя;
- сопоставление запроса с КЭ и атрибутами;
- формирование уточняющих вопросов;
- объяснение причин отказа или human review.

CR Manager:

- интерпретация remediation-инструкций;
- выбор коннектора;
- планирование последовательности исправлений;
- подготовка комментариев в Jira;
- решение retry vs escalation в разрешённых рамках.

ЕР-Координатор:

- подбор параметров реплики;
- объяснение выбранной конфигурации;
- диагностика конфликтов конфигурации.

### Принцип

LLM не должен напрямую менять состояние.

Правильная модель:

```text
LLM предлагает действие
→ workflow проверяет правила
→ tool выполняет действие через port
→ trace фиксирует результат
```

### Критерии готовности

- LLM вызывает только разрешённые typed tools.
- Все действия проверяются guardrails/state machine.
- Промпты не содержат секретов.
- Есть audit trail решений.

## Фаза 10. Production hardening

### Работы

- AuthN/AuthZ для внутренних API.
- Service accounts с минимальными правами.
- Secret management.
- Observability:
  - metrics;
  - logs;
  - traces;
  - dashboards.
- Rate limits.
- Circuit breakers.
- Dead-letter queue.
- Replay failed tasks.
- Load testing.
- Security review.
- Runbooks для эксплуатации.

### Критерии готовности

- Система готова к пилоту на реальных источниках.
- Есть rollback/эскалация.
- Есть мониторинг и алерты.
- Есть понятная операционная документация.

## Предлагаемый порядок внедрения

```text
1. Утвердить концепцию и READY как рубеж
2. Укрепить Координатор и storage
3. Реализовать CR Manager и Jira/CR creation
4. Подключить настоящий WARP readiness
5. Расширить CR Manager до remediation orchestration
6. Реализовать Requirements Agent и подключить СДО/каталоги
7. Реализовать Trace Collector
8. Реализовать ЕР-Координатор
9. Добавить Init Loader и Публикатор
10. Добавить LLM reasoning там, где есть ценность
11. Провести production hardening
```
