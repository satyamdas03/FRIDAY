# api/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from tools import _query_aws, _search_web, _send_email, _make_call
from create_sip_dispatch_rule import create_sip_dispatch_rule

app = FastAPI(title="Friday Agent API")


class QueryRequest(BaseModel):
    question: str

@app.post("/aws/query")
async def aws_query(req: QueryRequest):
    try:
        answer = await _query_aws(req.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SearchRequest(BaseModel):
    query: str

@app.post("/search")
async def web_search(req: SearchRequest):
    try:
        results = await _search_web(req.query)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


class CallRequest(BaseModel):
    room: str
    phone: str

@app.post("/call")
async def dial(req: CallRequest):
    try:
        await _make_call(req.room, req.phone)
        return {"status": "dialing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
