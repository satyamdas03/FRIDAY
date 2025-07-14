# #tools.py
# import os
# import json
# import logging
# import smtplib
# import psycopg2
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# from typing import Optional

# from dotenv import load_dotenv
# import boto3
# from langchain_community.tools import DuckDuckGoSearchRun
# from langchain_community.document_loaders import PyPDFLoader
# from langchain.text_splitter import CharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings
# from langchain_community.vectorstores import FAISS
# from langchain.schema import Document

# from livekit.agents import function_tool, RunContext
# from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
# from livekit.protocol.sip import CreateSIPParticipantRequest
# from livekit import api

# load_dotenv()

# # ─── CONFIG ────────────────────────────────────────────────────────────────────

# DATABASE_URL        = os.getenv("DATABASE_URL")
# AWS_REGION          = os.getenv("AWS_REGION", "us-east-1")
# AWS_ACCESS_KEY      = os.getenv("AWS_ACCESS_KEY")
# AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
# MODEL_ID_EMBED      = os.getenv("MODEL_ID_EMBED")
# MODEL_ID_CHAT       = os.getenv("MODEL_ID_CHAT")

# # Bedrock client for embeddings & chat
# bedrock = boto3.client(
#     "bedrock-runtime",
#     region_name=AWS_REGION,
#     aws_access_key_id=AWS_ACCESS_KEY,
#     aws_secret_access_key=AWS_SECRET_ACCESS_KEY
# )



# # ─── MULTIMODAL EMBEDDING TOOL ───────────────────────────────────────────────────
# def embed_text_or_image(content: str, content_type: str = "text", model_id: str | None = None) -> list[float]:
#     """
#     Embed either text or a base64-encoded image via Bedrock.
#     """
#     m = model_id or MODEL_ID_EMBED
#     if content_type == "text":
#         body = json.dumps({
#             "inputText": content,
#             "dimensions": 256,
#             "normalize": True
#         })
#     elif content_type == "image":
#         body = json.dumps({
#             "inputImage": content,
#             "dimensions": 256,
#             "normalize": True
#         })
#     else:
#         raise ValueError(f"Unsupported content_type={content_type}")

#     resp = bedrock.invoke_model(
#         modelId=m,
#         body=body,
#         contentType="application/json",
#         accept="application/json"
#     )
#     data = json.loads(resp["body"].read())
#     return data["embedding"]


# # ─── POSTGRES CONNECTOR ───────────────────────────────────────────────────────

# def get_db_connection():
#     conn = psycopg2.connect(DATABASE_URL)
#     return conn, conn.cursor()

# # ─── RAG INDEX IN MEMORY ──────────────────────────────────────────────────────

# rag_index: FAISS | None = None

# def reload_rag_index():
#     """Rebuild FAISS index from Postgres `embeddings` table."""
#     global rag_index
#     conn, cur = get_db_connection()
#     cur.execute("SELECT chunk_text FROM embeddings")
#     rows = cur.fetchall()
#     cur.close()
#     conn.close()

#     docs = [Document(page_content=row[0]) for row in rows]
#     embeddings = OpenAIEmbeddings()
#     rag_index = FAISS.from_documents(docs, embeddings)
#     logging.info(f"[tools] RAG index loaded with {len(docs)} docs")

# def _rag_search(question: str) -> str:
#     """Run similarity search against the live FAISS index."""
#     if rag_index is None:
#         reload_rag_index()
#     hits = rag_index.similarity_search(question, k=3)
#     return "\n\n".join(h.page_content for h in hits)

# # ─── STATIC AWS-PDF INDEX ─────────────────────────────────────────────────────

# _here = os.path.dirname(__file__)
# _pdf_path = os.path.join(_here, "data", "knowledgeBaseVapi.pdf")
# loader = PyPDFLoader(_pdf_path)
# docs = loader.load()
# splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
# chunks = splitter.split_documents(docs)
# aws_index = FAISS.from_documents(chunks, OpenAIEmbeddings())

# def _query_aws(question: str) -> str:
#     hits = aws_index.similarity_search(question, k=4)
#     return "\n\n".join(h.page_content for h in hits)

# # ─── WEB SEARCH TOOL ──────────────────────────────────────────────────────────

# def _search_web(query: str) -> str:
#     return DuckDuckGoSearchRun().run(tool_input=query)

# # ─── EMAIL SENDER TOOL ─────────────────────────────────────────────────────────

# def _send_email(
#     to_email: str,
#     subject: str,
#     message: str,
#     cc_email: Optional[str] = None
# ) -> str:
#     smtp_server, smtp_port = "smtp.gmail.com", 587
#     gmail_user = os.getenv("GMAIL_USER")
#     gmail_password = os.getenv("GMAIL_APP_PASSWORD")
#     if not gmail_user or not gmail_password:
#         logging.error("[tools] Gmail credentials missing")
#         return "Email sending failed: credentials not configured."
#     msg = MIMEMultipart()
#     msg["From"], msg["To"], msg["Subject"] = gmail_user, to_email, subject
#     recipients = [to_email]
#     if cc_email:
#         msg["Cc"] = cc_email
#         recipients.append(cc_email)
#     msg.attach(MIMEText(message, "plain"))
#     try:
#         server = smtplib.SMTP(smtp_server, smtp_port)
#         server.starttls()
#         server.login(gmail_user, gmail_password)
#         server.sendmail(gmail_user, recipients, msg.as_string())
#         server.quit()
#         return f"Email sent successfully to {to_email}"
#     except Exception as e:
#         logging.error(f"[tools] SMTP error: {e}")
#         return f"Email sending failed: {e}"

# # ─── LIVEKIT OUTBOUND CALL TOOL ──────────────────────────────────────────────

# async def _make_call(room_name: str, phone_number: str) -> None:
#     lkapi = api.LiveKitAPI()
#     await lkapi.agent_dispatch.create_dispatch(
#         CreateAgentDispatchRequest(
#             agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
#             room=room_name,
#             metadata=phone_number,
#         )
#     )
#     await lkapi.sip.create_sip_participant(
#         CreateSIPParticipantRequest(
#             room_name=room_name,
#             sip_trunk_id=os.getenv("SIP_OUTBOUND_TRUNK_ID"),
#             sip_number=os.getenv("SIP_CALLER_ID"),
#             sip_call_to=phone_number,
#             participant_identity=phone_number,
#             participant_name="Outbound Caller",
#             krisp_enabled=True,
#             wait_until_answered=True,
#             play_dialtone=True,
#         )
#     )
#     await lkapi.aclose()

# # ─── LIVEKIT FUNCTION-TOOLS ──────────────────────────────────────────────────

# @function_tool()
# async def query_aws_guide(ctx: RunContext, question: str) -> str:
#     return _query_aws(question)

# @function_tool()
# async def search_web(ctx: RunContext, query: str) -> str:
#     return _search_web(query)

# @function_tool()
# async def send_email(
#     ctx: RunContext,
#     to_email: str,
#     subject: str,
#     message: str,
#     cc_email: Optional[str] = None
# ) -> str:
#     return _send_email(to_email, subject, message, cc_email)

# @function_tool()
# async def make_call_tool(ctx: RunContext, room_name: str, phone_number: str) -> None:
#     await _make_call(room_name, phone_number)

# @function_tool()
# async def rag_query(ctx: RunContext, question: str) -> str:
#     return _rag_search(question)









# tools.py

import os
import json
import logging
import boto3
import psycopg2
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv
from langchain.schema import Document
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from livekit.agents import function_tool, RunContext
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
from livekit.protocol.sip import CreateSIPParticipantRequest
from livekit import api

load_dotenv()
logger = logging.getLogger("tools")
logger.setLevel(logging.INFO)

# ── CONFIG ────────────────────────────────────────────────────────────────
DATABASE_URL         = os.getenv("DATABASE_URL")
AWS_REGION           = os.getenv("AWS_REGION", "us-east-1")
AWS_ACCESS_KEY       = os.getenv("AWS_ACCESS_KEY")
AWS_SECRET_ACCESS_KEY= os.getenv("AWS_SECRET_ACCESS_KEY")
MODEL_ID_EMBED       = os.getenv("MODEL_ID_EMBED")
MODEL_ID_CHAT        = os.getenv("MODEL_ID_CHAT")

# Bedrock client
bedrock = boto3.client(
    "bedrock-runtime",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# ── POSTGRES CONNECTOR ─────────────────────────────────────────────────────
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn, conn.cursor()

# ── RAG INDEX IN MEMORY ────────────────────────────────────────────────────
rag_index: FAISS | None = None

def reload_rag_index():
    """Rebuild FAISS index from Postgres `embeddings` table."""
    global rag_index
    conn, cur = get_db_connection()
    cur.execute("SELECT chunk_text FROM embeddings")
    rows = cur.fetchall()
    cur.close(); conn.close()

    docs = [Document(page_content=r[0]) for r in rows]
    emb = OpenAIEmbeddings()
    rag_index = FAISS.from_documents(docs, emb)
    logger.info(f"[tools] RAG index loaded with {len(docs)} docs")

def _rag_search(question: str) -> str:
    """Run similarity search against the live FAISS index."""
    if rag_index is None:
        reload_rag_index()
    hits = rag_index.similarity_search(question, k=3)
    return "\n\n".join(h.page_content for h in hits)

# ── EMBEDDING HELPERS ──────────────────────────────────────────────────────
def embed_text_or_image(content: str, content_type: str = 'text', model_id: str = None):
    """Return a 256-dim embedding from Bedrock."""
    m = model_id or MODEL_ID_EMBED
    payload = {"inputText": content} if content_type == 'text' else {"inputImage": content}
    payload.update({"dimensions": 256, "normalize": True})
    resp = bedrock.invoke_model(
        modelId=m,
        body=json.dumps(payload),
        contentType="application/json",
        accept="application/json"
    )
    return json.loads(resp["body"].read())["embedding"]

# ── LIVEKIT FUNCTION-TOOLS ─────────────────────────────────────────────────
@function_tool()
async def query_aws_guide(ctx: RunContext, question: str) -> str:
    from langchain_community.tools import DuckDuckGoSearchRun
    return DuckDuckGoSearchRun().run(tool_input=question)

@function_tool()
async def search_web(ctx: RunContext, query: str) -> str:
    from langchain_community.tools import DuckDuckGoSearchRun
    return DuckDuckGoSearchRun().run(tool_input=query)

@function_tool()
async def send_email(
    ctx: RunContext,
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    smtp_server, smtp_port = "smtp.gmail.com", 587
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_password:
        logger.error("[tools] Gmail credentials missing")
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
        logger.error(f"[tools] SMTP error: {e}")
        return f"Email sending failed: {e}"

@function_tool()
async def make_call_tool(ctx: RunContext, room_name: str, phone_number: str) -> None:
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

@function_tool()
async def rag_query(ctx: RunContext, question: str) -> str:
    """
    1) retrieve top-k chunks from FAISS
    2) call Bedrock chat model with context + question
    """
    if rag_index is None:
        reload_rag_index()

    context = _rag_search(question)
    prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    body = {
        "schemaVersion": "messages-v1",
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "system": [{"text": "You are a helpful assistant. Use only the provided context."}],
        "inferenceConfig": {"maxTokens": 512, "temperature": 0.7}
    }
    resp = bedrock.invoke_model(
        modelId=MODEL_ID_CHAT,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json"
    )
    out = json.loads(resp["body"].read())
    return out["choices"][0]["message"]["content"]


