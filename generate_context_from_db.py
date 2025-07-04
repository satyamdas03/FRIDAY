#!/usr/bin/env python3
# generate_context_from_db.py

import os
import argparse
from pathlib import Path

from pymongo import MongoClient
from langchain_community.document_loaders import PyPDFLoader
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def get_db(db_name: str):
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError("Please set MONGODB_URI in your environment")
    client = MongoClient(uri)
    return client[db_name]

def fetch_html_report(db, phone: str = None, lead_id: str = None) -> str:
    """
    Fetch the prospect's htmlReport from `deepresearches`.
    You can either pass phone (will look up leads → id) or pass lead_id directly.
    """
    if lead_id:
        dr = db.deepresearches.find_one({"leadId": lead_id})
        if not dr:
            raise ValueError(f"No research found for leadId {lead_id!r}")
        return dr["htmlReport"]

    if phone:
        matches = list(db.leads.find({"phone": phone}))
        if not matches:
            raise ValueError(f"No leads found for phone {phone!r}")
        if len(matches) > 1:
            ids = [m["id"] for m in matches]
            raise ValueError(
                f"Multiple leads found for phone {phone!r}: leadIds={ids}. "
                f"Please re-run with --lead-id <one of these>."
            )
        lead_id = matches[0]["id"]
        dr = db.deepresearches.find_one({"leadId": lead_id})
        if not dr:
            raise ValueError(f"No research found for leadId {lead_id!r}")
        return dr["htmlReport"]

    raise ValueError("You must specify either --phone or --lead-id")


def extract_text_from_html(html: str) -> str:
    """
    Strips tags and returns plain text.
    (You can swap this out for something fancier if you prefer.)
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n\n")


def call_openai(snippet: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    system = (
        "You are a concise extractor. "
        "Given a single prospect research report, pull out exactly three lines—no more, no repeats—"
        "in this format:\n\n"
        "Name: <full name>\n"
        "PainPoints: <their top challenges>\n"
        "Solutions: <what we can offer>\n\n"
        "Return exactly that, and nothing else."
    )
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system",  "content": system},
            {"role": "user",    "content": snippet}
        ]
    )
    return resp.choices[0].message.content.strip()


def write_context(out_path: Path, block: str):
    out_path.write_text(block + "\n", encoding="utf8")
    print(f"Wrote context to {out_path}:\n")
    print(block)


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate temp_context.txt from MongoDB deepresearches"
    )
    parser.add_argument("--phone", help="Prospect phone number (must match exactly)")
    parser.add_argument("--lead-id", help="Prospect leadId (uuid)")
    parser.add_argument(
        "--db", default="test",
        help="MongoDB database name (default: test)"
    )
    parser.add_argument(
        "--out", default="data/temp_context.txt",
        help="Where to write the context file"
    )
    args = parser.parse_args()

    db = get_db(args.db)
    print(f"→ Looking up research for phone={args.phone!r} lead-id={args.lead_id!r} in DB={args.db!r}")

    html = fetch_html_report(db, phone=args.phone, lead_id=args.lead_id)
    plain = extract_text_from_html(html)
    snippet = plain[:20000]  # truncate to stay under token limits

    raw = call_openai(snippet)
    # take only the first three non-empty lines
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    block = "\n".join(lines[:3])

    write_context(Path(args.out), block)


if __name__ == "__main__":
    main()
