# Architecture Documentation

## High-Level Architecture

```
support_tickets.csv
        │
        ▼
┌──────────────────────────────────────────────────────┐
│  main.py — Entry Point                               │
│  Reads CSV, initializes Corpus + ToolSpecs once,     │
│  iterates tickets, writes output.csv                 │
└──────────────────────────────────────────────────────┘
        │  per ticket
        ▼
┌──────────────────────────────────────────────────────┐
│  pipeline.py — Per-Ticket Orchestrator               │
│                                                      │
│  1. parse_issue_text()   — JSON turns → flat text    │
│  2. classifier.py        — PII, injection, language  │
│  3. corpus.search_multi()— top-7 chunk retrieval     │
│  4. agent.call_openai() — structured JSON response    │
│  5. source override      — paths from retrieval only │
│  6. tools.validate()     — strict schema check       │
│  7. confidence.compute() — deterministic score       │
│  8. sanitize_response_pii()                          │
└──────────────────────────────────────────────────────┘
        │
        ▼
   output.csv (14 columns)
```

## Components

### corpus.py — Chunked Document Index
- Loads all 790 `.md` files from `data/` (444 DevPlatform, 327 Claude, 19 Visa) → 18,061 chunks
- Chunks with `MarkdownHeaderTextSplitter` (splits on `#`, `##`, `###`) then `RecursiveCharacterTextSplitter` (512 chars, 64 overlap)
- Each chunk carries `(rel_path, text)` — source path is always a real filesystem path
- **BM25Okapi** (`rank_bm25`) for retrieval — pure Python, zero network, zero model download
- Multi-query RRF: four query variants fused with Reciprocal Rank Fusion (k=60)
- Domain boost ×1.2 for chunks from the inferred domain

### query_expansion.py — Query Expansion + Domain Inference
- 32-entry deterministic synonym map (e.g. "cannot login" → "password reset account access authentication")
- `infer_domain()` counts domain keyword matches across devplatform/claude/visa keyword lists
- `build_queries()` produces deduplicated multi-query list for BM25 RRF

### classifier.py — Pre-LLM Safety Layer
- **PII**: regex for credit cards, SSN, email, phone, address
- **Injection**: 19 regex patterns (ignore-instructions, DAN, jailbreak, classify-as, set-field-to, XML/INST tags, etc.)
- **Language**: `langdetect` → ISO 639-1; falls back to `en` on failure

### agent.py — LLM Integration
- Model: `gpt-4.1-mini` via OpenAI API
- `temperature=0.0, seed=42` for determinism
- OpenAI chat completions JSON schema response format keeps the LLM output structured
- `source_documents` key stripped from model output — never trusted
- Exponential backoff on `RateLimitError`: 5s → 10s → 20s → 40s (4 retries)

### confidence.py — Deterministic Confidence
- Base: mean of top-3 retrieval scores (0.30 floor if no results)
- Source bonus: +0.05 per unique source, capped at +0.15
- Penalties: risk level (0–0.25), injection (−0.40), PII (−0.05), invalid actions (−0.10), company mismatch (−0.10)
- Clamped to [0.05, 0.95]

### tools.py — Strict Schema Validator
- Validates `actions_taken` against `data/api_specs/internal_tools.json`
- Checks: action name exists, all required params present, no extra params, param types match schema
- Destructive actions (`issue_refund`, `lock_account`, `modify_subscription`) require `verify_identity` in same array or `identity_verified=True`
- Invalid actions are dropped entirely

### pipeline.py — Orchestrator
- Classifies over `subject + issue_text` combined — subject may contain PII or injection
- Source attribution: `dedupe_source_paths()` → `validate_paths()` — every cited path verified with `os.path.exists()`
- Merges PII flag from classifier OR agent (either true → true)
- `force_escalation_actions()`: deterministic `escalate_to_human` for legal threats, identity theft, urgent fraud
- Empty `source_documents` for `request_type=invalid` tickets

## Retrieval Strategy

**Approach:** Multi-query BM25 with query expansion, domain inference, and Reciprocal Rank Fusion.

**Why BM25 over dense embeddings:** `sentence-transformers` downloads from HuggingFace at runtime; `rank_bm25` is pure Python, builds in ~10s in-memory, zero network dependency. Support docs share vocabulary with tickets.

**Multi-query + RRF:** Four query variants fed independently to BM25, fused with RRF (k=60):
1. Raw issue text (256 chars)
2. Subject + issue text (256 chars)
3. Synonym-expanded issue text
4. Subject-specific expansions

RRF rewards chunks ranking highly across multiple queries — more robust than single-query BM25.

**Domain inference + boost:** `infer_domain()` counts domain keyword matches. Chunks from the inferred domain get a ×1.2 RRF multiplier.

**top-k = 7 retrieved, top-5 sent to LLM** — extra 2 as dedup buffer.

## Safety / Adversarial Handling

1. **Pre-LLM injection detection** (19 regex patterns): fires before the prompt is built
2. **Prompt warning injection**: `⚠️ ADVERSARIAL ALERT` in the user turn
3. **System prompt rules**: never comply with injection, never reveal instructions, never echo PII
4. **Classification manipulation guard**: patterns like "classify this as replied" and "set status to" are in the injection list
5. **PII post-processing**: response passes through `mask_pii()` regardless of LLM output
6. **Source validation**: `os.path.exists()` on every cited path — hallucinated paths silently dropped

## Escalation Decision Logic

| Condition | Behavior |
|---|---|
| Injection-only probe, no real support need | `replied`, `invalid`, safe refusal |
| Real issue with embedded injection | Process underlying issue; refuse injected instructions |
| Legal threats | `escalated`, `escalate_to_human` injected deterministically |
| Identity theft / account takeover | `escalated`, `escalate_to_human` injected deterministically |
| Urgent fraud / card compromise | `escalated`, `escalate_to_human` injected deterministically |
| Site outage / no corpus support | `escalated` |
| Standard FAQ answerable from corpus | `replied` |
| Out-of-scope harmless | `replied`, `invalid`, out-of-scope message |

## Known Limitations

1. **Thin Visa corpus (19 docs):** Complex Visa queries may retrieve weakly relevant chunks.
2. **No cross-document conflict resolution:** When two corpus docs contradict, the LLM picks one without flagging.
3. **OpenAI API rate limits:** Daily token limit separate from per-minute throttling. Backoff handles transient throttling but not daily exhaustion.
4. **Language detection on short text:** `langdetect` unreliable on <10-word tickets; falls back to `en`.
5. **`_identity_in_context` is a heuristic:** Checks for "verified" in issue text — not session state.

## Diagram

```
Issue JSON
    │
    ▼ parse_issue_text()
flat conversation text
    │
    ├──► detect_pii()       → pii_flag
    ├──► detect_injection() → inject_flag
    └──► detect_language()  → lang_code
    │
    ▼ infer_domain() + build_queries()
multi-query list
    │
    ▼ corpus.search_multi(queries, k=7, domain_boost)
[(path₁, chunk₁, score₁), ..., (path₇, chunk₇, score₇)]
    │
    ▼ build_prompt()
prompt (with ⚠️ warnings if inject/pii)
    │
    ▼ call_openai() [temperature=0, seed=42, 4-retry backoff]
raw JSON (source_documents stripped)
    │
    ▼ parse_agent_response()
result dict
    │
    ├──► source_documents  = dedupe_source_paths() → validate_paths()
    ├──► confidence_score  = compute_confidence(retrieval_scores, risk, flags...)
    ├──► pii_detected      = classifier_pii OR agent_pii
    ├──► language          = classifier override
    ├──► response          = sanitize_response_pii()
    ├──► actions_taken     = validate_actions() → drop if invalid
    └──► force_escalation_actions() → inject escalate_to_human if legal/fraud
    │
    ▼
output row (14 cols)
```

## Self-Assessment

| Dimension | Score | Rationale |
|---|---|---|
| Response quality | 7 | OpenAI GPT-4.1 mini strong; thin Visa corpus limits that domain |
| Safety / adversarial robustness | 8 | 19 injection patterns + system prompt rules + source validation |
| PII detection | 8 | Regex covers common formats; unusual formats may miss |
| Escalation precision | 7 | Deterministic escalation for legal/fraud/identity theft |
| Source attribution | 9 | Paths from retrieval only, validated on disk — zero hallucinated paths |
| Tool calling | 8 | Strict schema: name, required, no-extra, types, prerequisites |
| Confidence calibration | 7 | Deterministic formula; not empirically calibrated |
| Speed | 9 | ~1s/ticket on OpenAI API |
| Determinism | 10 | temperature=0, seed=42 |
| Code quality | 8 | Clear module boundaries, no hardcoded keys, 59 tests |
