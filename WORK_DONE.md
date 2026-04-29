# Что уже сделано

## Краткий итог

Мы превратили исходное описание агентной архитектуры в первый рабочий production-shaped POC.

Сейчас система умеет демонстрировать ключевую идею:

```text
Пользователь создаёт предзаказ
→ Координатор проверяет источник через WARP
→ если источник не готов, создаётся CR-задача
→ после исправлений выполняется final-check
→ при READY стартует следующая фаза для ЕР-Конфигуратора
```

Это ещё не production-система, но уже не просто текстовая схема. Есть backend, UI, сценарии, тесты, правила архитектуры и документация.

## Архитектурные договорённости

Создан документ [PROJECT_RULES.md](PROJECT_RULES.md), где зафиксированы ключевые правила реализации:

- Python как основной язык;
- FastAPI как API-фреймворк;
- Pydantic-контракты;
- agent-oriented структура;
- ports-and-adapters архитектура;
- заглушки только за интерфейсами;
- возможность заменить mock-адаптеры на реальные API;
- разделение ответственности между агентами;
- `correlation_id` для сквозной трассировки;
- запрет хранить критическое состояние только в prompt memory;
- READY как рубеж между подготовкой источника и созданием реплики.

## Реализованный backend

Сейчас реализован первый агентный контур вокруг Координатора.

Реализовано:

- FastAPI-приложение;
- `CoordinatorService`;
- state machine статусов предзаказа;
- in-memory хранилище предзаказов;
- in-memory хранилище CR-задач;
- in-memory trace;
- mock WARP adapter;
- mock CR Manager adapter;
- mock Replica Init adapter;
- проверка принадлежности CR-задачи предзаказу;
- идемпотентная обработка повторного callback-а;
- retry logic до `FAILED`;
- trace events от Координатора, WARP и CR Manager.

Основные endpoints:

```text
POST /order
GET  /order/{order_id}
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
GET  /console
```

## Реализованные сценарии

Создан документ [SCENARIOS.md](SCENARIOS.md), где подробно описаны три демонстрационных сценария.

### Сценарий 1. Источник сразу READY

```text
Пользователь создаёт предзаказ для SRC-READY
→ WARP возвращает READY
→ CR Manager не нужен
→ Координатор передаёт задачу следующей фазе
```

### Сценарий 2. Источник требует исправлений

```text
Пользователь создаёт предзаказ для SRC-123
→ WARP возвращает NOT_READY
→ Координатор создаёт CR-задачу
→ предзаказ переходит в WAITING_CR
```

### Сценарий 3. CR Manager завершил работу

```text
CR Manager сообщает task-completed
→ Координатор проверяет принадлежность задачи
→ Координатор делает final-check через WARP
→ WARP возвращает READY
→ стартует следующая фаза
```

## Реализованный UI

Создан chat-first UI: [src/app/static/agent_console.html](src/app/static/agent_console.html).

UI показывает систему не как набор кнопок, а как комнату агентов:

- Пользователь;
- Координатор;
- WARP;
- CR Manager;
- ЕР-Конфигуратор.

Пользователь пишет запрос в чат:

```text
Хочу загрузить реплику для SRC-123
```

После этого агенты отвечают с паузами:

```text
Координатор принимает предзаказ
WARP проверяет источник
CR Manager выполняет исправления
WARP делает final-check
ЕР-Конфигуратор принимает задачу после READY
```

Также UI содержит:

- текущий статус предзаказа;
- `order_id`;
- `source_id`;
- `correlation_id`;
- CR-задачи;
- путь процесса;
- кнопку `Схема агентов`;
- модальное окно со схемой взаимодействия агентов до и после READY.

## Документация и визуализация

Подготовлены:

- [agents.md](agents.md) — исходное описание архитектуры;
- [PROJECT_RULES.md](PROJECT_RULES.md) — правила реализации;
- [SCENARIOS.md](SCENARIOS.md) — сценарии работы;
- [README.md](README.md) — запуск и основные endpoints;
- [architecture.html](architecture.html) — презентационная архитектурная страница;
- [src/app/static/agent_console.html](src/app/static/agent_console.html) — интерактивная UI-консоль.

## Текущее техническое состояние

Сейчас это POC с заменяемыми заглушками.

Используются:

- `MockWarpAdapter`;
- `MockCrManagerAdapter`;
- `MockReplicaInitAdapter`;
- `InMemoryOrderRepository`;
- `InMemoryTaskRepository`;
- `InMemoryTraceAdapter`.

При этом бизнес-логика Координатора уже работает через порты:

```text
WarpPort
CrManagerPort
ReplicaInitPort
OrderRepositoryPort
TaskRepositoryPort
TracePort
```

Это означает, что заглушки можно заменить на реальные API-адаптеры без переписывания workflow Координатора.

## Проверки

Добавлены unit tests для Координатора.

Команда:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Текущее состояние:

```text
5 tests OK
```

## Главный результат

Мы получили первый согласуемый контур:

```text
Идея → архитектурные правила → backend POC → UI-демонстрация → сценарии → база для roadmap
```

Теперь можно переходить к поэтапному внедрению настоящих агентов и реальных интеграций.

