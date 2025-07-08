# # GET API FOR FETCHING TRANSCRIPTS AND STUFF FROM DB
# # api/main.py

# import os
# import glob
# import datetime
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from openai import OpenAI
# from pymongo import MongoClient
# from dotenv import load_dotenv

# from tools import _query_aws, _search_web, _send_email, _make_call
# from create_sip_dispatch_rule import create_sip_dispatch_rule
# from api.context import generate_context_for_lead

# # ─── Load config ────────────────────────────────────────────────────────────────
# load_dotenv()
# OPENAI_KEY = os.getenv("OPENAI_API_KEY")
# if not OPENAI_KEY:
#     raise RuntimeError("Missing OPENAI_API_KEY in environment")

# MONGODB_URI = os.getenv("MONGODB_URI")
# if not MONGODB_URI:
#     raise RuntimeError("Missing MONGODB_URI in environment")
# MONGODB_DB = os.getenv("MONGODB_DB", "test")
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── MongoDB setup ──────────────────────────────────────────────────────────────
# client = MongoClient(MONGODB_URI)
# db = client[MONGODB_DB]
# call_records = db.callRecords
# leads_table   = db.leads
# # ────────────────────────────────────────────────────────────────────────────────

# app = FastAPI(title="Friday Agent API")

# # ─── CORS middleware ────────────────────────────────────────────────────────────
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],   # lock down in prod
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── AWS Query ─────────────────────────────────────────────────────────────────
# class QueryRequest(BaseModel):
#     question: str

# @app.post("/aws/query")
# async def aws_query(req: QueryRequest):
#     try:
#         answer = await _query_aws(req.question)
#         return {"answer": answer}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── Web Search ────────────────────────────────────────────────────────────────
# class SearchRequest(BaseModel):
#     query: str

# @app.post("/search")
# async def web_search(req: SearchRequest):
#     try:
#         results = await _search_web(req.query)
#         return {"results": results}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── Send Email ────────────────────────────────────────────────────────────────
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
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── Outbound Call ─────────────────────────────────────────────────────────────
# class CallRequest(BaseModel):
#     room: str
#     phone: str
#     lead_id: str

# @app.post("/call")
# async def dial(req: CallRequest):
#     # 1) regenerate context for this lead
#     try:
#         generate_context_for_lead(req.lead_id)
#     except LookupError:
#         raise HTTPException(status_code=404, detail="Do research bitch")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Context generation failed: {e}")

#     # 2) place the outbound call
#     try:
#         await _make_call(req.room, req.phone)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

#     # 3) record this call in MongoDB
#     call_records.insert_one({
#         "leadId":    req.lead_id,
#         "room":      req.room,
#         "phone":     req.phone,
#         "createdAt": datetime.datetime.utcnow()
#     })

#     # 4) mark the lead as called
#     leads_table.update_one(
#         {"id": req.lead_id},
#         {"$set": {"status": "called"}}
#     )

#     return {"status": "dialing"}
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── SIP Dispatch Rule ─────────────────────────────────────────────────────────
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
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── Transcript + Summary + Insights ───────────────────────────────────────────
# class TranscriptRequest(BaseModel):
#     room: str

# class TranscriptResponse(BaseModel):
#     transcript: str
#     summary: str
#     insights: list[str]

# @app.post("/transcript", response_model=TranscriptResponse)
# async def get_transcript(req: TranscriptRequest):
#     # locate the latest transcript file for this room
#     pattern = f"transcripts/{req.room}_*.txt"
#     files = glob.glob(pattern)
#     if not files:
#         raise HTTPException(status_code=404, detail="No transcript found for that room")
#     latest = max(files, key=os.path.getmtime)

#     # read transcript
#     try:
#         transcript = open(latest, encoding="utf8").read()
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to read transcript: {e}")

#     client = OpenAI(api_key=OPENAI_KEY)

#     # summary
#     sum_resp = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user",   "content": f"Summarize this call transcript:\n\n{transcript}"}
#         ]
#     )
#     summary = sum_resp.choices[0].message.content.strip()

#     # insights
#     ins_resp = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": "You are a helpful assistant."},
#             {"role": "user",   "content": f"From the transcript below, list three actionable insights:\n\n{transcript}"}
#         ]
#     )
#     raw_insights = ins_resp.choices[0].message.content.strip()
#     insights = [ln.strip() for ln in raw_insights.splitlines() if ln.strip()]

#     # update the call record
#     call_records.update_one(
#         {"room": req.room},
#         {"$set": {
#             "transcript":        transcript,
#             "summary":           summary,
#             "insights":          insights,
#             "transcriptSavedAt": datetime.datetime.utcnow()
#         }}
#     )

#     return {"transcript": transcript, "summary": summary, "insights": insights}
# # ────────────────────────────────────────────────────────────────────────────────

# # ─── NEW: GET call-record by lead_id ────────────────────────────────────────────
# class CallRecordResponse(BaseModel):
#     leadId: str
#     room: str
#     phone: str
#     createdAt: datetime.datetime
#     transcript: str | None = None
#     summary: str | None = None
#     insights: list[str] | None = None

# @app.get("/call/{lead_id}", response_model=CallRecordResponse)
# async def fetch_call_record(lead_id: str):
#     # find the latest call record for this lead
#     rec = call_records.find_one(
#         {"leadId": lead_id},
#         sort=[("createdAt", -1)]
#     )
#     if not rec:
#         raise HTTPException(status_code=404, detail="No call record found for that lead_id")

#     return CallRecordResponse(
#         leadId=rec["leadId"],
#         room=rec["room"],
#         phone=rec["phone"],
#         createdAt=rec["createdAt"],
#         transcript=rec.get("transcript"),
#         summary=rec.get("summary"),
#         insights=rec.get("insights", []),
#     )
# # ────────────────────────────────────────────────────────────────────────────────










# api/main.py

import os
import glob
import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

from openai import OpenAI
from dotenv import load_dotenv

from tools import _query_aws, _search_web, _send_email, _make_call
from create_sip_dispatch_rule import create_sip_dispatch_rule
from api.context import generate_context_for_lead

# ─── CONFIG ────────────────────────────────────────────────────────────────────
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in env")
MONGO_URI = os.getenv("MONGODB_URI")
if not MONGO_URI:
    raise RuntimeError("Missing MONGODB_URI in env")
DB_NAME = os.getenv("DB_NAME", "test")
# ────────────────────────────────────────────────────────────────────────────────

# ─── SETUP ─────────────────────────────────────────────────────────────────────
app = FastAPI(title="Friday Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # lock down in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mongo client + collections
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
call_records = db.callRecords
leads_table   = db.leads
# ────────────────────────────────────────────────────────────────────────────────

# ─── MODELS ────────────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str

class SearchRequest(BaseModel):
    query: str

class EmailRequest(BaseModel):
    to: str
    subject: str
    message: str
    cc: str | None = None

class CallRequest(BaseModel):
    room: str
    phone: str
    lead_id: str

class TranscriptRequest(BaseModel):
    lead_id: str

class TranscriptResponse(BaseModel):
    lead_id: str
    room: str
    phone: str
    createdAt: datetime.datetime
    transcript: str
    summary: str
    insights: list[str]
# ────────────────────────────────────────────────────────────────────────────────

# ─── ROUTES ────────────────────────────────────────────────────────────────────
@app.post("/aws/query")
async def aws_query(req: QueryRequest):
    try:
        return {"answer": await _query_aws(req.question)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/search")
async def web_search(req: SearchRequest):
    try:
        return {"results": await _search_web(req.query)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/email")
async def send_email(req: EmailRequest):
    try:
        return {"status": await _send_email(req.to, req.subject, req.message, req.cc)}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/sip/dispatch-rule")
async def sip_dispatch_rule(req: CallRequest):
    try:
        dispatch = await create_sip_dispatch_rule(req.trunk_ids, req.room_prefix, req.agent_name)
        return {"dispatch": dispatch}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/call")
async def dial(req: CallRequest):
    # 1) regenerate context or fail
    try:
        generate_context_for_lead(req.lead_id)
    except LookupError:
        raise HTTPException(404, "Do research bitch")
    except Exception as e:
        raise HTTPException(500, f"Context generation failed: {e}")

    # 2) dispatch AI agent and dial out
    try:
        await _make_call(req.room, req.phone)
    except Exception as e:
        raise HTTPException(500, str(e))

    # 3) record the call in Mongo
    call_records.insert_one({
        "leadId":    req.lead_id,
        "room":      req.room,
        "phone":     req.phone,
        "createdAt": datetime.datetime.utcnow(),
        # transcript/summary/insights to be filled later
    })

    # 4) update that lead's status to "called"
    leads_table.update_one(
        {"id": req.lead_id},
        {"$set": {"status": "called"}}
    )

    return {"status": "dialing"}


@app.post("/transcript", response_model=TranscriptResponse)
async def transcript(req: TranscriptRequest):
    # fetch the latest call record for this lead
    rec = call_records.find_one(
        {"leadId": req.lead_id},
        sort=[("createdAt", -1)]
    )
    if not rec:
        raise HTTPException(404, "No call record found for that lead_id")

    # if already summarized, return immediately
    if rec.get("transcript") and rec.get("summary") and rec.get("insights"):
        return TranscriptResponse(
            lead_id=rec["leadId"],
            room=rec["room"],
            phone=rec["phone"],
            createdAt=rec["createdAt"],
            transcript=rec["transcript"],
            summary=rec["summary"],
            insights=rec["insights"],
        )

    # else, load raw transcript file
    pattern = f"transcripts/{rec['room']}_*.txt"
    files = glob.glob(pattern)
    if not files:
        raise HTTPException(404, "Transcript file not found")
    latest_file = max(files, key=os.path.getmtime)
    try:
        raw_transcript = Path(latest_file).read_text(encoding="utf8")
    except Exception as e:
        raise HTTPException(500, f"Failed to read transcript file: {e}")

    client = OpenAI(api_key=OPENAI_KEY)

    # 1) summarize
    sum_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system","content":"You are a helpful assistant."},
            {"role":"user","content":f"Please summarize this call transcript in a few sentences:\n\n{raw_transcript}"}
        ]
    )
    summary = sum_resp.choices[0].message.content.strip()

    # 2) extract actionable insights
    ins_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role":"system","content":"You are a helpful assistant."},
            {"role":"user","content":f"From the transcript below, list three actionable insights:\n\n{raw_transcript}"}
        ]
    )
    insights_raw = ins_resp.choices[0].message.content.strip()
    insights = [line.strip() for line in insights_raw.splitlines() if line.strip()]

    # 3) persist back to Mongo
    call_records.update_one(
        {"_id": rec["_id"]},
        {"$set": {
            "transcript": raw_transcript,
            "summary": summary,
            "insights": insights
        }}
    )

    return TranscriptResponse(
        lead_id=rec["leadId"],
        room=rec["room"],
        phone=rec["phone"],
        createdAt=rec["createdAt"],
        transcript=raw_transcript,
        summary=summary,
        insights=insights,
    )
# ────────────────────────────────────────────────────────────────────────────────

