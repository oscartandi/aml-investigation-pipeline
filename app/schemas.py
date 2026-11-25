from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RiskDisposition(str, Enum):
    ESCALATE_SAR = "ESCALATE_SAR"
    ANALYST_REVIEW = "ANALYST_REVIEW"
    AUTO_CLEAR = "AUTO_CLEAR"


class EntityInput(BaseModel):
    entity_id: str
    name: str
    entity_type: str = Field(default="INDIVIDUAL", description="INDIVIDUAL or CORPORATE")
    country: Optional[str] = None
    dob: Optional[str] = None


class TransactionContext(BaseModel):
    amount_usd: float = 0.0
    tx_count_24h: int = 0
    total_volume_24h: float = 0.0
    counterparty_country: Optional[str] = None


class NetworkEdge(BaseModel):
    source: str
    target: str
    relation: str  # e.g., "SHARED_DEVICE", "BENEFICIAL_OWNER", "TRANSFER"
    weight: float = 1.0


class InvestigationRequest(BaseModel):
    case_id: str
    entity: EntityInput
    transaction: Optional[TransactionContext] = None
    network_edges: list[NetworkEdge] = Field(default_factory=list)
    known_high_risk_nodes: list[str] = Field(default_factory=list)


class StageResult(BaseModel):
    stage: str
    score: float
    flagged: bool
    reasons: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class InvestigationReport(BaseModel):
    case_id: str
    disposition: RiskDisposition
    composite_risk_score: float
    stages: list[StageResult]
    audit_narrative: str