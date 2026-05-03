# Требования к интеграции с WARP

Этот документ фиксирует текущую версию того, как наша агентная система должна интегрироваться с WARP.

WARP разрабатывается другой командой и в production рассматривается как внешний агент/сервис.
Мы не реализуем WARP внутри нашего проекта, а подключаемся к нему через `WarpPort` и `HttpWarpAdapter`.

## Роль WARP

WARP — единственный источник истины по готовности источника.

WARP отвечает на вопрос:

```text
"Готов ли источник к работе в рамках выбранного плана загрузки?"
```

WARP не должен:

- менять статус предзаказа;
- создавать CR/Jira-задачи;
- выполнять remediation;
- запускать ЕР-фазу;
- принимать бизнес-решение о превращении предзаказа в заказ.

## Общая логика проверки

Минимальный запрос к WARP содержит `source_id`.

Если `load_plan` не передан, WARP проверяет источник по плану по умолчанию.

Текущая договорённость:

```text
load_plan не передан -> WARP проверяет по PLAN_A
load_plan передан    -> WARP проверяет источник в рамках указанного плана
```

Пример без явного плана:

```json
{
  "source_id": "CM12345",
  "correlation_id": "CORR-001",
  "context": "initial_check"
}
```

В этом случае WARP сам определяет:

```text
effective load_plan = PLAN_A
```

Пример с явным планом:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_B",
  "correlation_id": "CORR-001",
  "context": "initial_check"
}
```

В этом случае WARP проверяет источник в рамках `PLAN_B`.

## Контексты проверки

Ожидаемые значения `context`:

```text
initial_check - первичная проверка Координатором
self_check    - самопроверка CR Manager после remediation
final_check   - официальная финальная проверка Координатором
```

`self_check` не переводит предзаказ в READY.

`READY` может выставить только Координатор после `final_check`, если WARP подтвердил 100% готовность.

## Взаимодействия с WARP

### 1. Coordinator initial readiness

Кто вызывает: Coordinator.

Endpoint:

```text
POST /warp/readiness
```

Когда вызывается: первичная техническая проверка после подтверждения требований.

Что передаём:

- `source_id`;
- опционально `load_plan`;
- `correlation_id`;
- `context=initial_check`.

Что хотим получить:

- `status`;
- `score`;
- фактический `load_plan`;
- невыполненные критерии и параметры;
- `warp_check_id`;
- `checked_at`.

Кто использует результат: Coordinator решает, идти дальше, передать CR Manager или эскалировать.

### 2. CR Manager remediation

Кто вызывает: CR Manager.

Endpoint:

```text
POST /warp/get-remediation
```

Когда вызывается: после получения remediation-поручения от Coordinator.

Что передаём:

- `source_id`;
- `load_plan`;
- `correlation_id`;
- `warp_check_id`;
- список `criteria_id + param_id`.

Что хотим получить:

- машинно-интерпретируемые инструкции по исправлению критериев и параметров;
- рекомендуемого владельца или connector, если WARP это поддерживает;
- признак, можно ли автоматизировать исправление.

Кто использует результат: CR Manager создаёт Jira/CR и организует remediation.

### 3. CR Manager self-check

Кто вызывает: CR Manager.

Endpoint:

```text
POST /warp/readiness
```

Когда вызывается: после выполнения remediation.

Что передаём:

- `source_id`;
- `load_plan`;
- `correlation_id`;
- `context=self_check`;
- при поддержке WARP список проверяемых criteria/params.

Что хотим получить:

- готовность после исправлений: `READY` или `NOT_READY`;
- оставшиеся failed criteria/params;
- `score`;
- `warp_check_id`;
- `checked_at`.

Кто использует результат: CR Manager решает, продолжать remediation, retry, эскалацию или callback Coordinator.

### 4. Coordinator official final-check

Кто вызывает: Coordinator.

Endpoint:

```text
POST /warp/readiness
```

Когда вызывается: после callback от CR Manager.

Что передаём:

- `source_id`;
- `load_plan`;
- `correlation_id`;
- `context=final_check`.

Что хотим получить:

- официальный `READY` или `NOT_READY`;
- `score`;
- failed criteria/params;
- `audit_hash`;
- `warp_check_id`;
- `checked_at`.

Кто использует результат: Coordinator меняет статус предзаказа на `READY` или снова поручает CR Manager.

Принцип:

```text
Coordinator спрашивает WARP о готовности.
CR Manager спрашивает WARP о том, как исправлять.
Coordinator делает финальное решение только после official final-check.
```

## Сводный список endpoint-ов и контрактов

Ниже зафиксирована целевая логическая поверхность WARP для нашей системы.

Физически у WARP может быть один readiness endpoint и один remediation endpoint.
Если реальные названия endpoint-ов отличаются, это будет скрыто внутри `HttpWarpAdapter`.

### 1. Coordinator initial readiness check

Кто вызывает:

```text
Coordinator
```

Endpoint:

```text
POST /warp/readiness
```

Когда:

```text
После того как Requirements Agent подтвердил, что предзаказ можно брать в работу.
```

Request:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "context": "initial_check"
}
```

`load_plan` опционален. Если он не передан, WARP проверяет источник по плану по умолчанию, сейчас это `PLAN_A`.

Response:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "status": "NOT_READY",
  "score": {
    "current": 72,
    "required": 100
  },
  "failed_criteria": [
    {
      "criteria_id": "C1",
      "criteria_name": "Готовность описания источника",
      "failed_params": [
        {
          "param_id": "P1",
          "param_name": "Не заполнено описание",
          "severity": "blocking",
          "message": "Описание источника отсутствует"
        },
        {
          "param_id": "P5",
          "param_name": "Не указан владелец источника",
          "severity": "blocking",
          "message": "Владелец источника не заполнен"
        }
      ]
    }
  ],
  "warp_check_id": "WARP-CHECK-123",
  "audit_hash": null,
  "checked_at": "2026-05-03T12:00:00Z"
}
```

Coordinator использует ответ так:

```text
READY     -> переводит предзаказ дальше по маршруту
NOT_READY -> создаёт remediation-поручение для CR Manager
```

Coordinator не использует remediation-инструкции.

### 2. CR Manager remediation request

Кто вызывает:

```text
CR Manager
```

Endpoint:

```text
POST /warp/get-remediation
```

Когда:

```text
После того как Coordinator передал CR Manager remediation-поручение.
```

Request:

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

Response:

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
    },
    {
      "criteria_id": "C1",
      "param_id": "P5",
      "title": "Указать владельца источника",
      "steps": [
        "Открыть карточку источника",
        "Заполнить владельца источника",
        "Сохранить изменения"
      ],
      "recommended_owner": "source_team",
      "recommended_connector": "source_catalog",
      "automation_possible": false,
      "required_inputs": ["source_owner"],
      "expected_result": "Владелец источника указан"
    }
  ]
}
```

CR Manager использует ответ так:

```text
создаёт Jira/CR
прикладывает критерии, параметры и инструкции
оркестрирует remediation через tools/connectors/subagents
```

### 3. CR Manager self-check

Кто вызывает:

```text
CR Manager
```

Endpoint:

```text
POST /warp/readiness
```

Когда:

```text
После выполнения remediation, перед callback в Coordinator.
```

Request:

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

`criteria_params` опционален и зависит от того, поддерживает ли WARP точечную перепроверку.
Если WARP не поддерживает точечную перепроверку, адаптер может отправлять только `source_id`, `load_plan`, `correlation_id`.

Response:

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
  "warp_check_id": "WARP-CHECK-124",
  "audit_hash": null,
  "checked_at": "2026-05-03T12:10:00Z"
}
```

CR Manager использует ответ так:

```text
READY     -> отправляет callback Coordinator
NOT_READY -> продолжает remediation, retry или эскалацию
```

`self_check` не даёт права переводить предзаказ в READY.

### 4. Coordinator official final-check

Кто вызывает:

```text
Coordinator
```

Endpoint:

```text
POST /warp/readiness
```

Когда:

```text
После callback от CR Manager о том, что remediation завершён и self-check успешен.
```

Request:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "context": "final_check"
}
```

Response:

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
  "warp_check_id": "WARP-CHECK-125",
  "audit_hash": "WARP-AUDIT-abc123",
  "checked_at": "2026-05-03T12:15:00Z"
}
```

Coordinator использует ответ так:

```text
READY     -> переводит предзаказ в READY
NOT_READY -> снова поручает CR Manager или эскалирует
```

Только `final_check` может стать основанием для смены статуса предзаказа на `READY`.

## Разделение readiness и remediation

В нашей внутренней архитектуре нужно разделять два типа информации от WARP:

```text
readiness  - готов источник или нет, какие критерии/параметры не выполнены
remediation - что нужно сделать, чтобы исправить критерии/параметры
```

Coordinator запрашивает только readiness.

Coordinator не должен получать и обрабатывать подробные инструкции по исправлению, потому что это не его зона ответственности.

CR Manager запрашивает remediation-инструкции.

CR Manager должен получить:

- список невыполненных критериев;
- список невыполненных параметров внутри критериев;
- инструкции по исправлению;
- рекомендуемого владельца или connector, если WARP это поддерживает;
- признак, можно ли автоматизировать исправление.

Целевая логическая модель:

```text
Coordinator -> WARP readiness
WARP -> Coordinator: status, score, load_plan, failed criteria/params, warp_check_id

Coordinator -> CR Manager: remediation task context

CR Manager -> WARP remediation
WARP -> CR Manager: instructions for criteria/params
```

Если реальный WARP API отдаёт readiness и remediation одним response, `HttpWarpAdapter` должен разделить эту информацию на уровне нашей системы:

- Coordinator-facing contract должен вернуть только readiness-часть;
- CR Manager-facing contract может использовать remediation-часть или запросить её отдельным вызовом;
- Coordinator application logic не должна зависеть от формата remediation-инструкций.

Так мы сохраняем чистые границы ответственности даже если внешний WARP API устроен иначе.

## Readiness request

Предварительная целевая схема:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "correlation_id": "CORR-001",
  "context": "initial_check"
}
```

Поля:

- `source_id` — обязательный идентификатор источника;
- `load_plan` — опциональный план загрузки;
- `correlation_id` — сквозной идентификатор trace;
- `context` — тип проверки.

Атрибутный состав пользователя в WARP readiness request не передаём.

Атрибуты проверяются не WARP, а Requirements Agent через СДО/каталоги.

## Readiness response

WARP должен вернуть не только общий статус, но и фактический план, по которому была выполнена проверка.

Предварительная целевая схема:

```json
{
  "source_id": "CM12345",
  "load_plan": "PLAN_A",
  "status": "NOT_READY",
  "score": {
    "current": 72,
    "required": 100
  },
  "failed_criteria": [
    {
      "criteria_id": "C1",
      "criteria_name": "Готовность описания источника",
      "failed_params": [
        {
          "param_id": "P1",
          "param_name": "Не заполнено описание",
          "severity": "blocking",
          "message": "Описание источника отсутствует"
        },
        {
          "param_id": "P5",
          "param_name": "Не указан владелец источника",
          "severity": "blocking",
          "message": "Владелец источника не заполнен"
        }
      ]
    }
  ],
  "warp_check_id": "WARP-CHECK-123",
  "audit_hash": null,
  "checked_at": "2026-05-03T12:00:00Z"
}
```

Минимально нужные поля:

- `source_id`;
- `load_plan` — фактический план проверки;
- `status`;
- `score.current`;
- `score.required`;
- `failed_criteria`;
- `failed_criteria[].criteria_id`;
- `failed_criteria[].failed_params[]`;
- `warp_check_id` или другой идентификатор проверки;
- `checked_at`;
- `audit_hash`, если WARP отдаёт audit marker.

## Failed criteria и параметры

WARP может вернуть невыполненный критерий с несколькими невыполненными параметрами.

Пример:

```text
Не выполнен критерий C1.
Внутри C1 не выполнены параметры P1 и P5.
```

CR Manager должен получать не только `criteria_id`, но и список конкретных `param_id`, чтобы понимать, какую remediation-работу организовывать.

## Кто запрашивает remediation-инструкции

Текущая договорённость:

```text
Coordinator не запрашивает remediation-инструкции.
CR Manager сам запрашивает remediation-инструкции у WARP.
```

Почему так:

- Coordinator остаётся владельцем маршрута и статуса, а не исполнителем исправлений;
- CR Manager владеет Jira/CR и должен сам решать, как оформить remediation;
- CR Manager может запрашивать инструкции точечно по критериям и параметрам;
- изменение формата инструкций WARP затрагивает CR Manager, а не Coordinator;
- границы ответственности остаются чистыми.

## Что Coordinator передаёт CR Manager

Coordinator передаёт не инструкции, а контекст remediation-задачи.

Пример:

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
  "attempt": 1
}
```

## Remediation request

CR Manager запрашивает у WARP инструкции по конкретным критериям и параметрам.

Предварительная целевая схема:

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

## Remediation response

Предварительная целевая схема:

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

Нужные поля:

- `criteria_id`;
- `param_id`;
- `title`;
- `steps`;
- `recommended_owner`;
- `recommended_connector`, если есть;
- `automation_possible`;
- `required_inputs`;
- `expected_result`.

## Jira/CR оформление

В MVP CR Manager создаёт одну Jira/CR-задачу на remediation-поручение.

В описании задачи фиксируются:

- источник;
- план проверки;
- `warp_check_id`;
- невыполненные критерии;
- невыполненные параметры;
- remediation-инструкции;
- ссылка на trace, если доступна.

Пример описания:

```text
Источник: CM12345
План проверки: PLAN_A
WARP check: WARP-CHECK-123

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

Subtasks можно добавить позже, если remediation по критериям нужно распределять между разными исполнителями или субагентами.

## Вопросы к WARP-команде

Перед реализацией real adapter нужно уточнить:

- как называется поле плана загрузки;
- какие значения планов поддерживаются;
- правда ли отсутствие плана означает `PLAN_A`;
- возвращает ли WARP фактический план проверки в ответе;
- какой формат `failed_criteria`;
- поддерживаются ли параметры внутри критерия;
- какие поля есть у параметра: id, name, severity, message;
- есть ли `warp_check_id`;
- есть ли `audit_hash`;
- есть ли отдельный endpoint для remediation-инструкций;
- можно ли запросить remediation по `criteria_id + param_id`;
- какие ошибки возвращает WARP;
- какие timeout/retry допустимы;
- есть ли ограничения по rate limit;
- какие headers/auth нужны;
- можно ли прокидывать `correlation_id`.

## Граница ответственности

```text
WARP диагностирует.
Coordinator маршрутизирует и меняет статус предзаказа.
CR Manager организует исправление, создаёт Jira/CR и запрашивает инструкции.
```
