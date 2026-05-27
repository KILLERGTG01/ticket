#!/usr/bin/env python3
import csv, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from corpus import Corpus
from pipeline import process_ticket
from tools import load_tool_specs
from agent import _get_client

REPO_ROOT  = Path(__file__).parent.parent
INPUT_CSV  = REPO_ROOT / "support_tickets" / "support_tickets.csv"
OUTPUT_CSV = REPO_ROOT / "support_tickets" / "output.csv"
DATA_DIR   = REPO_ROOT / "data"
TOOLS_PATH = REPO_ROOT / "data" / "api_specs" / "internal_tools.json"

OUTPUT_COLUMNS = [
    "issue", "subject", "company",
    "response", "product_area", "status", "request_type", "justification",
    "confidence_score", "source_documents", "risk_level",
    "pii_detected", "language", "actions_taken",
]

FALLBACK_ROW = {
    "status": "escalated",
    "product_area": "unknown",
    "response": "This ticket could not be processed automatically and has been escalated for human review.",
    "justification": "Processing error — escalated as safe default.",
    "request_type": "product_issue",
    "confidence_score": 0.0,
    "source_documents": "",
    "risk_level": "high",
    "pii_detected": False,
    "language": "en",
    "actions_taken": [],
}

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))


def _process_one(idx: int, ticket: dict, corpus, tool_specs: list, repo_root: str):
    issue_json = ticket.get("Issue", ticket.get("issue", ""))
    subject    = ticket.get("Subject", ticket.get("subject", ""))
    company    = ticket.get("Company", ticket.get("company", "None"))

    try:
        result = process_ticket(
            issue_json=issue_json,
            subject=subject,
            company=company,
            corpus=corpus,
            tool_specs=tool_specs,
            repo_root=repo_root,
        )
    except Exception as e:
        print(f"  [ERROR] Ticket {idx + 1}: {e}")
        result = dict(FALLBACK_ROW)

    row = {"issue": issue_json, "subject": subject, "company": company, **result}
    row["pii_detected"]  = str(row["pii_detected"]).lower()
    row["actions_taken"] = json.dumps(row["actions_taken"])
    return idx, company, result["status"], result["risk_level"], result["confidence_score"], row


def main():
    print("Loading corpus...")
    corpus = Corpus(data_dir=str(DATA_DIR))
    print(f"Corpus: {corpus.num_chunks} chunks indexed.")
    tool_specs = load_tool_specs(str(TOOLS_PATH))
    _get_client()  # init before threads to avoid race on module global

    with open(INPUT_CSV, encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))
    n = len(tickets)
    print(f"Processing {n} tickets with {MAX_WORKERS} workers...\n")

    results   = [None] * n
    completed = 0
    lock      = Lock()
    t0        = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_process_one, i, tickets[i], corpus, tool_specs, str(REPO_ROOT)): i
            for i in range(n)
        }
        for future in as_completed(futures):
            idx, company, status, risk_level, conf, row = future.result()
            results[idx] = row
            with lock:
                completed += 1
                elapsed = time.time() - t0
                eta = (elapsed / completed) * (n - completed)
                print(
                    f"  [{completed:3d}/{n}] {company:12s} | "
                    f"{status:9s} | {risk_level:8s} | "
                    f"conf={conf:.2f} | ETA {eta:.0f}s"
                )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    total = time.time() - t0
    print(f"\nDone. {len(results)} rows → {OUTPUT_CSV}")
    print(f"Total: {total:.1f}s  ({total/n:.2f}s/ticket)")


if __name__ == "__main__":
    main()
