# PostgreSQL Best Practices

## Schema Design

- Use `SERIAL` or `BIGSERIAL` (or `GENERATED ALWAYS AS IDENTITY`) for primary keys
- Prefer `TEXT` over `VARCHAR(n)` — PostgreSQL stores them the same way
- Use `JSONB` (not `JSON`) for semi-structured data — supports indexing
- Use `TIMESTAMPTZ` (with timezone) not `TIMESTAMP` — avoid timezone bugs
- Normalize to at least 3NF — denormalize only for proven performance needs
- Add `NOT NULL` constraints wherever the column should always have a value
- Use `CHECK` constraints for domain validation at DB level

## Indexes

- Index every foreign key column
- Use partial indexes for filtered queries: `CREATE INDEX ON orders (user_id) WHERE status = 'pending'`
- Use composite indexes in column order matching the WHERE clause
- `GIN` index for JSONB columns that will be queried
- `pg_trgm` extension + GIN index for LIKE/ILIKE full-text search
- Review `EXPLAIN ANALYZE` for slow queries — do not add indexes blindly

## Migrations

- Every schema change = a new migration file (never edit existing migrations)
- Always include `UP` and `DOWN` (rollback) scripts
- Test rollback in staging before production deploy
- Use transactions in migrations: `BEGIN; ... COMMIT;`
- Name migrations descriptively: `20240501_add_status_to_orders.sql`

## Connections & Performance

- Use connection pooling (PgBouncer) in production — never raw connections per request
- Set `statement_timeout` to prevent runaway queries
- Use `LIMIT` on all list queries — never `SELECT *` without pagination
- `VACUUM ANALYZE` periodically — autovacuum handles routine, manual for large deletes

## Security

- Principle of least privilege: app DB user has only SELECT/INSERT/UPDATE/DELETE
- Never grant SUPERUSER to the application user
- Use `pg_audit` extension for sensitive operations
- Encrypt sensitive columns at application level (not only DB-level)
- Backup strategy: daily full + WAL archiving for point-in-time recovery

## Anti-Patterns

- `SELECT *` in application queries — always name columns
- `VARCHAR(255)` for all strings — use `TEXT` or appropriate domain type
- Storing money as `FLOAT` — use `NUMERIC(10,2)` or `INTEGER` (cents)
- Missing foreign key constraints — always define relationships explicitly
- Running migrations without a transaction wrapper
- Using `JSON` instead of `JSONB` for queryable fields
