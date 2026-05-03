from __future__ import annotations

import json
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ai_quant_api.ai.agents.quant_team_agent import run_quant_assistant
from ai_quant_api.ai.agents.router_agent import route_intent
from ai_quant_api.ai.graphs.morning_brief_graph import build_graph
from ai_quant_api.ai.tools import list_tool_defs, run_tool
from ai_quant_api.runtime.job_store import AgentRunRecord, append_run, list_runs, now_iso

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    input: str


@router.get("/status")
def agent_status() -> dict[str, object]:
    return {"status": "ready", "frameworks": ["langgraph", "deepagent"]}


@router.get("/tools")
def agent_tools() -> dict[str, object]:
    return {"items": list_tool_defs()}


@router.post("/tools/{tool_name}/run")
def agent_run_tool(tool_name: str, body: dict[str, object]) -> dict[str, object]:
    try:
        result = run_tool(tool_name, dict(body))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"tool": tool_name, "result": result}


@router.post("/run")
def run_agent(req: AgentRunRequest) -> dict[str, object]:
    route = route_intent(req.input)
    run_id = uuid4().hex
    append_run(
        AgentRunRecord(
            run_id=run_id,
            input=req.input,
            route=route["target"],
            created_at=now_iso(),
        )
    )
    if route["target"] == "graph:morning_brief":
        graph = build_graph()
        result = graph.invoke({"input": req.input})
        return {"run_id": run_id, "route": route, "result": result}

    result = run_quant_assistant(req.input)
    return {"run_id": run_id, "route": route, "result": result}


@router.get("/runs")
def agent_runs() -> dict[str, object]:
    return {"runs": list_runs()}


@router.post("/stream")
def run_agent_stream(req: AgentRunRequest) -> StreamingResponse:
    payload = run_agent(req)

    def event_iter():
        yield f"data: {json.dumps({'phase': 'start'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'phase': 'done'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_iter(), media_type="text/event-stream")
