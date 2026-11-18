---
name: datagrip-readonly
description: Read-only rules for any SQL run through the DataGrip MCP server (execute_sql_query, preview_table_data, etc.). Use whenever querying a database via the datagrip MCP — investigating students, progress, payments, groups. Forbids INSERT, UPDATE, DELETE and every other data- or schema-changing statement.
---

# DataGrip: только чтение

Это личное правило для этого компьютера. Через MCP-сервер `datagrip` работаем с базой **только на чтение**. Базы содержат данные учеников и платежей.

## Разрешено

- `SELECT ...`
- `WITH ... SELECT ...` — только если ни один CTE не содержит `INSERT`, `UPDATE`, `DELETE`
- `EXPLAIN ...` — без `ANALYZE`, потому что `EXPLAIN ANALYZE` реально выполняет запрос
- `SHOW ...`
- инструменты просмотра схемы: `list_database_connections`, `list_database_schemas`, `get_database_object_description`, `list_schema_objects`, `preview_table_data`, `test_database_connection`

## Запрещено всегда, даже если пользователь просит прямо

Не отправлять через `execute_sql_query`:

- `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `INSERT ... ON CONFLICT`
- `TRUNCATE`, `DROP`, `ALTER`, `CREATE`, `RENAME`, `COMMENT ON`
- `GRANT`, `REVOKE`, `VACUUM`, `REINDEX`, `CLUSTER`, `REFRESH MATERIALIZED VIEW`
- `COPY`, `CALL`, `DO`, `EXECUTE`, `SELECT ... INTO`
- `SELECT ... FOR UPDATE` и `FOR SHARE` — они берут блокировки
- функции с побочными эффектами: `nextval`, `setval`, `pg_terminate_backend`, `pg_cancel_backend`, `pg_advisory_lock`, `lo_*`, `set_config`
- `BEGIN`, `COMMIT`, `ROLLBACK`, `SET`, если они меняют состояние сессии или транзакции
- несколько операторов в одном вызове, например `SELECT 1; DELETE ...`

Не вызывать `create_database_connection`, `edit_database_connection` и `execute_run_configuration`, даже если они доступны.

## Перед каждым запросом

1. Прочитать весь текст запроса целиком, а не только начало. Искать запрещённые слова в CTE и подзапросах.
2. Один запрос — один оператор.
3. `SELECT` без ограничений разрешён: любые колонки, любые таблицы, `LIMIT` и фильтры не обязательны. Это решение пользователя.
4. Если подключение — боевой мастер (`SELECT pg_is_in_recovery()` вернул `false`): Читать из него разрешено, спрашивать каждый раз не нужно. Запрещена только запись.
5. Ограничивается одно: запись и изменение данных или схемы (раздел «Запрещено»).

## Если нужна запись

Если для задачи нужно изменить данные (сбросить прогресс, восстановить балл, исправить группу):

1. Не выполнять запрос.
2. Написать пользователю готовый SQL в блоке кода и объяснить, что он сделает и сколько строк затронет. Для этого сначала выполнить аналогичный `SELECT count(*)`.
3. Пользователь выполнит его сам, под своей ответственностью.

## Ограничение этого скила

Скил — это инструкция для меня, а не технический запрет. Он не остановит запрос, если я его ошибочно отправлю. Настоящая защита — отдельная учётная запись базы с правами только `SELECT` и подключение к реплике.
