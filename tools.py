import os, logging, re, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from dotenv import load_dotenv

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from livekit.agents import function_tool

load_dotenv()  # ← must come before OpenAIEmbeddings

# — static AWS PDF index setup —
_here = os.path.dirname(__file__)
_STATIC_PDF = os.path.join(_here, "data", "knowledgeBaseVapi.pdf")
_static_loader = PyPDFLoader(_STATIC_PDF)
_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
_embeddings = OpenAIEmbeddings()
_static_docs = _static_loader.load()
_static_chunks = _splitter.split_documents(_static_docs)
_static_aws_index = FAISS.from_documents(_static_chunks, _embeddings)

_current_aws_index: Optional[FAISS] = None


@function_tool()
async def rebuild_aws_index(extra_pdfs: list[str] = None):
    docs = _static_loader.load()
    if extra_pdfs:
        for path in extra_pdfs:
            docs.extend(PyPDFLoader(path).load())
    chunks = _splitter.split_documents(docs)
    global _current_aws_index
    _current_aws_index = FAISS.from_documents(chunks, _embeddings)
    logging.info(f"Rebuilt AWS index with {len(chunks)} chunks")


@function_tool()
async def parse_prospect_info(report_path: str) -> dict:
    """Extract name, email, pain-point from a one-page prospect PDF."""
    pages = PyPDFLoader(report_path).load()
    text = "\n".join(p.page_content for p in pages)
    def find(pat):
        m = re.search(pat, text, re.IGNORECASE)
        return m.group(1).strip() if m else ""
    return {
        "name":  find(r"Name\s*[:\-]\s*(.+)"),
        "email": find(r"Email\s*[:\-]\s*([^\s,]+)"),
        "pain":  find(r"Pain\s*point\s*[:\-]\s*(.+)")
    }


@function_tool()
async def query_aws_guide(question: str) -> str:
    try:
        idx = _current_aws_index or _static_aws_index
        hits = idx.similarity_search(question, k=4)
        return "\n\n".join(h.page_content for h in hits)
    except Exception as e:
        logging.error(f"AWS query error: {e}")
        return "Sorry, I couldn’t find an answer in the AWS guide."


@function_tool()
async def search_web(query: str) -> str:
    try:
        return DuckDuckGoSearchRun().run(tool_input=query)
    except Exception as e:
        logging.error(f"Web search error: {e}")
        return f"Error searching web: {e}"


@function_tool()
async def send_email(
    to_email: str, subject: str, message: str, cc_email: Optional[str] = None
) -> str:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_pwd  = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_pwd:
        return "Email sending failed: credentials not configured."

    try:
        msg = MIMEMultipart()
        msg["From"]    = gmail_user
        msg["To"]      = to_email
        msg["Subject"] = subject
        if cc_email:
            msg["Cc"] = cc_email
        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(gmail_user, gmail_pwd)
        recipients = [to_email] + ([cc_email] if cc_email else [])
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()
        return f"Email sent to {to_email}"
    except Exception as e:
        logging.error(f"SMTP error: {e}")
        return f"Email error: {e}"
