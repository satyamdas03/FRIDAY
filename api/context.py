# api/context.py

import os
from pathlib import Path
from pymongo import MongoClient
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MONGO_URI    = os.getenv("MONGODB_URI")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY")
DEFAULT_DB   = os.getenv("MONGO_DB", "test")
OUT_PATH     = Path("data") / "temp_context.txt"

def get_db(db_name: str):
    if not MONGO_URI:
        raise RuntimeError("Please set MONGODB_URI in your environment")
    client = MongoClient(MONGO_URI)
    return client[db_name]

def fetch_html_report(db, lead_id: str) -> str:
    dr = db.deepresearches.find_one({"leadId": lead_id})
    if not dr:
        raise LookupError(f"No research found for leadId {lead_id!r}")
    return dr["htmlReport"]

def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n\n")

def call_openai(snippet: str) -> str:
    system = (
        "You are a concise extractor. "
        "Given a single prospect research report, pull out exactly three lines—no more, no repeats—"
        "in this format:\n\n"
        "Name: <full name>\n"
        "PainPoints: <their top challenges>\n"
        "Solutions: <what we can offer>\n\n"
        "Return exactly that, and nothing else."
    )
    client = OpenAI(api_key=OPENAI_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": snippet},
        ]
    )
    return resp.choices[0].message.content.strip()

def write_context(block: str):
    OUT_PATH.write_text(block + "\n", encoding="utf8")

def generate_context_for_lead(
    lead_id: str,
    db_name: str = DEFAULT_DB
) -> None:
    """
    1) Load HTML from Mongo
    2) Extract text
    3) Summarize into 3 lines via OpenAI
    4) Write data/temp_context.txt
    """
    db   = get_db(db_name)
    html = fetch_html_report(db, lead_id)
    plain = extract_text(html)[:20000]
    raw   = call_openai(plain)
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    block = "\n".join(lines[:3])
    write_context(block)
