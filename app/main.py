from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.orchestrator import run_investigation
from app.schemas import InvestigationReport, InvestigationRequest

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="End-to-End AML Investigation Pipeline",
    description=(
        "Unified financial crime investigation engine combining Sanctions Entity Resolution, "
        "Transaction Anomaly Scoring, and Multi-Hop Graph Forensics."
    ),
    version="1.0.0",
)


@app.get("/", include_in_schema=False)
def workbench_ui() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "aml-investigation-pipeline"}


@app.post("/investigate", response_model=InvestigationReport)
def investigate_case(request: InvestigationRequest) -> InvestigationReport:
    return run_investigation(request)