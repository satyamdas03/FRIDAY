# # api/main.py

# import os
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from tools import _query_aws, _search_web, _send_email, _make_call
# from create_sip_dispatch_rule import create_sip_dispatch_rule
# from api.context import generate_context_for_lead

# app = FastAPI(title="Friday Agent API")

# # ─── CORS middleware ────────────────────────────────────────────────────────────
# origins = ["*"]  # in prod, lock this down
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
# # ────────────────────────────────────────────────────────────────────────────────

# class QueryRequest(BaseModel):
#     question: str

# @app.post("/aws/query")
# async def aws_query(req: QueryRequest):
#     try:
#         answer = await _query_aws(req.question)
#         return {"answer": answer}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# class SearchRequest(BaseModel):
#     query: str

# @app.post("/search")
# async def web_search(req: SearchRequest):
#     try:
#         results = await _search_web(req.query)
#         return {"results": results}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# class EmailRequest(BaseModel):
#     to: str
#     subject: str
#     message: str
#     cc: str | None = None

# @app.post("/email")
# async def send_email(req: EmailRequest):
#     try:
#         status = await _send_email(req.to, req.subject, req.message, req.cc)
#         return {"status": status}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# class CallRequest(BaseModel):
#     room: str
#     phone: str
#     lead_id: str   # <-- must pass this now

# @app.post("/call")
# async def dial(req: CallRequest):
#     # Step 1: regenerate temp_context.txt or fail
#     try:
#         generate_context_for_lead(req.lead_id)
#     except LookupError:
#         # no research for that lead_id
#         raise HTTPException(status_code=404, detail="Do research bitch")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Context generation failed: {e}")

#     # Step 2: place the outbound call
#     try:
#         await _make_call(req.room, req.phone)
#         return {"status": "dialing"}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# class DispatchRuleRequest(BaseModel):
#     trunk_ids: list[str]
#     room_prefix: str
#     agent_name: str

# @app.post("/sip/dispatch-rule")
# async def sip_dispatch_rule(req: DispatchRuleRequest):
#     try:
#         dispatch = await create_sip_dispatch_rule(
#             req.trunk_ids,
#             req.room_prefix,
#             req.agent_name
#         )
#         return {"dispatch": dispatch}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

















# api/main.py

import os
import glob
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

from tools import _query_aws, _search_web, _send_email, _make_call
from create_sip_dispatch_rule import create_sip_dispatch_rule
from api.context import generate_context_for_lead

# ─── Load env & OpenAI key ─────────────────────────────────────────────────────
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in environment")
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Friday Agent API")

# ─── CORS middleware ────────────────────────────────────────────────────────────
origins = ["*"]  # lock down in prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ────────────────────────────────────────────────────────────────────────────────

# ─── AWS Query ─────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

@app.post("/aws/query")
async def aws_query(req: QueryRequest):
    try:
        answer = await _query_aws(req.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ────────────────────────────────────────────────────────────────────────────────

# ─── Web Search ────────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str

@app.post("/search")
async def web_search(req: SearchRequest):
    try:
        results = await _search_web(req.query)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ────────────────────────────────────────────────────────────────────────────────

# ─── Send Email ────────────────────────────────────────────────────────────────
class EmailRequest(BaseModel):
    to: str
    subject: str
    message: str
    cc: str | None = None

@app.post("/email")
async def send_email(req: EmailRequest):
    try:
        status = await _send_email(req.to, req.subject, req.message, req.cc)
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ────────────────────────────────────────────────────────────────────────────────

# ─── Outbound Call ─────────────────────────────────────────────────────────────
class CallRequest(BaseModel):
    room: str
    phone: str
    lead_id: str   # new

@app.post("/call")
async def dial(req: CallRequest):
    # Step 1: regenerate temp_context.txt
    try:
        generate_context_for_lead(req.lead_id)
    except LookupError:
        # no research for that lead_id
        raise HTTPException(status_code=404, detail="Do research bitch")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context generation failed: {e}")

    # Step 2: place the call
    try:
        await _make_call(req.room, req.phone)
        return {"status": "dialing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ────────────────────────────────────────────────────────────────────────────────

# ─── SIP Dispatch Rule ─────────────────────────────────────────────────────────
class DispatchRuleRequest(BaseModel):
    trunk_ids: list[str]
    room_prefix: str
    agent_name: str

@app.post("/sip/dispatch-rule")
async def sip_dispatch_rule(req: DispatchRuleRequest):
    try:
        dispatch = await create_sip_dispatch_rule(
            req.trunk_ids,
            req.room_prefix,
            req.agent_name
        )
        return {"dispatch": dispatch}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ────────────────────────────────────────────────────────────────────────────────

# ─── Transcript + Summary + Insights ───────────────────────────────────────────
class TranscriptRequest(BaseModel):
    room: str

class TranscriptResponse(BaseModel):
    transcript: str
    summary: str
    insights: list[str]

@app.post("/transcript", response_model=TranscriptResponse)
async def get_transcript(req: TranscriptRequest):
    # find latest transcript file for this room
    pattern = f"transcripts/{req.room}_*.txt"
    files = glob.glob(pattern)
    if not files:
        raise HTTPException(status_code=404, detail="No transcript found for that room")
    latest = max(files, key=os.path.getmtime)

    # read it
    try:
        transcript = open(latest, encoding="utf8").read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read transcript: {e}")

    client = OpenAI(api_key=OPENAI_KEY)

    # 1) Summarize
    sum_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Summarize this call transcript in a few sentences:\n\n{transcript}"}
        ]
    )
    summary = sum_resp.choices[0].message.content.strip()

    # 2) Extract actionable insights
    ins_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"From the transcript below, list three actionable insights:\n\n{transcript}"}
        ]
    )
    insights_raw = ins_resp.choices[0].message.content.strip()
    insights = [line.strip() for line in insights_raw.splitlines() if line.strip()]

    return {
        "transcript": transcript,
        "summary": summary,
        "insights": insights
    }
# ────────────────────────────────────────────────────────────────────────────────
