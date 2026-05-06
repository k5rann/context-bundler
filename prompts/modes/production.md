---

## PRODUCTION-GRADE MODE (executor must follow)

Code that runs in production with real users. Not a demo, not a prototype.

Rules:
1. Error handling on every external call (network, file I/O, parsing, DB). Specific exceptions, never bare except.
2. Structured logging at decision points. No print statements for control flow.
3. Input validation at trust boundaries. Assume inputs are hostile.
4. Configuration via env vars or config files. No hardcoded URLs, ports, secrets.
5. Address at least 3 real edge cases inline (empty input, network failure, partial result).
6. Include observability hooks: metrics, traces, or correlation IDs where appropriate.
7. Document failure modes in code comments where the failure happens, not in a README.
