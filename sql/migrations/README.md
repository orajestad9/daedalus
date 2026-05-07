# Database Migrations

Daedalus database migrations are committed as plain SQL so the persistence schema is reviewable before the local migration runner applies it.

Do not put secrets in migrations. Passwords, tokens, private hosts, connection strings, or local machine details belong only in ignored local environment files such as `.env`.

Migrations are applied locally with `daedalus migrate-db` or `make migrate-db`.
The current baseline includes workflow run, workflow artifact, and workflow step
tables.
