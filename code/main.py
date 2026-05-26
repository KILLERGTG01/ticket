#!/usr/bin/env python3
import csv, json, os, sys, time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent))

from corpus import Corpus
from pipeline import process_ticket
from tools import load_tool_specs

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

def main():
    print("Loading corpus...")
    corpus = Corpus(data_dir=str(DATA_DIR))
    print(f"Corpus: {corpus.num_chunks} chunks indexed.")
    tool_specs = load_tool_specs(str(TOOLS_PATH))

    with open(INPUT_CSV, encoding="utf-8") as f:
        tickets = list(csv.DictReader(f))
    print(f"Processing {len(tickets)} tickets...\n")

    results = []
    t0 = time.time()

    for i, ticket in enumerate(tickets, 1):
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
                repo_root=str(REPO_ROOT),
            )
        except Exception as e:
            print(f"  [ERROR] Ticket {i}: {e}")
            result = dict(FALLBACK_ROW)

        elapsed = time.time() - t0
        eta = (elapsed / i) * (len(tickets) - i)
        print(
            f"  [{i:3d}/{len(tickets)}] {company:12s} | "
            f"{result['status']:9s} | {result['risk_level']:8s} | "
            f"conf={result['confidence_score']:.2f} | ETA {eta:.0f}s"
        )

        row = {"issue": issue_json, "subject": subject, "company": company, **result}
        row["pii_detected"]  = str(row["pii_detected"]).lower()
        row["actions_taken"] = json.dumps(row["actions_taken"])
        results.append(row)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(results)

    total = time.time() - t0
    print(f"\nDone. {len(results)} rows → {OUTPUT_CSV}")
    print(f"Total: {total:.1f}s  ({total/len(tickets):.2f}s/ticket)")

if __name__ == "__main__":
    main()
