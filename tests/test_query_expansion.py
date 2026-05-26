import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from query_expansion import expand_query, infer_domain, build_queries

def test_expand_card_stolen():
    expanded = expand_query("my card was stolen yesterday")
    assert any("fraud" in q or "lost" in q for q in expanded)

def test_expand_login_issue():
    expanded = expand_query("I cannot login to my account")
    assert any("password" in q or "reset" in q for q in expanded)

def test_expand_no_match_returns_original():
    expanded = expand_query("general question about something")
    assert len(expanded) >= 1
    assert expanded[0] == "general question about something"

def test_infer_domain_devplatform():
    assert infer_domain("I sent an assessment to a candidate on HackerRank") == "devplatform"

def test_infer_domain_claude():
    assert infer_domain("My Claude API is returning 429 rate limit errors") == "claude"

def test_infer_domain_visa():
    assert infer_domain("My Visa card was declined at the merchant") == "visa"

def test_infer_domain_unknown():
    result = infer_domain("hello how are you")
    assert result == "unknown"

def test_build_queries_deduplicates():
    queries = build_queries(subject="billing issue", issue_text="I need a refund for my charge")
    assert len(queries) == len(set(queries))
    assert len(queries) >= 2

def test_build_queries_includes_subject_plus_issue():
    queries = build_queries(subject="card stolen", issue_text="my card is gone")
    combined = " ".join(queries)
    assert "card" in combined and "stolen" in combined
