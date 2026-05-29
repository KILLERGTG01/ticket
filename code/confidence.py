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
        s = retrieval_scores
        # Use score drop-off to signal retrieval quality:
        # top score is always ~1.0 (RRF-normalized); second+ scores reveal true discrimination.
        top   = s[0] if len(s) > 0 else 0.5
        sec   = s[1] if len(s) > 1 else top * 0.7
        third = s[2] if len(s) > 2 else sec * 0.7
        # Weight second and third heavily so their drop creates calibration spread
        base = top * 0.40 + sec * 0.40 + third * 0.20
    else:
        base = 0.30

    source_bonus = min(num_sources * 0.02, 0.06)

    risk_pen     = RISK_PENALTY.get(risk_level, 0.0)
    inject_pen   = 0.40 if injection_detected else 0.0
    pii_pen      = 0.05 if pii_detected else 0.0
    action_pen   = 0.10 if not actions_valid else 0.0
    mismatch_pen = 0.10 if company_mismatch else 0.0

    score = base + source_bonus - risk_pen - inject_pen - pii_pen - action_pen - mismatch_pen
    return round(max(0.05, min(0.88, score)), 3)
