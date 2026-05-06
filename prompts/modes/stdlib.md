---

## STDLIB-ONLY MODE (executor must follow)

Use the language's standard library. No third-party packages.

Rules:
1. No `pip install`, no `npm install`, no `cargo add`. Period.
2. If a stdlib equivalent exists for what you'd reach for, use it (urllib not requests, json not orjson, sqlite3 not psycopg2 for local needs).
3. If the task genuinely requires an external package, STOP and tell the user: "This needs X — install with `pip install X` or change the task."
4. No exceptions for "it's just a tiny utility package."
5. If a stdlib-only solution is meaningfully harder, say so in a one-line comment so the user knows the cost.
