import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from confidence import compute_confidence

def test_high_retrieval_no_flags():
    score = compute_confidence(
        retrieval_scores=[0.92, 0.88, 0.85],
        risk_level="low",
        injection_detected=False,
        pii_detected=False,
        actions_valid=True,
        num_sources=2,
        company_mismatch=False,
    )
    assert score >= 0.75

def test_no_sources_lowers_confidence():
    score = compute_confidence(
        retrieval_scores=[],
        risk_level="low",
        injection_detected=False,
        pii_detected=False,
        actions_valid=True,
        num_sources=0,
        company_mismatch=False,
    )
    assert score <= 0.45

def test_injection_lowers_confidence():
    score = compute_confidence(
        retrieval_scores=[0.9],
        risk_level="high",
        injection_detected=True,
        pii_detected=False,
        actions_valid=True,
        num_sources=1,
        company_mismatch=False,
    )
    assert score <= 0.40

def test_invalid_actions_lowers_confidence():
    score = compute_confidence(
        retrieval_scores=[0.88],
        risk_level="low",
        injection_detected=False,
        pii_detected=False,
        actions_valid=False,
        num_sources=1,
        company_mismatch=False,
    )
    base = compute_confidence(
        retrieval_scores=[0.88],
        risk_level="low",
        injection_detected=False,
        pii_detected=False,
        actions_valid=True,
        num_sources=1,
        company_mismatch=False,
    )
    assert score < base

def test_score_bounded():
    for _ in range(10):
        s = compute_confidence([0.5], "medium", False, False, True, 1, False)
        assert 0.0 <= s <= 1.0
