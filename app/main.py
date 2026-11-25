from fastapi import FastAPI
from app.orchestrator import run_investigation
from app.schemas import InvestigationReport, InvestigationRequest

app = FastAPI(
    title="End-to-End AML Investigation Pipeline",
    description=(
        "Unified financial crime investigation engine combining Sanctions Entity Resolution, "
        "Transaction Anomaly Scoring, and Multi-Hop Graph Forensics."
    ),
    version="1.0.0",
)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "aml-investigation-pipeline",
        "docs": "/docs",
        "health": "/health",
        "investigate_endpoint": "POST /investigate",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "aml-investigation-pipeline"}


@app.post("/investigate", response_model=InvestigationReport)
def investigate_case(request: InvestigationRequest) -> InvestigationReport:
    return run_investigation(request)