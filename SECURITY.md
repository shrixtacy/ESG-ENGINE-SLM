# Security Policy

## Supported Versions

We actively maintain the latest release on `main`. Security fixes are backported when feasible.

| Branch | Supported |
|---|---|
| `main` | ✅ Yes |
| Older tags | ❌ No guarantee |

---

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

To report a vulnerability, contact the maintainers privately:

1. Go to the **Security** tab of this repository on GitHub.
2. Click **"Report a vulnerability"** (GitHub's private advisory feature).
3. Fill in the details — steps to reproduce, potential impact, and any suggested fix.

We will acknowledge your report within **72 hours** and aim to have a triage decision within **7 days**. We will keep you updated as we work on a fix and coordinate responsible disclosure timing with you.

---

## Scope

The following are in scope for security reports:

- **Authentication / authorisation bypass** — tenant isolation (RLS), JWT handling, role-based access control
- **Data leakage between tenants** — cross-tenant vector index access, SQL injection via NL→SQL path
- **Remote code execution** — via API inputs, document parsing pipeline, or ingestion scripts
- **PII / secret exposure** — in logs, API responses, or the knowledge base
- **Prompt injection** — inputs causing the LLM to act as an instruction source rather than data
- **Dependency vulnerabilities** — critical CVEs in pinned packages in `requirements.txt` or `package.json`

Out of scope (unless they lead to a higher-severity issue):

- Denial-of-service via legitimate rate limits
- Self-XSS (requires the attacker to run code in their own browser)
- Missing security headers on documentation pages
- Social engineering

---

## Security Design Notes

For contributors and auditors, key security decisions in this codebase:

- **Tenant isolation**: every database table has a `tenant_id` column enforced via PostgreSQL Row-Level Security. Never bypass RLS by using a superuser connection in application code.
- **Vector isolation**: each tenant gets a separate Qdrant collection (`kb_tenant_{id}`). The retrieval service enforces a `tenant_scope` filter on every query.
- **NL → SQL**: the SLM emits a structured query-plan JSON (metric, dimensions, filters). A server-side validator converts this to parameterised SQL against an allow-listed set of views. The SLM never has access to raw table names or a SQL execution path.
- **Prompt injection defence**: form values and uploaded documents are delimited and treated as *data* in the system prompt, never as instructions. Instruction hierarchy is enforced at the prompt level.
- **Secrets**: never commit secrets to this repository. Use `.env` (gitignored) locally and a secrets manager (Vault, AWS Secrets Manager, etc.) in production.
- **PII**: PII redaction runs on all inputs before logging. Do not add logging that captures raw form values.
- **JWT**: session tokens have a 15-minute TTL. Refresh tokens are issued by the host backend, not this service.

---

## Dependency Updates

We use `pip-audit` and `npm audit` in CI. If you notice a critical CVE in a pinned dependency before CI catches it, please report it using the process above.
