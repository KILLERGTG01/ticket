# Support Triage Agent

## Setup

```bash
pip install uv
uv pip install -r code/requirements.txt
cp .env.example .env
# Edit .env: OPENAI_API_KEY=your_key
```

## Run

```bash
python3 code/main.py
```

Output: `support_tickets/output.csv`

## Validate

```bash
python3 code/validate_output.py
```

## Test

```bash
python3 -m pytest tests/ -v
```

## Dependencies

All in `code/requirements.txt`. No GPU required.

| Variable | Required | Notes |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Used by the OpenAI SDK |
| `OPENAI_MODEL` | No | Defaults to `gpt-4.1-mini` |
