# Changelog

All notable changes to ESG-ENGINE-SLM will be documented here.

This project adheres to [Semantic Versioning](https://semver.org/) and [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) conventions.

---

## [Unreleased]

### Added
- Initial open-source release of the ESGPilot backend, rules engine, ingestion pipeline, TypeScript SDK, and reference Next.js frontend
- FastAPI backend with LangGraph orchestrator, rules engine, and RAG retrieval service
- BRSR field catalogue (YAML) with completeness, consistency, and boundary checks
- India emission factor tables with source attribution (CEA, IPCC)
- Ingestion crawlers for SEBI, MCA, and UN SDG portals
- PDF, HTML, and table parsers for regulatory document ingestion
- TypeScript SDK with L1 (schema push), L2 (declarative attributes), and L3 (auto-discovery) form adapters
- Guardrails service: cite-or-abstain, no-number policy, PII filter, scope policy
- SFT / DPO training scripts (LoRA, QLoRA) and AWQ quantisation script
- BRSR Q&A gold set for evaluation (`eval/gold_sets/brsr_qa.jsonl`)
- Docker Compose stack (API, PostgreSQL, Qdrant, Redis)
- GitHub Actions CI (lint, type-check, rules tests, API tests, dependency audit)
- Apache 2.0 licence, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, issue templates, PR template

---

## Format reference

Sections used in each release entry:

- **Added** — new features
- **Changed** — changes to existing behaviour
- **Deprecated** — features to be removed in a future release
- **Removed** — features removed in this release
- **Fixed** — bug fixes
- **Security** — vulnerability fixes (reference CVE or advisory where possible)
