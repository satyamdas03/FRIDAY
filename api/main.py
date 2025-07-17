import os
import glob
import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient

from openai import OpenAI
from dotenv import load_dotenv

from tools import _query_aws, _search_web, _send_email, _make_call
from create_sip_dispatch_rule import create_sip_dispatch_rule
from api.context import generate_context_for_lead

# 🆕 New Import
from livekit.api.access_token import AccessToken, VideoGrants 
from livekit import api as livekit_api

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
    allow_origins=["*"],  # Update with actual frontend URL in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mongo client + collections
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME]
call_records = db.callRecords
leads_table = db.leads
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
    try:
        generate_context_for_lead(req.lead_id)
    except LookupError:
        raise HTTPException(404, "Do research bitch")
    except Exception as e:
        raise HTTPException(500, f"Context generation failed: {e}")

    try:
        await _make_call(req.room, req.phone)
    except Exception as e:
        raise HTTPException(500, str(e))

    call_records.insert_one({
        "leadId": req.lead_id,
        "room": req.room,
        "phone": req.phone,
        "createdAt": datetime.datetime.utcnow(),
    })

    leads_table.update_one(
        {"id": req.lead_id},
        {"$set": {"status": "called"}}
    )

    return {"status": "dialing"}

@app.post("/transcript", response_model=TranscriptResponse)
async def transcript(req: TranscriptRequest):
    rec = call_records.find_one(
        {"leadId": req.lead_id},
        sort=[("createdAt", -1)]
    )
    if not rec:
        raise HTTPException(404, "No call record found for that lead_id")

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

    sum_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Please summarize this call transcript in a few sentences:\n\n{raw_transcript}"}
        ]
    )
    summary = sum_resp.choices[0].message.content.strip()

    ins_resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"From the transcript below, list three actionable insights:\n\n{raw_transcript}"}
        ]
    )
    insights_raw = ins_resp.choices[0].message.content.strip()
    insights = [line.strip() for line in insights_raw.splitlines() if line.strip()]

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

# ─── 🆕 New LiveKit Token Route ────────────────────────────────────────────────
# @app.get("/get-livekit-token")
# async def get_livekit_token(identity: str = Query(...), room: str = Query(...)):
#     try:
#         api_key = os.getenv("LIVEKIT_API_KEY")
#         api_secret = os.getenv("LIVEKIT_API_SECRET")
#         if not api_key or not api_secret:
#             raise HTTPException(500, detail="Missing LiveKit API credentials.")

#         # Build token
#         token = (
#             AccessToken(api_key=api_key, api_secret=api_secret)
#             .with_identity(identity)
#             .with_name(identity)
#             .with_grants(VideoGrants(
#                 room_join=True,
#                 room=room,
#                 can_publish=True,
#                 can_subscribe=True,
#             ))
#         )
#         jwt = token.to_jwt()
#         return {"token": jwt}

#     except Exception as e:
#         print("🔴 LiveKit token error:", e)
#         raise HTTPException(500, detail=str(e))


@app.get("/get-livekit-token")
async def get_livekit_token(identity: str = Query(...), room: str = Query(...)):
    try:
        api_key = os.getenv("LIVEKIT_API_KEY")
        api_secret = os.getenv("LIVEKIT_API_SECRET")
        agent_name = os.getenv("AGENT_NAME", "inbound-agent")

        if not api_key or not api_secret:
            raise HTTPException(500, detail="LiveKit API credentials not set.")

        # 1. Create access token for browser user
        token = (
            AccessToken(api_key=api_key, api_secret=api_secret)
            .with_identity(identity)
            .with_name(identity)
            .with_grants(VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_subscribe=True
            ))
        )

        jwt = token.to_jwt()

        # 2. Dispatch the AI agent into the room
        lkapi = livekit_api.LiveKitAPI()
        await lkapi.agent_dispatch.create_dispatch(
            livekit_api.CreateAgentDispatchRequest(
                agent_name=agent_name,
                room=room,
                metadata=identity
            )
        )
        await lkapi.aclose()

        # 3. Return the token to the client
        return {"token": jwt}

    except Exception as e:
        print("🔴 Failed to issue token or dispatch agent:", e)
        raise HTTPException(500, detail=str(e))

