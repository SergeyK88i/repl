# Feature backlog

Этот файл связывает верхнеуровневый `ROADMAP.md` с конкретными реализуемыми фичами.

Принцип работы:

```text
ROADMAP.md показывает фазу
FEATURE_BACKLOG.md разбивает фазу на конкретные фичи
каждая фича имеет цель, границы, acceptance criteria и статус
```

Статусы:

```text
planned     - запланировано
next        - следующая фича в работе
in_progress - сейчас реализуется
done        - реализовано и проверено
blocked     - есть внешний блокер
```

## F-001. LLM Provider Foundation

Статус: `done`

Roadmap phase: инфраструктурная подготовка для LLM reasoning.

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

## F-002. CR Manager Agent Skeleton

Статус: `next`

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
- `ports/jira.py`;
- `ports/warp.py`;
- `ports/coordinator_callback.py`;
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

## F-003. Mock Jira Adapter

Статус: `planned`

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

## F-004. CR Manager Creates Jira/CR From WARP Failed Criteria

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

## F-005. Coordinator Dispatches To Real CR Manager Module

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

## F-006. Real WARP Adapter

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
