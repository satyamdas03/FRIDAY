#!/usr/bin/env python3
# generate_context.py

import glob
import os
import argparse
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from langchain_community.document_loaders import PyPDFLoader

load_dotenv()

# Default glob for your prospect PDF(s)
PROSPECT_GLOB = "data/deep-research-report-*.pdf"
FALLBACK_GLOB = "data/*.pdf"
OUT_PATH = Path("data") / "temp_context.txt"

def find_pdf(explicit: str = None) -> Path:
    # 1) If user passed --pdf, use that
    if explicit:
        p = Path(explicit)
        if not p.exists():
            raise FileNotFoundError(f"Could not find PDF at {explicit}")
        return p

    # 2) Else look only for your prospect reports
    files = glob.glob(PROSPECT_GLOB)
    if files:
        latest = max(files, key=lambda f: os.path.getmtime(f))
        return Path(latest)

    # 3) Fallback to any PDF under data/
    files = glob.glob(FALLBACK_GLOB)
    if not files:
        raise FileNotFoundError(f"No PDFs matching {PROSPECT_GLOB} or {FALLBACK_GLOB}")
    return Path(max(files, key=lambda f: os.path.getmtime(f)))


def extract_text(pdf_path: Path) -> str:
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()
    # join page contents
    return "\n\n".join(d.page_content for d in docs)


def call_openai(snippet: str) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # system prompt insists on exactly one block
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pdf", "-p",
        help="(optional) path to your prospect PDF; otherwise finds data/deep-research-report-*.pdf"
    )
    args = parser.parse_args()

    pdf_path = find_pdf(args.pdf)
    print(f"→ Extracting from PDF: {pdf_path}")

    full_text = extract_text(pdf_path)
    snippet = full_text[:20000]  # keep under token limits

    raw = call_openai(snippet)

    # in case the model did slip in separators, just take the first three lines
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    first_block = "\n".join(lines[:3])

    OUT_PATH.write_text(first_block + "\n", encoding="utf8")
    print(f"Wrote context to {OUT_PATH}:\n")
    print(first_block)


if __name__ == "__main__":
    main()
