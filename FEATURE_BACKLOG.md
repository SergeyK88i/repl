# Feature backlog

Этот файл связывает верхнеуровневый `ROADMAP.md` с конкретными реализуемыми фичами.

Принцип работы:

```text
ROADMAP.md показывает крупные фазы развития
FEATURE_BACKLOG.md переводит эти фазы в FR-релизы и конкретные F-фичи
каждая фича имеет цель, границы, acceptance criteria и статус
```

`FR-*` — крупный этап из roadmap или исторический этап проекта.
`F-*` — конкретная реализуемая фича внутри FR.

Пример:

```text
ROADMAP.md Фаза 2 -> FEATURE_BACKLOG.md FR-2
FR-2 -> F-002, F-003, F-004, F-005
```

Статусы:

```text
planned     - запланировано
next        - следующая фича в работе
in_progress - сейчас реализуется
done        - реализовано и проверено
blocked     - есть внешний блокер
```

## FR-0. Presentation POC на заглушках

Статус: `done`

Roadmap phase: Фаза 0. Согласование концепции.

Цель:

```text
Собрать первый production-shaped POC, чтобы показать руководству идею агентной системы: от пользовательского предзаказа до READY и запуска следующей фазы репликации.
```

Что было сделано:

- зафиксирована агентная архитектура и границы ответственности;
- выбран Python/FastAPI как базовый технологический стек;
- описаны правила проекта в `PROJECT_RULES.md`;
- описаны сценарии в `SCENARIOS.md`;
- подготовлен бизнесовый материал в `MANAGEMENT_PRESENTATION_NOTES.md`;
- создан backend POC вокруг Coordinator Agent;
- реализована state machine статусов предзаказа;
- добавлены replaceable ports/adapters;
- реализованы mock adapters:
  - `MockWarpAdapter`;
  - `MockCrManagerAdapter`;
  - `MockReplicaInitAdapter`;
  - in-memory repositories;
  - in-memory trace adapter;
- добавлена идемпотентная обработка повторного callback-а;
- добавлена проверка принадлежности CR/remediation-задачи предзаказу;
- реализована retry-логика до `FAILED`;
- добавлены trace events от Координатора, WARP и CR Manager;
- создан chat-first UI для демонстрации агентной комнаты;
- добавлена визуальная схема взаимодействия агентов;
- подготовлены презентационные HTML-страницы;
- добавлены unit tests для текущего POC.

Основные POC endpoints:

```text
POST /order
GET  /order/{order_id}
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
GET  /console
```

Демонстрационные сценарии:

- источник сразу проходит WARP и становится `READY`;
- источник не готов, Координатор создаёт remediation-поручение для CR Manager;
- CR Manager завершает задачу, Координатор делает WARP final-check и переводит предзаказ в `READY`;
- источник не проходит после лимита попыток и уходит в `FAILED`.

Acceptance criteria:

- можно показать end-to-end концепцию без реальных внешних систем;
- заглушки спрятаны за ports/adapters и могут заменяться реальными API;
- Coordinator не создаёт Jira/CR сам, а только создаёт remediation-поручение;
- READY ставит только Coordinator после WARP final-check;
- сценарии можно запускать через API и UI;
- документация объясняет идею для разработки и для руководства.

Результат:

```text
Идея -> архитектурные правила -> backend POC -> UI-демонстрация -> сценарии -> roadmap -> feature backlog
```

## FR-1. Coordinator Core и LLM-инфраструктура

Статус: `in_progress`

Roadmap phase: Фаза 1. Укрепление ядра Координатора.

Цель:

```text
Укрепить основу системы вокруг Coordinator Agent и подготовить общую LLM-инфраструктуру для будущих reasoning-агентов.
```

### F-001. LLM Provider Foundation

Статус: `done`

Roadmap phase: Фаза 1. Укрепление ядра Координатора.

Цель:

```text
Подключить LLM provider через общий порт и adapter, чтобы будущие агенты могли использовать reasoning без прямой зависимости от конкретного LLM API.
```

Что входит:

- общий `LlmPort`;
- общие LLM contracts;
- `GigaChatAdapter`;
- token refresh;
- chat completions;
- embeddings;
- SSL/CA bundle settings;
- локальный smoke-test script;
- `.env.example`;
- защита `.env.local` от commit;
- unit tests adapter-а без реального сетевого вызова.

Затронутые слои:

- `src/shared/contracts/`;
- `src/shared/ports/`;
- `src/shared/adapters/`;
- `src/app/config/`;
- `scripts/`;
- `tests/`.

Acceptance criteria:

- LLM provider подключается через `LlmPort`;
- GigaChat adapter не хранит conversation history;
- секреты не попадают в git;
- есть smoke-test реального LLM вызова;
- unit tests проходят;
- реальный smoke-test GigaChat проходит с локальным `.env.local`.

Проверка:

```text
PYTHONPATH=src python3 -m unittest discover -s tests
set -a && source .env.local && set +a && PYTHONPATH=src python3 scripts/llm_smoke.py
```

## FR-2. CR Manager Agent и Jira

Статус: `in_progress`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Реализовать CR Manager как отдельный агентный модуль, который получает remediation-поручение от Coordinator, создаёт Jira/CR и готовит основу для дальнейшей оркестрации исправлений.
```

### F-002. CR Manager Agent Skeleton

Статус: `done`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Создать самостоятельный модуль CR Manager, который принимает remediation-поручение от Coordinator и ведёт собственный task lifecycle.
```

Что входит:

- `src/agents/cr_manager/`;
- `api/routes.py`;
- `domain/task.py`;
- `domain/statuses.py`;
- `application/service.py`;
- `ports/task_repository.py`;
- mock/in-memory adapters;
- базовые trace events;
- unit tests.

Acceptance criteria:

- CR Manager принимает `POST /cr-manager/task`;
- создаёт внутреннюю task record;
- возвращает `task_id`;
- пишет trace event `cr_task_received`;
- может быть вызван из Coordinator через port/adapter;
- application/domain не зависят от FastAPI/Jira/WARP SDK напрямую.

Реализовано сейчас:

- `src/agents/cr_manager/`;
- `POST /cr-manager/task`;
- `GET /cr-manager/task/{task_id}`;
- domain model `CrManagerTask`;
- task lifecycle enum;
- `CrManagerTaskRepositoryPort`;
- in-memory task repository;
- `CrManagerService`;
- trace event `cr_task_received`;
- unit tests для service и route handlers.

Следующие ports из исходного объёма будут добавлены в следующих фичах:

- `ports/jira.py` — в `F-003`;
- `ports/warp.py` — в `F-004`;
- `ports/coordinator_callback.py` — в `F-005`.

### F-003. Mock Jira Adapter

Статус: `done`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Добавить заменяемый JiraPort и mock adapter, чтобы CR Manager мог создавать CR/Jira-задачи без реальной Jira.
```

Acceptance criteria:

- есть `JiraPort.create_issue`;
- mock adapter создаёт predictable issue id/url;
- CR Manager сохраняет связь task_id -> jira_issue_id;
- повторный вызов не создаёт дубль при том же idempotency key.

Реализовано сейчас:

- `JiraPort.create_issue`;
- `CreateJiraIssueRequest`;
- `CreateJiraIssueResult`;
- `MockJiraAdapter`;
- автоматическое создание mock Jira/CR при `POST /cr-manager/task`;
- статус CR Manager task `JIRA_CREATED`;
- сохранение `jira_issue_id` и `jira_issue_url`;
- trace event `jira_issue_created`;
- idempotency key в `DispatchCrTaskRequest`;
- повторный `POST /cr-manager/task` с тем же idempotency key возвращает существующую task и не создаёт дубль Jira/CR.

### F-004. CR Manager Creates Jira/CR From WARP Failed Criteria

Статус: `next`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Научить CR Manager создавать Jira/CR с источником, load_plan, warp_check_id, критериями, параметрами и remediation-инструкциями.
```

Acceptance criteria:

- CR Manager принимает legacy `failed_criteria: list[str]` без поломки текущего Coordinator;
- CR Manager принимает structured `failed_items` с `criteria_id` и `failed_params`;
- CR Manager принимает optional `load_plan` и `warp_check_id`;
- CR Manager запрашивает remediation у WARP adapter;
- CR Manager создаёт Jira/CR с читаемым описанием;
- trace содержит `jira_issue_created`;
- tests покрывают happy path и idempotency.

Migration note:

```text
В F-004 расширяем контракт, но не удаляем legacy failed_criteria: list[str].
Legacy-формат будет удалён отдельной будущей фичей после перехода Coordinator и WARP adapter на structured failed_items.
```

### F-005. Coordinator Dispatches To Real CR Manager Module

Статус: `planned`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Заменить текущий mock CR Manager adapter на in-process или HTTP adapter к новому CR Manager module.
```

Acceptance criteria:

- Coordinator создаёт remediation-поручение при WARP `NOT_READY`;
- поручение попадает в CR Manager module;
- Coordinator сохраняет task id;
- дубли callback не ломают состояние;
- tests покрывают Coordinator -> CR Manager flow.

### F-012. Remove Legacy Failed Criteria Contract

Статус: `planned`

Roadmap phase: migration cleanup after Coordinator/WARP structured contract adoption.

Цель:

```text
Удалить legacy `failed_criteria: list[str]` из CR Manager-facing контракта после того, как Coordinator и WARP adapter начнут передавать structured failed_items.
```

Acceptance criteria:

- Coordinator отправляет `failed_items` вместо legacy-only `failed_criteria`;
- WARP adapter маппит failed criteria/params в structured contract;
- CR Manager не зависит от строкового формата `C3.P2`;
- tests обновлены на structured failed criteria;
- документация помечает legacy контракт удалённым.

## FR-3. Real WARP Adapter

Статус: `planned`

Roadmap phase: Фаза 3. Реальный WARP adapter.

Цель:

```text
Заменить mock WARP на интеграцию с внешним WARP API другой команды через `WarpPort` и `HttpWarpAdapter`.
```

### F-006. Real WARP Adapter

Статус: `planned`

Roadmap phase: Фаза 3. Реальный WARP adapter.

Цель:

```text
Подключить внешний WARP API другой команды через `WarpPort`.
```

Acceptance criteria:

- реализован `HttpWarpAdapter`;
- поддержан `load_plan`;
- response mapping сохраняет failed criteria/params;
- Coordinator-facing contract не содержит remediation-инструкции;
- CR Manager-facing remediation contract получает инструкции отдельно;
- есть contract tests/fixtures.

## FR-4. CR Manager Remediation Orchestration

Статус: `planned`

Roadmap phase: Фаза 4. CR Manager remediation orchestration.

Цель:

```text
Расширить CR Manager от создания Jira/CR до управляемого исполнения remediation через tools, connectors, self-check и policy.
```

### F-007. CR Manager Tools, Connectors and Self-check

Статус: `planned`

Roadmap phase: Фаза 4. CR Manager remediation orchestration.

Цель:

```text
Добавить минимальный tool execution контур CR Manager: получить remediation, выбрать разрешённый connector, выполнить действие, сделать WARP self-check и принять retry/escalation decision по policy.
```

Acceptance criteria:

- есть typed tools:
  - `get_warp_remediation`;
  - `run_connector`;
  - `run_warp_self_check`;
  - `complete_jira_issue`;
  - `notify_coordinator`;
  - `escalate_to_human`;
- tools работают через ports/adapters, а не через прямые внешние вызовы;
- unsafe connector требует policy или human approval;
- self-check не переводит preorder в `READY`;
- CR Manager пишет trace events tool execution;
- tests покрывают happy path, self-check failed и escalation.

### F-008. CR Manager Reasoning Layer

Статус: `planned`

Roadmap phase: Фаза 4. CR Manager remediation orchestration / Фаза 9. ИИ-слой агентов.

Цель:

```text
Добавить LLM reasoning внутрь CR Manager только после появления Jira/WARP/tools, чтобы LLM планировал remediation и выбирал разрешённые tools, но не управлял критичными статусами напрямую.
```

Acceptance criteria:

- создан `src/agents/cr_manager/reasoning/`;
- есть `ContextBuilder`;
- есть `ReasoningService`;
- reasoning использует общий `LlmPort`;
- reasoning возвращает structured result, а не свободный текст;
- есть `PolicyValidator`;
- LLM может предложить remediation plan и tool choices;
- backend выполняет tools и меняет статусы;
- LLM не может ставить preorder `READY`;
- LLM не может вызывать Jira/WARP/DB/API напрямую;
- tests проверяют policy-denied scenarios.

## FR-5. Requirements Agent

Статус: `planned`

Roadmap phase: Фаза 5. Requirements Agent.

Цель:

```text
Реализовать агента, который проверяет качество пользовательского входа до технической проверки WARP: КЭ, выбранные атрибуты, обязательные поля и согласование с СДО.
```

### F-009. Requirements Agent Skeleton and Mock Catalogs

Статус: `planned`

Roadmap phase: Фаза 5. Requirements Agent.

Цель:

```text
Создать модуль Requirements Agent с mock adapters для СДО, каталога источников и каталога атрибутов.
```

Acceptance criteria:

- создан `src/agents/requirements/`;
- есть `POST /requirements/check`;
- есть result model:
  - `APPROVED`;
  - `NEEDS_CLARIFICATION`;
  - `REJECTED`;
  - `HUMAN_REVIEW_REQUIRED`;
- mock adapters можно заменить real API;
- Coordinator сможет поручать проверку через `RequirementsPort`;
- неполный предзаказ не идёт в WARP.

## FR-6. Trace and Observability Hardening

Статус: `planned`

Roadmap phase: Фаза 6. Trace Collector.

Цель:

```text
Вынести trace из in-memory adapter в устойчивое хранилище или отдельный Trace Collector и подготовить основу для объяснений/аудита.
```

### F-010. Trace Storage and Agent Timeline

Статус: `planned`

Roadmap phase: Фаза 6. Trace Collector.

Цель:

```text
Сделать trace устойчивым и пригодным для восстановления хронологии работы всех агентов по correlation_id.
```

Acceptance criteria:

- trace events сохраняются не только in-memory;
- есть единая schema trace event;
- можно получить timeline по `correlation_id`;
- каждый агент пишет свои события напрямую;
- trace содержит task ids, agent_run_id и внешние issue/check ids;
- tests покрывают восстановление timeline.

## FR-9. Agent Reasoning Experience

Статус: `planned`

Roadmap phase: Фаза 9. ИИ-слой агентов.

Цель:

```text
Добавить LLM reasoning там, где он даёт ценность пользователю и команде, не ломая deterministic workflow и ownership критичных решений.
```

### F-011. Coordinator Explanation Reasoning

Статус: `planned`

Roadmap phase: Фаза 9. ИИ-слой агентов.

Цель:

```text
Добавить LLM reasoning в Coordinator только для объяснений, summary trace, подготовки escalation text и классификации нестандартных ошибок.
```

Acceptance criteria:

- создан `src/agents/coordinator/reasoning/`;
- Coordinator reasoning использует общий `LlmPort`;
- LLM объясняет статус preorder простым языком;
- LLM делает summary trace;
- LLM готовит escalation summary;
- LLM не меняет статус preorder;
- LLM не вызывает WARP/CR/Jira/EP напрямую;
- status transitions остаются deterministic;
- tests проверяют, что reasoning result не может обойти state machine.
