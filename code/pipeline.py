import json, os, re
from typing import List, Tuple

from classifier import detect_pii, detect_injection, detect_language, mask_pii
from agent import build_prompt, call_openai
from tools import validate_actions
from confidence import compute_confidence
from query_expansion import build_queries, infer_domain

_LEGAL_RE = re.compile(
    r'\b(sue|lawsuit|litigation|lawyer|attorney|legal action|court|damages|'
    r'regulatory complaint|file a complaint)\b', re.IGNORECASE
)
_IDENTITY_THEFT_RE = re.compile(
    r'\b(identity theft|identity (?:has been |was |is )?stolen|stolen identity|stole my identity|account takeover|'
    r'unauthorized access|hacked my account|someone else.{0,20}account)\b', re.IGNORECASE
)
_FRAUD_URGENT_RE = re.compile(
    r'\b(fraudulent (charge|transaction)|unauthorized (charge|transaction)|'
    r'card (stolen|compromised|cloned))\b', re.IGNORECASE
)
COMPANY_DOMAINS = {
    "DevPlatform": "devplatform",
    "Claude": "claude",
    "Visa": "visa",
}

def parse_issue_text(issue_json: str) -> str:
    try:
        turns = json.loads(issue_json)
        if isinstance(turns, list):
            return "\n".join(
                f"{t.get('role','user').capitalize()}: {t.get('content','')}"
                for t in turns
            )
        return str(turns)
    except (json.JSONDecodeError, TypeError):
        return str(issue_json)

def classify_full_text(subject: str, issue_text: str):
    combined = (subject or "") + "\n" + issue_text
    pii       = detect_pii(combined)
    injection = detect_injection(combined)
    language  = detect_language(issue_text)
    return pii, injection, language

def choose_domain(company: str, text: str) -> str:
    return COMPANY_DOMAINS.get(company) or infer_domain(text)

def merge_pii_flag(classifier_pii: bool, agent_pii: bool) -> bool:
    return classifier_pii or agent_pii

def sanitize_response_pii(response: str) -> str:
    if detect_pii(response):
        return mask_pii(response)
    return response

def dedupe_source_paths(retrieved: List[Tuple]) -> List[str]:
    seen = []
    for path, _, _ in retrieved:
        if path not in seen:
            seen.append(path)
    return seen

def citation_paths_from_retrieval(
    retrieved: List[Tuple],
    max_docs_sent: int = 5,
    max_sources: int = 4,
    domain: str = "unknown",
) -> List[str]:
    paths = dedupe_source_paths(retrieved[:max_docs_sent])
    if domain and domain != "unknown":
        domain_prefix = f"data/{domain}/"
        domain_paths = [p for p in paths if p.startswith(domain_prefix)]
        if domain_paths:
            paths = domain_paths
    return paths[:max_sources]

def validate_paths(paths: List[str], repo_root: str) -> List[str]:
    return [p for p in paths if os.path.exists(os.path.join(repo_root, p))]

def should_clear_sources(request_type: str) -> bool:
    return request_type == 'invalid'

def force_escalation_actions(
    issue_text: str, current_actions: list
) -> tuple:
    """Return (updated_actions, override_justification_or_None)."""
    triggers = {
        _LEGAL_RE:         ("high",    "legal",    "Legal threat detected — requires legal team review",
                            "Escalated: legal threat detected in ticket. Routing to legal team for review."),
        _IDENTITY_THEFT_RE:("urgent",  "security", "Identity theft/account takeover suspected",
                            "Escalated: identity theft or account takeover reported. Immediate security team review required."),
        _FRAUD_URGENT_RE:  ("high",    "security", "Urgent fraud/card compromise reported",
                            "Escalated: fraudulent transaction or card compromise reported. Requires security team intervention."),
    }
    already_escalating = any(a.get('action') == 'escalate_to_human' for a in current_actions)
    if already_escalating:
        return current_actions, None

    for pattern, (priority, dept, summary, justification) in triggers.items():
        if pattern.search(issue_text):
            return (
                current_actions + [{
                    "action": "escalate_to_human",
                    "parameters": {"priority": priority, "department": dept, "summary": summary},
                }],
                justification,
            )
    return current_actions, None

def _has_escalation_action(actions: list) -> bool:
    return any(a.get('action') == 'escalate_to_human' for a in actions)

def _default_escalation_action(result: dict) -> dict:
    risk = result.get('risk_level', 'medium')
    priority = 'urgent' if risk == 'critical' else 'high' if risk == 'high' else 'normal'
    product_area = result.get('product_area') or 'general support'
    return {
        "action": "escalate_to_human",
        "parameters": {
            "priority": priority,
            "department": "general",
            "summary": f"Human review required for {product_area}.",
        },
    }

def normalize_escalation_result(result: dict, override_justification: str | None = None) -> dict:
    if result.get('status') != 'escalated':
        return result

    if not _has_escalation_action(result.get('actions_taken', [])):
        result['actions_taken'] = result.get('actions_taken', []) + [_default_escalation_action(result)]

    result['risk_level'] = max_risk(result.get('risk_level', 'medium'), 'high')

    if override_justification:
        result['justification'] = override_justification
    return result

def _identity_in_context(issue_text: str) -> bool:
    return "verified" in issue_text.lower() or "identity confirmed" in issue_text.lower()

def _company_mismatch(company: str, product_area: str) -> bool:
    domain_map = {
        "DevPlatform": ["devplatform", "hackerrank", "screen", "interview", "test"],
        "Claude":      ["claude", "anthropic", "api", "console"],
        "Visa":        ["visa", "card", "payment", "transaction"],
    }
    if company not in domain_map:
        return False
    return not any(k in product_area.lower() for k in domain_map[company])

def max_risk(a: str, b: str) -> str:
    order = ["low", "medium", "high", "critical"]
    return order[max(order.index(a) if a in order else 1,
                     order.index(b) if b in order else 1)]

def process_ticket(
    issue_json: str,
    subject: str,
    company: str,
    corpus,
    tool_specs: list,
    repo_root: str,
) -> dict:
    issue_text = parse_issue_text(issue_json)

    pii_detected, injection_detected, language = classify_full_text(subject, issue_text)

    domain = choose_domain(company, f"{subject} {issue_text}")
    queries = build_queries(subject=subject, issue_text=issue_text)
    retrieved = corpus.search_multi(queries, k=7, domain_boost=domain)

    prompt = build_prompt(
        issue_text=issue_text,
        subject=subject,
        company=company,
        retrieved_docs=retrieved[:5],
        pii_detected=pii_detected,
        injection_detected=injection_detected,
        language=language,
    )

    result = call_openai(prompt)

    result['language'] = language
    result['pii_detected'] = merge_pii_flag(pii_detected, result.get('pii_detected', False))
    result['response'] = sanitize_response_pii(result['response'])

    if should_clear_sources(result.get('request_type', '')):
        result['source_documents'] = ''
    else:
        raw_paths   = citation_paths_from_retrieval(
            retrieved, max_docs_sent=5, max_sources=4, domain=domain
        )
        valid_paths = validate_paths(raw_paths, repo_root)
        result['source_documents'] = "|".join(valid_paths)

    identity_verified = _identity_in_context(issue_text)
    actions_valid, _ = validate_actions(
        result['actions_taken'], tool_specs, identity_verified=identity_verified
    )
    if not actions_valid:
        result['actions_taken'] = []

    result['actions_taken'], override_justification = force_escalation_actions(issue_text, result['actions_taken'])
    if any(a.get('action') == 'escalate_to_human' for a in result['actions_taken']):
        result['status'] = 'escalated'
    result = normalize_escalation_result(result, override_justification)

    if injection_detected:
        result['risk_level'] = max_risk(result.get('risk_level', 'medium'), 'medium')

    num_valid_sources = len(result['source_documents'].split('|')) if result['source_documents'] else 0
    retrieval_scores  = [r[2] for r in retrieved]
    result['confidence_score'] = compute_confidence(
        retrieval_scores=retrieval_scores,
        risk_level=result.get('risk_level', 'medium'),
        injection_detected=injection_detected,
        pii_detected=result['pii_detected'],
        actions_valid=actions_valid,
        num_sources=num_valid_sources,
        company_mismatch=_company_mismatch(company, result.get('product_area', '')),
    )

    return result
