from typing import List

EXPANSION_MAP = {
    "card stolen":      "lost stolen card fraud",
    "card was stolen":  "lost stolen card fraud",
    "card lost":        "lost stolen card fraud",
    "card missing":     "lost stolen card fraud",
    "card compromised": "stolen compromised card fraud security",
    "card declined":    "card declined payment merchant transaction",
    "cannot login":     "password reset account access authentication sign in",
    "can't login":      "password reset account access authentication sign in",
    "login failed":     "password reset account access authentication",
    "sign in":          "login account access authentication",
    "forgot password":  "password reset account access authentication",
    "billing":          "invoice payment subscription refund charge",
    "refund":           "billing invoice refund transaction payment",
    "charge":           "billing invoice payment refund transaction",
    "overcharged":      "billing refund payment dispute transaction",
    "test candidate":   "HackerRank test assessment invite screen",
    "assessment":       "HackerRank test assessment invite screen candidate",
    "invite":           "candidate invite test assessment email",
    "rate limit":       "API rate limit quota throttle 429 error",
    "api error":        "API error connection timeout authentication 429",
    "api key":          "API key authentication access credentials",
    "account delete":   "delete account close remove deactivate",
    "delete account":   "delete account close remove deactivate",
    "account closed":   "delete account close remove deactivate",
    "fraud":            "fraud unauthorized transaction suspicious security",
    "unauthorized":     "fraud unauthorized transaction suspicious access",
    "dispute":          "dispute chargeback refund unauthorized transaction",
    "traveller":        "travellers cheques lost stolen refund citicorp",
    "cheque":           "travellers cheques lost stolen refund",
    "site down":        "outage down unavailable service disruption",
    "not working":      "error bug issue troubleshoot unavailable",
    "slow":             "performance latency timeout slow response",
}

DOMAIN_KEYWORDS = {
    "devplatform": [
        "hackerrank", "devplatform", "test", "assessment", "candidate", "interview",
        "screen", "invite", "coding", "challenge", "submission", "proctoring",
        "library", "question", "role", "skill", "webhook", "recruiter",
        "plagiarism", "anti-cheat", "time limit", "test variant",
    ],
    "claude": [
        "claude", "anthropic", "api", "console", "prompt", "model", "token",
        "context", "rate limit", "message", "conversation", "subscription",
        "pro plan", "team plan", "enterprise", "bedrock", "sonnet", "haiku",
        "opus", "workbench", "workspace", "usage", "billing claude",
    ],
    "visa": [
        "visa", "card", "payment", "transaction", "merchant", "chargeback",
        "dispute", "fraud", "traveller", "cheque", "atm", "pin", "contactless",
        "debit", "credit", "cardholder", "issuer", "acquirer", "network",
    ],
}

def infer_domain(text: str) -> str:
    text_lower = text.lower()
    scores = {
        domain: sum(1 for kw in keywords if kw in text_lower)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"

def expand_query(text: str) -> List[str]:
    queries = [text]
    text_lower = text.lower()
    for trigger, expansion in EXPANSION_MAP.items():
        if trigger in text_lower:
            queries.append(expansion)
    return queries

def build_queries(subject: str, issue_text: str) -> List[str]:
    """Build deduplicated multi-query list for BM25 RRF search."""
    raw = [
        issue_text[:256],
        f"{subject} {issue_text}"[:256],
    ]
    expanded = expand_query(issue_text)
    if subject:
        expanded += expand_query(subject)

    seen = []
    for q in raw + expanded:
        q = q.strip()
        if q and q not in seen:
            seen.append(q)
    return seen
