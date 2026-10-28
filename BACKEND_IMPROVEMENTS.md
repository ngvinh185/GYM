# Backend review and implementation notes

This report records changes made in `backend_new`. The original `backend` directory was left untouched. The new directory was copied from the current working tree, including its data and evaluation files, while excluding `.env`, virtual environments, bytecode and caches.

## Changes made

- Renamed the TXT retrieval code from `pdf_*` to `knowledge` / `document_*`, removed import-time embedding initialization, cached document parsing and embeddings, and retrieve three matching chunks.
- Added PostgreSQL row-level security for `users` and `class_enrollments`, plus public read/admin write policies for catalog tables. USER SQL runs in a read-only transaction; the runtime rejects superuser/BYPASSRLS/table-owner chat accounts and refuses startup use until the migration is applied.
- Split database roles: `gym_chat_app` is used by the SQL agent and cannot read `password_hash`; `gym_api_auth` is used only for API login and role lookups.
- Limited SQL to one parsed statement, blocked sensitive columns and dangerous functions, enforced statement timeouts and `DB_MAX_ROWS`, and disallowed DDL. The SQL AST walk also rejects data-modifying CTEs inside read-shaped statements. ADMIN writes are previewed in a rolled-back transaction and committed only on an exact confirmation in the same user/session. DDL is intentionally unsupported.
- Removed chat trace/message/token logging, capped the in-memory graph cache at 64 sessions, cleaned duplicate imports and unused wrappers, and aligned the contact number with the TXT source.
- Added setup/migration guidance, `.env.example`, and ignore rules in `backend_new`.

## Required setup and limits

- Apply `backend_new/database/migrations/001_chat_row_security.sql` to the existing GymHeart schema as a database administrator, then set separate passwords for the two database roles.
- Configure `AUTH_DB_PASSWORD`, `DB_PASSWORD`, `JWT_SECRET`, and `OPENAI_API_KEY` in a local `.env`; no `.env` from the original backend was copied.
- Keep the `session_id` returned by `/chat` for follow-up confirmation. Confirmation must be an exact supported phrase; another message cancels the pending preview. The cache keeps up to 64 idle sessions; active concurrent sessions may temporarily exceed that and an evicted session loses its unconfirmed preview.
- Conversation checkpoints and pending previews are in process memory; use one API worker until a shared store is added. Restarting clears them.
- ADMIN SQL writes support INSERT/UPDATE/DELETE only. DDL is blocked, and inserting a `users` record is not granted because authentication credentials are managed separately.

## Verification status

No tests were added or run. The migration was not applied to a live database. All 25 Python files passed AST syntax parsing, and the copied tree was checked for excluded environments, caches, and `.env` files. An independent review confirmed that nested data-modifying CTEs are rejected before execution. Actual SQL behavior still depends on applying the migration and configuring the two roles.
