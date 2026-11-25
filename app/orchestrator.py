from app.schemas import (
    InvestigationReport,
    InvestigationRequest,
    RiskDisposition,
    StageResult,
)
from app.stages.anomaly import run_anomaly_stage
from app.stages.network import run_network_stage
from app.stages.sanctions import run_sanctions_stage

# Stage weights for composite risk score
WEIGHT_SANCTIONS = 0.45
WEIGHT_ANOMALY = 0.25
WEIGHT_NETWORK = 0.30


def build_audit_narrative(
    request: InvestigationRequest,
    disposition: RiskDisposition,
    composite_score: float,
    stages: list[StageResult],
) -> str:
    """Generate a concise, auditable SAR/UAR-style summary from stage findings."""
    flagged_stages = [s.stage for s in stages if s.flagged]
    all_reasons = [
        f"[{s.stage}] {reason}"
        for s in stages
        for reason in s.reasons
        if s.flagged or s.score > 0
    ]

    if not all_reasons:
        evidence_summary = "All screening, behavioral, and network checks cleared within baseline parameters."
    else:
        evidence_summary = " | ".join(all_reasons)

    return (
        f"Case {request.case_id} ({request.entity.name}, ID: {request.entity.entity_id}) "
        f"assigned disposition {disposition.value} with composite risk score {composite_score:.2f}/100. "
        f"Flagged stages: {', '.join(flagged_stages) if flagged_stages else 'None'}. "
        f"Key findings: {evidence_summary}"
    )


def run_investigation(request: InvestigationRequest) -> InvestigationReport:
    """Execute the end-to-end AML investigation pipeline across all three stages."""
    sanctions_res = run_sanctions_stage(request.entity)
    anomaly_res = run_anomaly_stage(request.transaction)
    network_res = run_network_stage(
        entity_id=request.entity.entity_id,
        edges=request.network_edges,
        known_high_risk_nodes=request.known_high_risk_nodes,
    )

    stages = [sanctions_res, anomaly_res, network_res]

    weighted_score = (
        WEIGHT_SANCTIONS * sanctions_res.score
        + WEIGHT_ANOMALY * anomaly_res.score
        + WEIGHT_NETWORK * network_res.score
    )

    # Compounding risk boost when multiple independent typologies trigger together
    flagged_count = sum(1 for s in stages if s.flagged)
    if flagged_count >= 2:
        weighted_score += 12.0 * (flagged_count - 1)

    composite_score = round(min(100.0, weighted_score), 2)

    # Hard override & composite threshold disposition rules
    sanctions_tier = sanctions_res.metadata.get("tier")
    if sanctions_tier == "HIGH_RISK_HIT" or composite_score >= 65.0 or flagged_count >= 2:
        disposition = RiskDisposition.ESCALATE_SAR
    elif flagged_count == 1 or composite_score >= 30.0:
        disposition = RiskDisposition.ANALYST_REVIEW
    else:
        disposition = RiskDisposition.AUTO_CLEAR

    narrative = build_audit_narrative(request, disposition, composite_score, stages)

    return InvestigationReport(
        case_id=request.case_id,
        disposition=disposition,
        composite_risk_score=composite_score,
        stages=stages,
        audit_narrative=narrative,
    )