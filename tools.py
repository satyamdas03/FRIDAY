# tools.py

import os
import json
import logging
import smtplib
import psycopg2
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

from livekit.agents import function_tool, RunContext
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
from livekit.protocol.sip import CreateSIPParticipantRequest
from livekit import api

# pull in your RAG helper functions & DB connector
from integrations.rag_app.main import (
    embed_text_or_image,
    bedrock,
    MODEL_ID_CHAT,
    get_db_connection,
)

from integrations.rag_app.main import DATABASE_URL  # or your conn helper

load_dotenv()

# — static AWS‐PDF index (unchanged) —
_here = os.path.dirname(__file__)
_pdf_path = os.path.join(_here, "data", "knowledgeBaseVapi.pdf")
loader = PyPDFLoader(_pdf_path)
docs = loader.load()
splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)
embeddings = OpenAIEmbeddings()
aws_index = FAISS.from_documents(chunks, embeddings)


# — live RAG index for uploads —
rag_index: FAISS | None = None

def reload_rag_index():
    """Rebuild the in-memory FAISS index from the Postgres embeddings table."""
    global rag_index

    # 1) pull all chunks from Postgres
    conn = psycopg2.connect(DATABASE_URL)
    cur  = conn.cursor()
    cur.execute("SELECT chunk_text FROM embeddings")
    docs = [Document(page_content=row[0]) for row in cur.fetchall()]
    cur.close()
    conn.close()

    # 2) rebuild FAISS
    embeddings = OpenAIEmbeddings()
    rag_index = FAISS.from_documents(docs, embeddings)
    logging.info(f"RAG index now has {len(docs)} documents")


async def _rag_search(question: str) -> str:
    """Query against the live FAISS RAG index."""
    global rag_index
    hits = rag_index.similarity_search(question, k=3)
    return "\n\n".join(h.page_content for h in hits)


# — core, context‐free versions of your old tools —


async def _query_aws(question: str) -> str:
    hits = aws_index.similarity_search(question, k=4)
    return "\n\n".join(h.page_content for h in hits)


async def _search_web(query: str) -> str:
    return DuckDuckGoSearchRun().run(tool_input=query)


async def _send_email(
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    smtp_server, smtp_port = "smtp.gmail.com", 587
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_password:
        logging.error("Gmail credentials missing")
        return "Email sending failed: credentials not configured."
    msg = MIMEMultipart()
    msg["From"], msg["To"], msg["Subject"] = gmail_user, to_email, subject
    recipients = [to_email]
    if cc_email:
        msg["Cc"] = cc_email
        recipients.append(cc_email)
    msg.attach(MIMEText(message, "plain"))
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, recipients, msg.as_string())
        server.quit()
        return f"Email sent successfully to {to_email}"
    except Exception as e:
        logging.error(f"SMTP error: {e}")
        return f"Email sending failed: {str(e)}"


async def _make_call(room_name: str, phone_number: str) -> None:
    lkapi = api.LiveKitAPI()
    await lkapi.agent_dispatch.create_dispatch(
        CreateAgentDispatchRequest(
            agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
            room=room_name,
            metadata=phone_number,
        )
    )
    await lkapi.sip.create_sip_participant(
        CreateSIPParticipantRequest(
            room_name=room_name,
            sip_trunk_id=os.getenv("SIP_OUTBOUND_TRUNK_ID"),
            sip_number=os.getenv("SIP_CALLER_ID"),
            sip_call_to=phone_number,
            participant_identity=phone_number,
            participant_name="Outbound Caller",
            krisp_enabled=True,
            wait_until_answered=True,
            play_dialtone=True,
        )
    )
    await lkapi.aclose()


# — LiveKit tool adapters —

@function_tool()
async def query_aws_guide(ctx: RunContext, question: str) -> str:
    return await _query_aws(question)


@function_tool()
async def search_web(ctx: RunContext, query: str) -> str:
    return await _search_web(query)


@function_tool()
async def send_email(
    ctx: RunContext,
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    return await _send_email(to_email, subject, message, cc_email)


@function_tool()
async def make_call_tool(ctx: RunContext, room_name: str, phone_number: str) -> None:
    await _make_call(room_name, phone_number)


@function_tool()
async def rag_query(ctx: RunContext, question: str) -> str:
    # 1) make sure the in-memory index is loaded
    if rag_index is None:
        reload_rag_index()

    # 2) fetch top-k chunks from FAISS
    context = await _rag_search(question)

    # 3) build your Bedrock chat payload
    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    body = {
        "schemaVersion":"messages-v1",
        "messages":[{"role":"user","content":[{"text":prompt}]}],
        "system":[{"text":"You are a helpful assistant. Use only the provided context."}],
        "inferenceConfig":{"maxTokens":512,"temperature":0.7}
    }

    # 4) call Bedrock and parse out the response
    resp = bedrock.invoke_model(
        modelId=MODEL_ID_CHAT,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )
    out = json.loads(resp["body"].read())
    return out["choices"][0]["message"]["content"]

