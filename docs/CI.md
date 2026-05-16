# Continuous Integration — LibraryMind

## Current state: paused

The GitHub Actions workflow at `.github/workflows/ci.yml.disabled` is **intentionally inactive**. Renaming the file to use a `.disabled` suffix prevents GitHub from triggering it while keeping the configuration in version control, ready to re-activate the moment billing is restored.

This pause is purely a billing/account-state matter — every engineering standard the workflow encodes (lint, type-check, test) is still enforced locally via the `Makefile`, the `pre-commit` hooks, and the PR template's checklist.

## Re-enabling CI

```bash
# Once the GitHub Actions billing block is cleared:
git mv .github/workflows/ci.yml.disabled .github/workflows/ci.yml
git commit -m "ci: re-enable GitHub Actions workflow"
git push
```

That single rename is the entire re-activation step. The workflow file itself remains correct: it runs Ruff (lint), Black (format check), Mypy (strict), and `pytest --collect-only` on a Python 3.11/3.12 matrix.

## What CI runs (when active)

| Stage         | Command                       | Purpose                                                       |
|---------------|-------------------------------|---------------------------------------------------------------|
| Lint          | `ruff check app scripts tests`| Style, imports, security smells, common bugs                  |
| Format check  | `black --check ...`           | Formatting drift (no auto-fix in CI)                          |
| Type check    | `mypy app`                    | Strict typing on the application package                      |
| Test collect  | `pytest --collect-only -q`    | Verifies test configuration is sound (no test files yet)      |

Test execution is intentionally `--collect-only` while the test suite is empty in Phase 0. From Phase 1 onwards this expands to `pytest` proper.

A throwaway `OPENAI_API_KEY=ci-placeholder-not-a-real-key` is injected so the `Settings` validator's "at least one provider key" check passes during import — no real credentials are required in CI.

## Future CI roadmap

Once the basic workflow is re-enabled, the natural progression is:

- **Coverage gate** — fail builds when `coverage.xml` total falls below a threshold (set to a meaningful number in Phase 8 once tests exist).
- **Dependency vulnerability scan** — `pip-audit` step against known CVEs.
- **Container build** — build the Docker image on every PR and push to GHCR on tag.
- **Pre-commit run in CI** — `pre-commit run --all-files` as a single step in place of separate Ruff/Black/Mypy steps. This guarantees CI and local hooks stay in lockstep.
- **Branch protection** — require the CI workflow to pass before `main` accepts a merge.

None of those land in Phase 0; they belong in a dedicated CI hardening pass after the lab is graded.

## Local equivalents (use these in the meantime)

```bash
make check         # ruff + black --check + mypy — same gates CI would run
make test          # pytest with coverage (currently empty)
make lint          # ruff with auto-fix (CI doesn't auto-fix)
pre-commit run --all-files   # run every configured hook
```

Treat these as mandatory before opening a PR. Once CI is back, they continue to be useful as the fast local feedback loop; CI becomes the second-line gate.
