import json
from typing import List, Tuple

DESTRUCTIVE_ACTIONS = {"issue_refund", "lock_account", "modify_subscription"}


def load_tool_specs(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _type_ok(value, type_str: str) -> bool:
    if type_str == "string":
        return isinstance(value, str)
    if type_str == "number":
        return isinstance(value, (int, float))
    if type_str == "boolean":
        return isinstance(value, bool)
    return True


def validate_actions(
    actions: List[dict],
    specs: List[dict],
    identity_verified: bool = False,
) -> Tuple[bool, List[str]]:
    if not actions:
        return True, []

    spec_map = {s['name']: s for s in specs}
    errors = []
    has_verify = any(a.get('action') == 'verify_identity' for a in actions)

    for i, action in enumerate(actions):
        name = action.get('action', '')
        if name not in spec_map:
            errors.append(f"Action {i}: unknown action '{name}'")
            continue

        spec = spec_map[name]
        props = spec.get('parameters', {}).get('properties', {})
        required = spec.get('parameters', {}).get('required', [])
        params = action.get('parameters', {})

        for req in required:
            if req not in params:
                errors.append(f"Action {i} ({name}): missing required param '{req}'")

        for key in params:
            if key not in props:
                errors.append(f"Action {i} ({name}): extra param '{key}' not in schema")

        for key, val in params.items():
            if key in props:
                expected_type = props[key].get('type', '')
                if expected_type and not _type_ok(val, expected_type):
                    errors.append(
                        f"Action {i} ({name}): param '{key}' expected {expected_type},"
                        f" got {type(val).__name__}"
                    )

        if name in DESTRUCTIVE_ACTIONS and not identity_verified and not has_verify:
            errors.append(
                f"Action {i} ({name}): destructive action requires identity verification "
                f"(add verify_identity action or pass identity_verified=True)"
            )

    return len(errors) == 0, errors
