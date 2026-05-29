# Support Triage Agent

A terminal-based AI agent that classifies and responds to support tickets across three product ecosystems: **DevPlatform**, **Claude**, and **Visa**. Uses multi-query BM25 retrieval over a local corpus — no external knowledge base, no embeddings download.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for a full design walkthrough.

---

## Prerequisites

- Python 3.10+
- An OpenAI API key (`gpt-4.1-mini` by default)

---

## Setup

```bash
# Install dependencies
pip install uv
uv pip install -r code/requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=your_key
```

---

## Run

```bash
python3 code/main.py
```

Reads `support_tickets/support_tickets.csv`, writes predictions to `support_tickets/output.csv`.

Progress is printed per ticket as it completes:

```
[  1/ 89] Claude       | replied   | low      | conf=0.82 | ETA 42s
[  2/ 89] DevPlatform  | escalated | high     | conf=0.71 | ETA 39s
...
Done. 89 rows → support_tickets/output.csv
Total: 48.3s  (0.54s/ticket)
```

### Tuning parallelism

Set `MAX_WORKERS` in `.env` (default: `4`). Increase for higher OpenAI rate limits; drop to `2` if you hit per-minute throttling.

```bash
MAX_WORKERS=2 python3 code/main.py
```

---

## Validate output format

```bash
python3 code/validate_output.py
```

Checks structural correctness (column presence, allowed values). Does not score quality.

---

## Test

```bash
python3 -m pytest tests/ -v
```

71 tests, covering classifier patterns, confidence weights, escalation normalization, tool schema validation, query expansion, and domain inference. All pass in ~4s, no API calls required.

---

## Performance snapshot

Results below are from the current `support_tickets/output.csv` (89 tickets).

| Metric | Value |
|---|---|
| Tickets processed | 89 |
| Replied | 79 (88.8%) |
| Escalated | 10 (11.2%) |
| Escalated with `escalate_to_human` action | 10 / 10 (100%) |
| Average confidence | 0.821 |
| Average source docs cited per ticket | 2.92 |
| PII detected | 10 tickets |
| Non-English tickets detected | 9 (de, fr, es, af, ca, no, zh-cn) |

**Confidence distribution**

| Range | Count |
|---|---|
| < 0.50 | 3 |
| 0.50 – 0.70 | 5 |
| 0.70 – 0.88 | 28 |
| 0.88 (cap) | 53 |

**Escalation breakdown** (10 tickets)

| Department | Priority | Count |
|---|---|---|
| general | urgent | 5 |
| general | high | 3 |
| security | urgent | 1 |
| legal | high | 1 |

**Risk distribution**

| Level | Count |
|---|---|
| low | 48 |
| medium | 20 |
| high | 15 |
| critical | 6 |

Low-confidence tickets (< 0.50) are typically adversarial probes or out-of-scope requests with no matching corpus signal — expected behaviour.

---

## Configuration

| Variable | Required | Default | Notes |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | Used by the OpenAI SDK |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` | Any chat-completions model |
| `MAX_WORKERS` | No | `4` | Thread pool size |

All configuration via environment variables or `.env`. No hardcoded values.

---

## Output schema

`output.csv` contains 14 columns:

| Column | Type | Description |
|---|---|---|
| `issue` | string | Raw issue JSON from input |
| `subject` | string | Ticket subject |
| `company` | string | `Claude`, `DevPlatform`, `Visa`, or `None` |
| `response` | string | User-facing answer grounded in corpus |
| `product_area` | string | Most relevant support category |
| `status` | `replied` \| `escalated` | Routing decision |
| `request_type` | `product_issue` \| `feature_request` \| `bug` \| `invalid` | Classification |
| `justification` | string | Routing rationale |
| `confidence_score` | float [0.05, 0.88] | Deterministic retrieval-based score |
| `source_documents` | pipe-separated paths | Corpus files cited; empty for `invalid` |
| `risk_level` | `low` \| `medium` \| `high` \| `critical` | Risk assessment |
| `pii_detected` | bool | True if PII found in ticket |
| `language` | ISO 639-1 | Detected ticket language |
| `actions_taken` | JSON array | Tool actions taken (validated against schema) |
