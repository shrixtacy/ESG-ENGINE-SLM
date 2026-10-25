# RESOURCES.md — Data Sources, Models & Tools

> ⚠️ **Verify before ingesting.** Links below are the official portals/landing pages I'm confident about. Regulators reorganise URLs often and rules may have changed recently (BRSR assurance/value-chain phase-ins, new circulars). For each source: open it, download the *latest in-force* version, record `url + date + sha256` in the KB register. Deep links to specific circulars should be pulled from the portal's search (keywords given).
>
> ⚖️ **Licensing:** Government docs (SEBI/MCA/UN) are generally fine to index and cite. **GRI, SASB, ISSB/IFRS, CDP, ESRS** have their own terms — link/summarise, and check licence before redistributing text or training on it. Keep a licence column in your KB register.

---

## A. Indian Regulatory Core (Priority 1)

| # | Source | What to pull | Link | Search keywords |
|---|---|---|---|---|
| A1 | **SEBI** | BRSR format (Annexure I/II), BRSR Core, circulars on assurance, value chain disclosures, FAQs, industry-standards note | https://www.sebi.gov.in | "Business Responsibility and Sustainability Reporting", "BRSR Core", "ESG disclosures", "value chain" |
| A2 | **SEBI LODR Regulations** | Reg. 34(2)(f) and amendments (BRSR applicability, top-1000 listed entities) | https://www.sebi.gov.in/legal/regulations.html | "LODR 2015 consolidated" |
| A3 | **MCA** | National Guidelines on Responsible Business Conduct (NGRBC, 2019), Companies Act s.135 + CSR Rules, Schedule VII, CSR amendments | https://www.mca.gov.in | "NGRBC", "CSR Rules 2014 amendment 2021", "Companies Act 2013" |
| A4 | **MCA – Companies Act text** | Full Act (for s.134/135, board report) | https://www.indiacode.nic.in | "Companies Act 2013" |
| A5 | **BSE / NSE** | Published BRSR filings of listed companies (training/eval examples, benchmarks) | https://www.bseindia.com , https://www.nseindia.com | NSE: *Corporate Filings → Business Sustainability Reports*; BSE: *Corporate Announcements/Annual Reports* |
| A6 | **MoEFCC** | EIA notifications, environmental clearance conditions, hazardous waste, e-waste, plastic EPR, battery rules | https://moef.gov.in | "EIA notification 2006", "Plastic Waste Management Rules", "E-Waste Rules 2022", "Hazardous Waste Rules" |
| A7 | **CPCB** | Pollution standards, EPR portals, consent-to-operate norms, waste/effluent standards | https://cpcb.nic.in | "emission standards", "EPR", "water quality criteria" |
| A8 | **BEE** | PAT scheme, energy audits, Energy Conservation Act, **India Carbon Market (CCTS)** | https://beeindia.gov.in | "PAT scheme", "Carbon Credit Trading Scheme" |
| A9 | **CEA** | **CO₂ Baseline Database** (grid emission factor for Scope 2), installed capacity data | https://cea.nic.in | "CO2 baseline database" |
| A10 | **Ministry of Labour** | Labour Codes (wages, OSH, social security, IR), minimum wages, POSH, Maternity Benefit Act | https://labour.gov.in | "Code on Occupational Safety", "Code on Wages" |
| A11 | **DGFASLI / Factories Act** | OSH metrics (LTIFR context), factory safety rules | https://dgfasli.gov.in | "Factories Act" |
| A12 | **POSH / Disability / Equal Remuneration** | Social (S) pillar legal basis | https://www.indiacode.nic.in | "POSH Act 2013", "RPwD Act 2016" |
| A13 | **MeitY – DPDP Act 2023** | Data privacy (BRSR P9 consumer data + your own compliance) | https://www.meity.gov.in | "Digital Personal Data Protection Act" |
| A14 | **RBI / SEBI Green finance** | Green bonds, sustainable finance framework (if client is a financial entity) | https://www.rbi.org.in | "sustainable finance", "green deposit" |
| A15 | **MNRE** | Renewable targets, RPO, wind/solar policy (for power/infra clients like MEIL) | https://mnre.gov.in | "RPO", "renewable purchase obligation" |
| A16 | **Ministry of Jal Shakti / CGWA** | Groundwater extraction NOC, water norms (irrigation/water-infra clients) | https://jalshakti-dowr.gov.in , https://cgwb.gov.in | "groundwater NOC guidelines" |
| A17 | **State Pollution Control Boards** (e.g., Odisha SPCB, Telangana PCB) | State-specific consent norms | https://ospcboard.org | per state |

## B. UN SDGs & India's SDG Framework (Priority 1)

| # | Source | What to pull | Link |
|---|---|---|---|
| B1 | **UN SDG portal** | 17 goals, 169 targets, descriptions | https://sdgs.un.org/goals |
| B2 | **UN Stats – Global Indicator Framework** | 231 unique indicators list + **metadata sheets** (definitions, computation, sources) | https://unstats.un.org/sdgs/indicators/indicators-list/ , https://unstats.un.org/sdgs/metadata/ |
| B3 | **UN SDG Report / SDG Database** | Global progress, data | https://unstats.un.org/sdgs/report , https://unstats.un.org/sdgs/dataportal |
| B4 | **NITI Aayog – SDG India Index & Dashboard** | State/UT indicator framework, scores, methodology | https://sdgindiaindex.niti.gov.in |
| B5 | **MoSPI – National Indicator Framework (NIF) & SDG** | India's national indicators mapped to SDGs, progress reports | https://mospi.gov.in (section: Sustainable Development Goals) |
| B6 | **India Voluntary National Review (VNR)** | India's SDG narrative | https://sustainabledevelopment.un.org/vnrs/ |
| B7 | **SDG–Company mapping guidance** | **SDG Compass** (GRI + UN Global Compact + WBCSD) | https://sdgcompass.org |
| B8 | **UN Global Compact** | Ten Principles, SDG business guides | https://unglobalcompact.org |
| B9 | **OSDG / Aurora SDG queries** | SDG text-classification query sets & open dataset (for tagging model) | https://osdg.ai , https://aurora-universities.eu |
| B10 | **SDG Impact Standards (UNDP)** | Impact management for enterprises | https://sdgimpact.undp.org |

## C. Global Reporting Frameworks (Priority 2 — for cross-mapping)

| # | Source | Link | Notes |
|---|---|---|---|
| C1 | **GRI Standards** (Universal, Sector, Topic) | https://www.globalreporting.org/standards/ | Free to download; check terms. Use for BRSR↔GRI crosswalk |
| C2 | **ISSB – IFRS S1 / S2** | https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ | India adoption roadmap via ICAI/NFRA — track |
| C3 | **SASB Standards** (industry-specific) | https://sasb.ifrs.org | Great for sector KPIs (infra, engineering, construction) |
| C4 | **TCFD recommendations** | https://www.fsb-tcfd.org | Now folded into ISSB, still referenced |
| C5 | **GHG Protocol** (Corporate, Scope 2 Guidance, Scope 3 Standard) | https://ghgprotocol.org/standards | Core for emissions calc rules |
| C6 | **CDP** questionnaires (climate, water, forests) | https://www.cdp.net | Licence restricted — use as structure reference |
| C7 | **SBTi** | https://sciencebasedtargets.org | Target-setting criteria |
| C8 | **EU CSRD / ESRS** | https://finance.ec.europa.eu (search "CSRD") and EFRAG https://www.efrag.org | For clients with EU exposure |
| C9 | **ISO 14001 / 14064 / 45001 / 26000** | https://www.iso.org | Paid standards — don't ingest text; summarise public descriptions |
| C10 | **IPCC Guidelines / AR6 GWP values** | https://www.ipcc.ch | GWP factors for CO₂e conversion |
| C11 | **UN Guiding Principles on Business & Human Rights** | https://www.ohchr.org | Social/human-rights reference for NGRBC P5 |
| C12 | **OECD Guidelines for MNEs** | https://www.oecd.org | RBC due diligence |
| C13 | **IFC Performance Standards** | https://www.ifc.org | Project-level E&S standards (infra projects) |

## D. Data for Rules Engine (Emission Factors, Conversions)

| Data | Source | Link |
|---|---|---|
| India grid EF (tCO₂/MWh) | CEA CO₂ Baseline Database | https://cea.nic.in |
| India GHG Programme (WRI India, CII, TERI) methodology & tools | India GHG Program | https://indiaghgp.org |
| IPCC EF Database | IPCC | https://www.ipcc-nggip.iges.or.jp/EFDB/main.php |
| DEFRA/UK conversion factors (fuel/transport/material) | UK Gov | https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting |
| EPA emission factors hub | US EPA | https://www.epa.gov/climateleadership/ghg-emission-factors-hub |
| Ecoinvent / ICE database (embodied carbon, construction) | Check licences | https://ecoinvent.org , https://circularecology.com/embodied-carbon-footprint-database.html |
| India Petroleum / PPAC fuel data | PPAC | https://ppac.gov.in |
| Calorific values & conversions | BEE / CEA / IPCC | (as above) |

## E. Real-World Report Corpus (for RAG examples, SFT data, eval)

| Source | What | How |
|---|---|---|
| NSE / BSE BRSR filings | 1000+ real BRSRs (PDF/XBRL) → learn real disclosure style, field values, ranges | Bulk download per FY; parse with Docling; **store as `kb_examples`**, anonymise if shown to others |
| Company sustainability reports (Tata, Infosys, L&T, Adani, Reliance, JSW, NTPC, Power Grid, etc.) | Narrative quality, GRI/SDG mapping | Company IR sites; respect copyright (use for training analysis/eval, don't redistribute) |
| MEIL / client private docs | Internal policies, past reports | Only via tenant-private KB with client consent; never in global index. (MEIL is unlisted — expect no BRSR filing; use client-provided data) |
| CDP public responses | Climate disclosure examples | https://www.cdp.net/en/responses (terms apply) |
| Corporate Sustainability Reports hubs | Cross-company access | https://www.sustainability-reports.com (verify availability) , https://www.responsibilityreports.com |
| Climate TRACE / WRI | Emissions benchmarking context | https://climatetrace.org , https://www.wri.org |

## F. Public ESG / Climate NLP Datasets & Models (for fine-tuning components)

> Search these on Hugging Face and **check each licence** before use.

| Use | Resource | Link |
|---|---|---|
| Climate-domain BERTs & datasets (ClimateBERT: detector, sentiment, specificity, commitments & actions, TCFD classifier) | ClimateBERT org | https://huggingface.co/climatebert |
| ESG topic classification (E/S/G) | ESG-BERT & variants | https://huggingface.co/models?search=esg-bert |
| SDG text classification | SDG BERT classifiers / OSDG dataset | https://huggingface.co/models?search=sdg |
| Climate claim detection / fact-check datasets | Climate-FEVER, ClimaText | https://huggingface.co/datasets?search=climate |
| Financial/sustainability QA | FinQA/ConvFinQA-style sets (adapt) | https://huggingface.co/datasets?search=finqa |
| Table QA over reports | TAT-QA, ConvFinQA | https://huggingface.co/datasets?search=tat-qa |
| Multilingual embeddings | BGE-M3 | https://huggingface.co/BAAI/bge-m3 |
| Reranker | bge-reranker-v2-m3 | https://huggingface.co/BAAI/bge-reranker-v2-m3 |
| Indian-language translation | IndicTrans2 | https://github.com/AI4Bharat/IndicTrans2 |

## G. SLM Base Model Candidates

| Model | Size | Link | Note |
|---|---|---|---|
| Qwen2.5-Instruct | 3B / 7B | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct | Strong JSON/tool use, multilingual (check licence per size — 3B has a different licence than 7B) |
| Llama 3.1 / 3.2 Instruct | 8B / 3B | https://huggingface.co/meta-llama | Gated, community licence |
| Phi-3.5-mini / Phi-4-mini | ~3.8B | https://huggingface.co/microsoft | MIT licence, good reasoning for size |
| Gemma 2 / 3 | 2B–9B | https://huggingface.co/google | Gemma terms |
| Mistral 7B / Ministral | 7B | https://huggingface.co/mistralai | Check licence version |

> Run a bake-off on your own eval set (Stage 0) before picking. Verify latest releases — this space moves fast.

## H. Tooling Links

| Purpose | Tool | Link |
|---|---|---|
| Serving | vLLM | https://github.com/vllm-project/vllm |
| Local/dev serving | Ollama / llama.cpp | https://ollama.com , https://github.com/ggml-org/llama.cpp |
| Fine-tuning | Unsloth / TRL / Axolotl / PEFT | https://github.com/unslothai/unsloth , https://github.com/huggingface/trl , https://github.com/axolotl-ai-cloud/axolotl |
| Orchestration | LangGraph | https://github.com/langchain-ai/langgraph |
| Vector DB | Qdrant / pgvector | https://qdrant.tech , https://github.com/pgvector/pgvector |
| Doc parsing | Docling / Unstructured / PyMuPDF | https://github.com/docling-project/docling , https://github.com/Unstructured-IO/unstructured , https://pymupdf.readthedocs.io |
| OCR | PaddleOCR / Tesseract | https://github.com/PaddlePaddle/PaddleOCR , https://github.com/tesseract-ocr/tesseract |
| RAG eval | RAGAS / DeepEval | https://github.com/explodinggradients/ragas , https://github.com/confident-ai/deepeval |
| LLM observability | Langfuse | https://langfuse.com |
| Guardrails | Guardrails AI / Outlines (guided decoding) | https://github.com/guardrails-ai/guardrails , https://github.com/dottxt-ai/outlines |
| Workflow automation | n8n | https://n8n.io |
| Web UI components | Lit / Preact | https://lit.dev , https://preactjs.com |
| Charts | Vega-Lite | https://vega.github.io/vega-lite/ |

## I. Knowledge Base Build Order (what to ingest first)

1. **BRSR format + BRSR Core + all SEBI circulars/FAQs** (A1, A2) → drives field catalogue.
2. **NGRBC 2019 + Companies Act s.135/CSR Rules** (A3).
3. **UN SDG goals/targets/indicator metadata + NIF/NITI** (B1–B5) → SDG mapper.
4. **GHG Protocol + CEA baseline + IPCC GWP** (C5, A9, C10) → emissions rules.
5. **Environmental & labour law basics** (A6–A12) → answers for P2/P3/P5/P6 doubts.
6. **GRI + SASB + ISSB crosswalks** (C1–C3) → cross-framework mapping.
7. **Real BRSR corpus** (E) → examples, ranges, SFT/eval data.
8. **Tenant-private docs** → per-client index.

## J. Human Expertise (don't skip)
- Hire/contract **1 ESG consultant / BRSR assurance practitioner** for: field catalogue sign-off, SFT data review (≥20%), gold eval set, regulatory-change review.
- Possible networks: ICAI sustainability committees, CII/TERI/WRI India workshops, Indian Institute of Corporate Affairs (IICA — https://iica.nic.in) which runs ESG/BRSR programmes.

## K. KB Register Template (keep this in your repo)

| doc_id | title | issuer | version/date | effective_from–to | url | sha256 | licence | scope (global/tenant) | ingested_on | reviewed_by |
|---|---|---|---|---|---|---|---|---|---|---|
