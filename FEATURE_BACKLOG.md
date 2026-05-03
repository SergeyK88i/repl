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

Статус: `next`

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

### F-004. CR Manager Creates Jira/CR From WARP Failed Criteria

Статус: `planned`

Roadmap phase: Фаза 2. CR Manager Agent и Jira.

Цель:

```text
Научить CR Manager создавать Jira/CR с источником, load_plan, warp_check_id, критериями, параметрами и remediation-инструкциями.
```

Acceptance criteria:

- CR Manager получает remediation context от Coordinator;
- CR Manager запрашивает remediation у WARP adapter;
- CR Manager создаёт Jira/CR с читаемым описанием;
- trace содержит `jira_issue_created`;
- tests покрывают happy path и idempotency.

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
