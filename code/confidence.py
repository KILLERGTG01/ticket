from typing import List

RISK_PENALTY = {"low": 0.0, "medium": 0.05, "high": 0.15, "critical": 0.25}

def compute_confidence(
    retrieval_scores: List[float],
    risk_level: str,
    injection_detected: bool,
    pii_detected: bool,
    actions_valid: bool,
    num_sources: int,
    company_mismatch: bool,
) -> float:
    if retrieval_scores:
        base = sum(retrieval_scores[:3]) / min(len(retrieval_scores), 3)
    else:
        base = 0.30

    source_bonus = min(num_sources * 0.05, 0.15)

    risk_pen     = RISK_PENALTY.get(risk_level, 0.0)
    inject_pen   = 0.40 if injection_detected else 0.0
    pii_pen      = 0.05 if pii_detected else 0.0
    action_pen   = 0.10 if not actions_valid else 0.0
    mismatch_pen = 0.10 if company_mismatch else 0.0

    score = base + source_bonus - risk_pen - inject_pen - pii_pen - action_pen - mismatch_pen
    return round(max(0.05, min(0.95, score)), 3)
