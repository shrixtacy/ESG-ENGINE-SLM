# Contributing to ESG-ENGINE-SLM

Thank you for taking the time to contribute. This document covers everything you need to know before opening an issue or pull request.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [What we're looking for](#what-were-looking-for)
- [Reporting bugs](#reporting-bugs)
- [Requesting features](#requesting-features)
- [Development setup](#development-setup)
- [Branch and commit conventions](#branch-and-commit-conventions)
- [Pull request process](#pull-request-process)
- [Code style](#code-style)
- [Testing](#testing)
- [Working with the knowledge base](#working-with-the-knowledge-base)
- [Licensing](#licensing)

---

## Code of Conduct

This project follows our [Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to uphold it. Please report unacceptable behaviour to the maintainers.

---

## What we're looking for

We especially welcome contributions in these areas:

- **Rules engine** — new BRSR field checks, emission factor updates, additional framework checks (GRI, ISSB)
- **Knowledge base ingestion** — new crawlers or parsers for regulatory sources listed in `RESOURCES.md`
- **Retrieval quality** — chunking strategies, metadata enrichment, reranking experiments
- **SDK / widget** — accessibility improvements, new integration adapters, bug fixes
- **Evaluation** — expanding the gold Q&A set, adding new RAGAS metrics, test fixtures for rules
- **Documentation** — clearer explanations, additional examples, translations
- **Bug fixes** — especially anything that causes incorrect numbers or silently wrong citations

If you are unsure whether an idea fits, open a Discussion before writing code.

---

## Reporting bugs

1. Search existing issues first — your bug may already be tracked.
2. Open a new issue using the **Bug report** template.
3. Include:
   - Steps to reproduce
   - Expected vs actual behaviour
   - Environment (OS, Python version, GPU/CPU, model name)
   - Relevant log output (redact any secrets or PII)

For security vulnerabilities, **do not open a public issue**. See [`SECURITY.md`](SECURITY.md).

---

## Requesting features

1. Check the roadmap in `BUILD_SPEC.md` — it may already be planned.
2. Open a new issue using the **Feature request** template.
3. Describe the use case before the implementation. A clear problem statement helps maintainers prioritise.

---

## Development setup

### Python backend

```bash
git clone https://github.com/shrixtacy/ESG-ENGINE-SLM.git
cd ESG-ENGINE-SLM

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install torch==2.4.0+cu121 --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements.txt
pip install pre-commit
pre-commit install
```

### TypeScript SDK

```bash
cd sdk
npm install
npm run dev
```

### Infrastructure (local)

```bash
docker compose up -d postgres qdrant redis
alembic upgrade head
```

---

## Branch and commit conventions

**Branches** follow this pattern:

```
feat/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
test/<short-description>
chore/<short-description>
```

**Commits** use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(rules): add BRSR Core KPI completeness check
fix(retrieval): correct version filter for superseded docs
docs(readme): clarify Docker GPU setup
test(rules): add golden-file tests for Scope 2 intensity
```

Squash your branch to clean commits before requesting a review.

---

## Pull request process

1. Fork the repo and create a branch from `main`.
2. Make your changes. Keep PRs focused — one logical change per PR.
3. Add or update tests for any changed behaviour.
4. Run the full test suite locally (see [Testing](#testing)) — PRs with failing tests will not be merged.
5. Update documentation (README, docstrings, ARCHITECTURE.md) if your change affects public APIs or behaviour.
6. Open the PR against `main`. Fill in the PR template.
7. A maintainer will review within a few business days. Address review comments in new commits (do not force-push during review).
8. Once approved, a maintainer will merge via squash.

**For large changes** (new subsystem, significant refactor): open a Discussion or draft PR early to align on approach before writing a lot of code.

---

## Code style

### Python

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting. It runs automatically via pre-commit.

```bash
ruff check .
ruff format .
```

Additional conventions:
- Type-annotate all public functions and class methods.
- Use `structlog` for logging — no bare `print()` statements in production code.
- Pydantic v2 for all data models. No raw `dict` in API boundaries.
- Avoid mutable module-level state; use dependency injection via FastAPI `Depends`.

### TypeScript (SDK)

We follow standard ESLint rules (config in `sdk/`). Run:

```bash
cd sdk && npm run lint
```

### SQL

- Use parameterised queries everywhere — no string interpolation with user-supplied values.
- Analytics queries must target allow-listed views only. Never expose raw table access via the NL→SQL path.

---

## Testing

### Rules engine (must pass 100%)

```bash
pytest rules/tests/ -v
```

### API tests

```bash
pytest api/ -v --asyncio-mode=auto
```

### Eval harness (retrieval + answer quality)

```bash
pytest eval/harness/ -v
```

### Full suite

```bash
pytest --cov=api --cov=rules --cov=ingestion -v
```

When adding a new BRSR check or emission factor:
- Add a corresponding unit test in `rules/tests/`.
- Include at least one positive case, one boundary case, and one rejection case.

---

## Working with the knowledge base

The knowledge base (regulatory documents, field catalogues, emission factors) is central to the product's quality and trustworthiness.

- **Do not add synthetic or AI-generated regulatory content** to `kb/` or the ingestion pipeline without a human ESG practitioner review.
- Check licences before adding any document source — see `RESOURCES.md` for guidance. GRI, SASB, ISSB, and CDP texts have usage restrictions.
- Every added document source should be recorded in the KB register (see `RESOURCES.md` §K) with `url`, `version/date`, `sha256`, and `licence`.
- Emission factors must cite their source year and issuer. Undated or unattributed factors will not be merged.

---

## Licensing

By contributing to this project you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).

If you are contributing on behalf of an employer, make sure you have the right to do so under your employment agreement.
