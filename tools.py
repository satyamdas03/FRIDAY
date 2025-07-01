# tools.py
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# --- Static AWS knowledge base setup ---
_here = os.path.dirname(__file__)
_STATIC_PDF = os.path.join(_here, "data", "knowledgeBaseVapi.pdf")
_static_loader = PyPDFLoader(_STATIC_PDF)
_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
_embeddings = OpenAIEmbeddings()
_static_docs = _static_loader.load()
_static_chunks = _splitter.split_documents(_static_docs)
_static_aws_index = FAISS.from_documents(_static_chunks, _embeddings)

# This will hold the merged static+dynamic index
_current_aws_index: Optional[FAISS] = None

async def rebuild_aws_index(extra_pdfs: list[str] = None):
    """
    Rebuild the FAISS index from the static AWS PDF plus any extra report PDFs.
    """
    docs = _static_loader.load()
    if extra_pdfs:
        for path in extra_pdfs:
            docs.extend(PyPDFLoader(path).load())
    chunks = _splitter.split_documents(docs)
    global _current_aws_index
    _current_aws_index = FAISS.from_documents(chunks, _embeddings)
    logging.info(f"Rebuilt AWS index with {len(chunks)} chunks")

async def parse_prospect_info(report_path: str) -> tuple[str, str, str]:
    """
    Extract prospect Name, Email, and Pain Point from a PDF report.
    Expects lines like "Name: ...", "Email: ...", "Pain point: ...".
    """
    pages = PyPDFLoader(report_path).load()
    text = "\n".join(p.page_content for p in pages)
    def _find(pattern):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
    name = _find(r"Name\s*[:\-]\s*(.+)")
    email = _find(r"Email\s*[:\-]\s*([^\s,]+)")
    pain = _find(r"Pain\s*point\s*[:\-]\s*(.+)")
    return name or "there", email or "", pain or ""

async def query_aws_guide(question: str) -> str:
    """
    Retrieve top‐4 relevant AWS chunks from the dynamic index or static fallback.
    """
    try:
        index = _current_aws_index or _static_aws_index
        hits = index.similarity_search(question, k=4)
        return "\n\n".join(h.page_content for h in hits)
    except Exception as e:
        logging.error(f"Error querying AWS knowledge base: {e}")
        return "Sorry, I couldn’t find an answer in the AWS knowledge base."

async def search_web(query: str) -> str:
    """
    Search the web using DuckDuckGo.
    """
    try:
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}'."

async def send_email(to_email: str, subject: str, message: str, cc_email: Optional[str] = None) -> str:
    """
    Send an email through Gmail.
    """
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pass:
        logging.error("Gmail credentials missing")
        return "Email sending failed: credentials not set."
    try:
        msg = MIMEMultipart()
        msg["From"] = gmail_user
        msg["To"]   = to_email
        msg["Subject"] = subject
        if cc_email:
            msg["Cc"] = cc_email
        msg.attach(MIMEText(message, "plain"))
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_pass)
        recipients = [to_email] + ([cc_email] if cc_email else [])
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()
        logging.info(f"Email sent to {to_email}")
        return f"Email sent successfully to {to_email}"
    except Exception as e:
        logging.error(f"SMTP error: {e}")
        return f"Email sending failed: {str(e)}"
