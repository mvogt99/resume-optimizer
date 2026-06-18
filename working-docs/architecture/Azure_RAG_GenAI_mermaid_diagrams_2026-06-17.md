# Azure RAG/GenAI + Config-Driven Data Platform — Mermaid Diagrams
2026-06-17 · renders natively on GitHub, GitLab, Confluence (Mermaid plugin), VS Code, Obsidian.

> Source-of-truth diagrams for the two reference docs. Paste any block into a Mermaid renderer.
> ASCII equivalents live in `Azure_RAG_GenAI_reference_architecture_*.md` (Part 1) and
> `Azure_ConfigDriven_DataPlatform_variants_*.md` (Part 2).

---

## 1. Arch A — Production RAG / GenAI on Azure

```mermaid
flowchart TD
  U["Web · Teams/Copilot · API clients"] -->|"HTTPS + Entra ID"| APIM["Azure API Management<br/>authN/Z · throttling · circuit-breaker"]
  APIM --> ORC["Orchestrator (Container Apps)<br/>AI Foundry Agent / Semantic Kernel<br/>plan → retrieve → prompt → tools → synthesize"]
  ORC --> SR["Azure AI Search<br/>hybrid: vector + BM25 + semantic ranker<br/>confidence-gated"]
  ORC --> GR["Cosmos DB<br/>GraphRAG + memory store"]
  ORC --> AOAI["Azure OpenAI<br/>GPT-4o · text-embedding-3 · model router"]
  AOAI -.->|"OSS / fine-tuned"| AML["Azure ML / AI Foundry<br/>GPU endpoints"]
  SR -->|"cited chunks"| ORC
  GR -->|"entities/edges"| ORC
  GOLD[("Governed GOLD data products<br/>(see data-platform variants)")] --> ING["Ingestion<br/>Functions / ACA Jobs / ADF<br/>chunk → embed → dual-write"]
  ING --> SR
  ING --> GR
  ORC --> CS["AI Content Safety<br/>jailbreak · groundedness"]
  ORC --> OBS["Azure Monitor / App Insights<br/>tokens · latency · groundedness"]
  PUR["Microsoft Purview<br/>catalog · lineage · classification"] --- GOLD
```

---

## 2. Configuration-driven control model (one config, swappable engines)

```mermaid
flowchart LR
  CFG["CONFIG / METADATA STORE<br/>App Configuration + Git repo + control DB<br/>sources · CDM entities · mappings · DQ rules<br/>access policies · platform selector · ai_grounding bindings"]
  CFG -->|"drives (parameterized pipelines)"| ENG["DATA ENGINE<br/>bronze → silver → GOLD<br/>governed data products"]
  CFG -->|"binds GOLD → index/graph"| RAG["RAG / GenAI tier (Arch A)"]
  ENG -->|"governed GOLD"| RAG
```

---

## 3. Variant 1 — Databricks Lakehouse

```mermaid
flowchart TD
  CFG["Config store<br/>DABs + Unity Catalog (metadata authority)"] --> DBX
  SRC["Sources: ADLS · CDC · API"] --> DBX
  subgraph DBX["Azure Databricks"]
    B["BRONZE Δ"] --> S["SILVER Δ"] --> G["GOLD Δ<br/>governed data products"]
    UC["Unity Catalog: lineage · ABAC"]
    MS["Mosaic AI / Model Serving · Genie (NL→SQL)"]
  end
  G --> PBI["Power BI (Import / DirectQuery)"]
  G --> EMB["Embedding job<br/>Databricks + Azure OpenAI"]
  EMB --> AIS["Azure AI Search index<br/>+ Cosmos GraphRAG"]
  AIS --> ARCHA["Arch A: GPT-4o orchestration"]
  PUR["Purview (estate catalog/lineage)"] --- UC
```

---

## 4. Variant 2 — Microsoft Fabric

```mermaid
flowchart TD
  CFG["Config store<br/>Fabric pipeline params + config Lakehouse table"] --> FAB
  SRC["Sources: Dataflows Gen2 · shortcuts · CDC"] --> FAB
  subgraph FAB["Microsoft Fabric"]
    B["OneLake BRONZE"] --> S["OneLake SILVER"] --> G["OneLake GOLD Δ<br/>single-copy"]
    DL["Direct Lake semantic models"]
    AGT["Fabric Data Agents / AI Skills"]
  end
  G --> PBI["Power BI Direct Lake + Copilot (BI GenAI)"]
  G --> EMB["Embedding skillset"]
  EMB --> AIS["Azure AI Search index<br/>+ Cosmos GraphRAG"]
  AIS --> ARCHA["Arch A: GPT-4o orchestration"]
  PUR["Purview + Fabric domain governance"] --- G
```

---

## 5. Variant 3 — Hybrid (config picks the engine per workload)

```mermaid
flowchart TD
  CFG["CONFIG store — per-workload selector<br/>platform: databricks | fabric<br/>one canonical model · data-product contracts · RAG bindings"]
  CFG -->|"platform: databricks"| DBX["Azure Databricks<br/>heavy ETL/ELT · DLT · ML (Mosaic AI)<br/>BRONZE→SILVER→GOLD Δ → ADLS/OneLake<br/>Unity Catalog governance"]
  CFG -->|"platform: fabric"| FAB["Microsoft Fabric<br/>BI semantic models · Direct Lake<br/>Power BI + Copilot · Data Agents"]
  DBX -->|"GOLD Δ (single copy)"| SHARE[("Shared GOLD Delta")]
  SHARE -.->|"OneLake shortcut (no copy)"| FAB
  SHARE --> EMB["Embedding job → AI Search (hybrid) + Cosmos GraphRAG"]
  EMB --> ARCHA["Arch A: GPT-4o orchestration · Content Safety · eval loop"]
  UC["Unity Catalog"] -. "federated governance" .- PUR["Microsoft Purview"]
  DBX --- UC
  FAB --- PUR
```

---

## 6. Render notes
- GitHub/GitLab/Obsidian render ```` ```mermaid ```` fences automatically.
- Confluence: use the *Mermaid Diagrams* macro/app, or convert with the Mermaid CLI
  (`mmdc -i file.md -o out.png`) for static images.
- These are intentionally simplified vs. the ASCII versions (whiteboard-friendly); the ASCII docs
  carry the full cross-cutting detail (security, governance, eval loop, data flows).
