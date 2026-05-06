---

## TEST-FIRST MODE (executor must follow)

TDD discipline: failing test before any implementation.

Rules:
1. For every feature or function, write a failing test FIRST. Show the failure (red).
2. Implement only enough to make the test pass. Nothing more (green).
3. Refactor only after green. Show the test still passes.
4. Test file structure mirrors source structure.
5. Test names describe behavior, not implementation: "rejects empty input" not "test_validate_None".
6. If you can't test a code path, redesign it. Untestable code is a bug.
