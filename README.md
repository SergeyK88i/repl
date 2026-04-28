# Agentic Replica Readiness Platform

Production-shaped POC системы ИИ-агентов для подготовки источника данных к созданию реплики.

Первый реализованный контур:

- `Coordinator Agent`;
- replaceable ports/adapters;
- mock WARP;
- mock CR Manager;
- mock Replica Init;
- in-memory order repository;
- in-memory trace collector;
- FastAPI endpoints.

## Запуск

```bash
pip install -r requirements.txt
PYTHONPATH=src uvicorn app.main:app --reload
```

## Проверка

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## Основные endpoints

```text
POST /order
GET  /order/{order_id}
POST /order/{order_id}/task-completed
GET  /trace/{correlation_id}
```

## Пример создания заказа

```json
{
  "source_id": "SRC-123",
  "request": "загрузить реплику"
}
```

