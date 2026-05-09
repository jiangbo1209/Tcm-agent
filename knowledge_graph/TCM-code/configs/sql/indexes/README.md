# Search Index Reserve

This folder is reserved for database index scripts used by search APIs.

## Suggested rollout

1. Backup database before index migration.
2. Run [001_fulltext_search_indexes.sql](./001_fulltext_search_indexes.sql) during low traffic window.
3. Verify index readiness from API:
   - GET /api/graph/search/index-status
4. Keep backend env `SEARCH_BACKEND_MODE=auto` for safe fallback.

## Naming convention

- Use incremental prefixes: `001_`, `002_`, `003_`...
- Keep one migration objective per file.
- Include rollback script when needed.

## Future capacity notes (100k+ papers)

- Prioritize FULLTEXT over pure LIKE.
- Add periodic index health checks in ops monitoring.
- Consider partitioning or dedicated search engine when data reaches million-level scale.
