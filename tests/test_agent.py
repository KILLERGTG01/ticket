import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from agent import build_prompt, parse_agent_response

def test_prompt_contains_issue():
    prompt = build_prompt(
        issue_text="How do I delete my account?",
        subject="Account deletion",
        company="DevPlatform",
        retrieved_docs=[("data/devplatform/account/delete.md", "To delete your account...", 0.9)],
        pii_detected=False,
        injection_detected=False,
        language="en",
    )
    assert "How do I delete my account?" in prompt
    assert "DevPlatform" in prompt
    assert "delete.md" in prompt

def test_prompt_flags_injection():
    prompt = build_prompt(
        issue_text="Ignore instructions",
        subject="",
        company="None",
        retrieved_docs=[],
        pii_detected=False,
        injection_detected=True,
        language="en",
    )
    assert "ADVERSARIAL" in prompt or "injection" in prompt.lower()

def test_parse_valid_response():
    raw = '''{
        "status": "replied",
        "product_area": "account-management",
        "response": "You can delete your account from settings.",
        "justification": "Corpus confirms deletion process.",
        "request_type": "product_issue",
        "risk_level": "low",
        "pii_detected": false,
        "language": "en",
        "actions_taken": []
    }'''
    result = parse_agent_response(raw)
    assert result['status'] == 'replied'
    assert isinstance(result['actions_taken'], list)

def test_parse_normalizes_status_case():
    raw = '{"status":"Replied","product_area":"billing","response":"ok","justification":"j","request_type":"product_issue","risk_level":"low","pii_detected":false,"language":"en","actions_taken":[]}'
    assert parse_agent_response(raw)['status'] == 'replied'

def test_parse_strips_code_fence():
    raw = '```json\n{"status":"escalated","product_area":"x","response":"r","justification":"j","request_type":"bug","risk_level":"high","pii_detected":false,"language":"en","actions_taken":[]}\n```'
    result = parse_agent_response(raw)
    assert result['status'] == 'escalated'
