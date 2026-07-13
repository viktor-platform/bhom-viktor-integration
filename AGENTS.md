# Repository guidance

## VIKTOR Lightsail testing

- This project uses SSH for remote VIKTOR testing.
- When present, read the ignored repository-local skill at `.codex/skills/bhom-lca-service-ops/SKILL.md` for this app's SOW, test boundaries, and handoff checklist.
- Before connecting to or changing the shared Lightsail test host, read and follow the `viktor-lightsail-testing` skill at `/Users/alejandroduarte/.codex/skills/viktor-lightsail-testing/SKILL.md`.
- Use the configured SSH alias `viktor-test`; do not copy credentials, private keys, tokens, or authorization headers into the repository or command output.
- Inspect the remote Git status before pulling or editing. Preserve remote changes and never reset, clean, force-push, or publish without explicit user authorization.
- Avoid parallel dependency installs and duplicate VIKTOR processes because the host has limited memory.

## Python quality checks

Run these commands from `viktor-bhom-lca-service-starter` after changing Python code. Activate the project environment first, or pass its Python executable to `ty` explicitly:

```bash
uvx ruff format .
uvx ruff check .
uvx ty check --python venv/bin/python
```

- Formatting must complete before linting and type checking.
- Fix reported issues when they are caused by the current change. Do not suppress diagnostics or reformat unrelated code merely to make checks pass.
- `ty` checks Python files recursively and uses the project environment for dependency discovery. If dependencies cannot be resolved, report the environment problem separately from genuine type errors.
