from typing import Optional
from app.schemas import StageResult, TransactionContext

STRUCTURING_THRESHOLD_USD = 10000.0
HIGH_VELOCITY_TX_COUNT = 8
HIGH_VOLUME_24H_USD = 25000.0
HIGH_RISK_CORRIDORS = {"IR", "KP", "SY", "MM", "RU"}


def run_anomaly_stage(tx: Optional[TransactionContext]) -> StageResult:
    """Score transaction structuring, 24h velocity, and high-risk corridor signals."""
    if tx is None:
        return StageResult(
            stage="transaction_anomaly",
            score=0.0,
            flagged=False,
            reasons=["No transaction context provided for this investigation case"],
            metadata={"signals_triggered": 0},
        )

    score = 0.0
    reasons: list[str] = []
    signals = 0

    # 1. Structuring / smurfing just below standard $10,000 reporting threshold
    if 7500.0 <= tx.amount_usd < STRUCTURING_THRESHOLD_USD and tx.tx_count_24h >= 3:
        score += 35.0
        signals += 1
        reasons.append(
            f"Potential structuring: single tx ${tx.amount_usd:,.2f} below $10k threshold across {tx.tx_count_24h} txs/24h"
        )

    # 2. High 24-hour transaction velocity
    if tx.tx_count_24h >= HIGH_VELOCITY_TX_COUNT:
        score += 25.0
        signals += 1
        reasons.append(f"High 24h transaction velocity ({tx.tx_count_24h} transactions)")

    # 3. Elevated 24-hour cumulative volume
    if tx.total_volume_24h >= HIGH_VOLUME_24H_USD:
        score += 25.0
        signals += 1
        reasons.append(f"Elevated 24h volume (${tx.total_volume_24h:,.2f} USD)")

    # 4. Cross-border exposure to elevated-risk jurisdiction
    if tx.counterparty_country and tx.counterparty_country.upper() in HIGH_RISK_CORRIDORS:
        code = tx.counterparty_country.upper()
        score += 30.0
        signals += 1
        reasons.append(f"Counterparty jurisdiction in high-risk corridor ({code})")

    clamped_score = round(min(100.0, score), 2)
    flagged = clamped_score >= 30.0

    if not reasons:
        reasons.append("Transaction patterns within normal baseline thresholds")

    return StageResult(
        stage="transaction_anomaly",
        score=clamped_score,
        flagged=flagged,
        reasons=reasons,
        metadata={
            "signals_triggered": signals,
            "amount_usd": tx.amount_usd,
            "tx_count_24h": tx.tx_count_24h,
            "total_volume_24h": tx.total_volume_24h,
        },
    )