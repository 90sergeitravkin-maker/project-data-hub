# Приложение для работы с базой

## Проект создан для работы в среде  предназначен как проект по управлению файлами и базой данных

- Почтовая рассылка
- Просмотр файлов списокм и по содержимому
- Опись файлов

## Стек

1. FastAPI
2. PostgreSQL

## Общая логика ПО

чтобы отображалось корректно установи ***mermaid*** в IDE

```mermaid
graph LR
    User((👤 Пользователь)) --> Browser[браузер]
Browser --> Nginx[Nginx]
Nginx --> Uvicorn[Uvicorn]
Uvicorn --> FastAPI[FastAPI]
FastAPI --> App[Бизнес‑логика]
App --> DB[(💾 База данных)]
```

## Способы запуска

1. описание
   ```bash
    fastapi dev app_main.py
    ```
2. описание
    ```bash
   unicorn main:app --reload
   ```
3. описание
   ```bash
   python app_main.py
   ```
4. Собрать код для ИИ

```bash
  powershell -NoProfile -ExecutionPolicy Bypass -File .\collect.ps1
```

# Установить зависимости

```bash
    pip install -r requirements.txt
```
## Alembic
### Активируйте виртуальное окружение
```
.venv\Scripts\activate
```
### Создайте первую миграцию (autogenerate)
```
alembic revision --autogenerate -m "Initial migration with all schemas"
```
### Примените миграции
```
alembic upgrade head
```
### Откатите миграции (если нужно)
```
alembic downgrade -1
```
### Посмотрите историю миграций
```
alembic history --verbose
```
### Проверьте текущую версию
```
alembic current
```

### Автоматическая генерация миграции на основе моделей
```
alembic revision --autogenerate -m "initial migration - create all tables"
```
### Затем примените миграцию:
```
alembic upgrade head
```
