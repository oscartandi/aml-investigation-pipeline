# End-to-End AML Investigation Pipeline

[![CI - AML Investigation Pipeline](https://github.com/oscartandi/aml-investigation-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/oscartandi/aml-investigation-pipeline/actions/workflows/ci.yml)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)

A unified financial crime investigation engine that orchestrates **Sanctions Entity Resolution**, **Real-Time Transaction Anomaly Detection**, and **Multi-Hop Graph Forensics** into a single auditable disposition (`ESCALATE_SAR`, `ANALYST_REVIEW`, or `AUTO_CLEAR`).

---

## Architecture & Investigation Flow

```mermaid
flowchart TD
    A[POST /investigate<br/>InvestigationRequest] --> B[Stage 1: Sanctions Resolution<br/>Normalization + RapidFuzz + DOB/Country]
    A --> C[Stage 2: Transaction Anomaly<br/>Structuring + 24h Velocity + Corridors]
    A --> D[Stage 3: Network Forensics<br/>NetworkX Multi-Hop + UBO + Cycles]

    B --> E[Composite Risk Orchestrator<br/>Weighted Score + Compounding Multi-Stage Boost]
    C --> E
    D --> E

    E --> F{Disposition Engine}
    F -->|HIGH_RISK_HIT or Score >= 65 or >= 2 Flagged Stages| G[ESCALATE_SAR + Audit Narrative]
    F -->|1 Flagged Stage or Score >= 30| H[ANALYST_REVIEW + Audit Narrative]
    F -->|Below Thresholds| I[AUTO_CLEAR + Audit Narrative]
