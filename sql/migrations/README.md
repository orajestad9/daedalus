# Database Migrations

Daedalus database migrations are committed as plain SQL so the persistence schema is reviewable before any runner applies it.

Do not put secrets in migrations. Passwords, tokens, private hosts, connection strings, or local machine details belong only in ignored local environment files such as `.env`.

Migrations are not applied automatically yet. A migration runner will be added in a later Phase 1 step after the schema baseline is established.
