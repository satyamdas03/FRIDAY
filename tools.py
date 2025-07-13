# tools.py
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import requests
from langchain_community.tools import DuckDuckGoSearchRun
from livekit.agents import function_tool, RunContext
from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
from livekit.protocol.sip import CreateSIPParticipantRequest
from livekit import api

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

from dotenv import load_dotenv
load_dotenv()

# — initialize your AWS guide index once —
_here = os.path.dirname(__file__)
_pdf_path = os.path.join(_here, "data", "knowledgeBaseVapi.pdf")
loader = PyPDFLoader(_pdf_path)
docs = loader.load()
splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
chunks = splitter.split_documents(docs)
embeddings = OpenAIEmbeddings()
aws_index = FAISS.from_documents(chunks, embeddings)


# — core, context-free versions —

async def _query_aws(question: str) -> str:
    """Return top-4 relevant chunks from your AWS PDF."""
    hits = aws_index.similarity_search(question, k=4)
    return "\n\n".join(h.page_content for h in hits)


async def _search_web(query: str) -> str:
    """DuckDuckGo search via langchain_community."""
    return DuckDuckGoSearchRun().run(tool_input=query)


async def _send_email(
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    """Send an email through Gmail SMTP."""
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
    """
    Dial out via LiveKit’s SIP trunk:
    1) dispatch the AI agent into the room
    2) invite the PSTN callee
    """
    lkapi = api.LiveKitAPI()
    # 1) dispatch your agent
    await lkapi.agent_dispatch.create_dispatch(
        CreateAgentDispatchRequest(
            agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
            room=room_name,
            metadata=phone_number,
        )
    )
    # 2) dial out
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





















# ## fixing?
# # tools.py
# import logging
# import os
# import smtplib
# import threading
# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# from typing import Optional

# from langchain_community.tools import DuckDuckGoSearchRun
# from livekit.agents import function_tool, RunContext
# from livekit.protocol.agent_dispatch import CreateAgentDispatchRequest
# from livekit.protocol.sip import CreateSIPParticipantRequest
# from livekit import api

# from langchain_community.document_loaders import PyPDFLoader
# from langchain.text_splitter import CharacterTextSplitter
# from langchain_openai import OpenAIEmbeddings
# from langchain_community.vectorstores import FAISS

# from dotenv import load_dotenv

# load_dotenv()

# # ─── Lazy‐loaded AWS guide index ───────────────────────────────────────────────

# _aws_index: FAISS | None = None
# _aws_lock = threading.Lock()

# def get_aws_index() -> FAISS:
#     """
#     Build (once) and return the FAISS index over our AWS guide PDF.
#     This only runs on first call, avoiding embedding the entire doc at import time.
#     """
#     global _aws_index
#     if _aws_index is None:
#         with _aws_lock:
#             if _aws_index is None:
#                 here = os.path.dirname(__file__)
#                 pdf_path = os.path.join(here, "data", "knowledgeBaseVapi.pdf")
#                 loader = PyPDFLoader(pdf_path)
#                 docs = loader.load()
#                 splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
#                 chunks = splitter.split_documents(docs)
#                 embeddings = OpenAIEmbeddings()
#                 _aws_index = FAISS.from_documents(chunks, embeddings)
#     return _aws_index

# # ─── Core tool implementations ────────────────────────────────────────────────

# async def _query_aws(question: str) -> str:
#     """Return top-4 relevant chunks from your AWS PDF."""
#     index = get_aws_index()
#     hits = index.similarity_search(question, k=4)
#     return "\n\n".join(h.page_content for h in hits)

# async def _search_web(query: str) -> str:
#     """DuckDuckGo search via langchain_community."""
#     return DuckDuckGoSearchRun().run(tool_input=query)

# async def _send_email(
#     to_email: str,
#     subject: str,
#     message: str,
#     cc_email: Optional[str] = None
# ) -> str:
#     """Send an email through Gmail SMTP."""
#     smtp_server, smtp_port = "smtp.gmail.com", 587
#     gmail_user = os.getenv("GMAIL_USER")
#     gmail_password = os.getenv("GMAIL_APP_PASSWORD")
#     if not gmail_user or not gmail_password:
#         logging.error("Gmail credentials missing")
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
#         logging.error(f"SMTP error: {e}")
#         return f"Email sending failed: {str(e)}"

# async def _make_call(room_name: str, phone_number: str) -> None:
#     """
#     Dial out via LiveKit’s SIP trunk:
#     1) dispatch the AI agent into the room
#     2) invite the PSTN callee
#     """
#     lkapi = api.LiveKitAPI()
#     # 1) dispatch your agent
#     await lkapi.agent_dispatch.create_dispatch(
#         CreateAgentDispatchRequest(
#             agent_name=os.getenv("AGENT_NAME", "inbound-agent"),
#             room=room_name,
#             metadata=phone_number,
#         )
#     )
#     # 2) dial out
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

# # ─── LiveKit function‐tools ──────────────────────────────────────────────────

# @function_tool()
# async def query_aws_guide(ctx: RunContext, question: str) -> str:
#     return await _query_aws(question)

# @function_tool()
# async def search_web(ctx: RunContext, query: str) -> str:
#     return await _search_web(query)

# @function_tool()
# async def send_email(
#     ctx: RunContext,
#     to_email: str,
#     subject: str,
#     message: str,
#     cc_email: Optional[str] = None
# ) -> str:
#     return await _send_email(to_email, subject, message, cc_email)

# @function_tool()
# async def make_call_tool(ctx: RunContext, room_name: str, phone_number: str) -> None:
#     await _make_call(room_name, phone_number)
