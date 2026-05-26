# Support Triage Agent

## Setup

```bash
pip install -r code/requirements.txt
cp .env.example .env
# Edit .env: GROQ_API_KEY=your_key  (free at console.groq.com)
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
| `GROQ_API_KEY` | Yes | Free tier at console.groq.com |
