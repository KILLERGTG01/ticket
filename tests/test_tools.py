import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from tools import validate_actions, load_tool_specs

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
SPECS_PATH = os.path.join(REPO_ROOT, 'data', 'api_specs', 'internal_tools.json')

def specs():
    return load_tool_specs(SPECS_PATH)

def test_load_six_specs():
    s = specs()
    assert len(s) == 6
    assert {t['name'] for t in s} == {
        'issue_refund', 'reset_password', 'lock_account',
        'escalate_to_human', 'modify_subscription', 'verify_identity'
    }

def test_valid_reset_password():
    valid, errors = validate_actions(
        [{"action": "reset_password", "parameters": {"user_email": "t@x.com"}}],
        specs(), identity_verified=False
    )
    assert valid and errors == []

def test_unknown_action_rejected():
    valid, errors = validate_actions(
        [{"action": "send_email", "parameters": {}}], specs(), identity_verified=False
    )
    assert not valid
    assert any("unknown" in e for e in errors)

def test_missing_required_param():
    valid, errors = validate_actions(
        [{"action": "issue_refund", "parameters": {"amount": 50}}],
        specs(), identity_verified=True
    )
    assert not valid
    assert any("transaction_id" in e or "reason" in e for e in errors)

def test_extra_param_rejected():
    valid, errors = validate_actions(
        [{"action": "reset_password", "parameters": {"user_email": "t@x.com", "secret": "x"}}],
        specs(), identity_verified=False
    )
    assert not valid
    assert any("extra" in e.lower() or "secret" in e for e in errors)

def test_destructive_without_identity_rejected():
    valid, errors = validate_actions(
        [{"action": "issue_refund", "parameters": {"transaction_id": "txn_1", "amount": 50, "reason": "duplicate"}}],
        specs(), identity_verified=False
    )
    assert not valid
    assert any("identity" in e.lower() or "verify" in e.lower() for e in errors)

def test_destructive_with_verify_identity_allowed():
    actions = [
        {"action": "verify_identity", "parameters": {"method": "email_otp", "target": "t@x.com"}},
        {"action": "issue_refund", "parameters": {"transaction_id": "txn_1", "amount": 50, "reason": "duplicate"}},
    ]
    valid, errors = validate_actions(actions, specs(), identity_verified=False)
    assert valid

def test_destructive_with_pre_verified_allowed():
    valid, errors = validate_actions(
        [{"action": "issue_refund", "parameters": {"transaction_id": "txn_1", "amount": 50, "reason": "duplicate"}}],
        specs(), identity_verified=True
    )
    assert valid

def test_empty_actions_valid():
    valid, errors = validate_actions([], specs(), identity_verified=False)
    assert valid and errors == []
