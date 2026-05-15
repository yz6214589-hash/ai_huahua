from __future__ import annotations

import json
import time
import traceback
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aiagents.router_agent import route_intent
from ai.graphs.morning_brief_graph import build_graph
from ai.tools import list_tool_defs, run_tool
from runtime.job_store import AgentRunRecord, append_run, list_runs, now_iso
from runtime.logging_service import get_logger

logger = get_logger("ai")

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    input: str


@router.get("/status")
def agent_status() -> dict[str, object]:
    logger.info("AI Agent status check", extra={})
    return {"status": "ready", "frameworks": ["langgraph", "deepagent"]}


@router.get("/tools")
def agent_tools() -> dict[str, object]:
    logger.info("AI Agent tools query", extra={})
    return {"items": list_tool_defs()}


@router.post("/tools/{tool_name}/run")
def agent_run_tool(tool_name: str, body: dict[str, object]) -> dict[str, object]:
    logger.info("AI Agent tool execution", extra={"tool_name": tool_name, "params": body})
    try:
        result = run_tool(tool_name, dict(body))
        logger.info("AI Agent tool success", extra={"tool_name": tool_name})
    except KeyError:
        logger.warning("tool not found", extra={"tool_name": tool_name})
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}")
    except Exception as exc:
        logger.error("tool failed", extra={"tool_name": tool_name, "error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))
    return {"tool": tool_name, "result": result}


@router.post("/run")
def run_agent(req: AgentRunRequest) -> dict[str, object]:
    logger.info("AI Agent run start", extra={"input": req.input[:100]})
    try:
        route = route_intent(req.input)
        run_id = uuid4().hex
        append_run(AgentRunRecord(run_id=run_id, input=req.input, route=route["target"], created_at=now_iso()))
        logger.info("AI Agent routed", extra={"run_id": run_id, "target": route["target"]})

        if route["target"] == "graph:morning_brief":
            graph = build_graph()
            result = graph.invoke({"input": req.input})
            logger.info("AI Agent done", extra={"run_id": run_id, "target": route["target"]})
            return {"run_id": run_id, "route": route, "result": result}

        result = _run_sync(req.input, run_id, route)
        logger.info("AI Agent done", extra={"run_id": run_id, "target": route["target"]})
        return {"run_id": run_id, "route": route, "result": result}
    except Exception as exc:
        logger.error("AI Agent failed", extra={"input": req.input[:100], "error": str(exc)})
        raise


def _run_sync(user_input: str, run_id: str, route: dict) -> dict:
    from aiagents.quant_team_agent import run_quant_assistant

    return run_quant_assistant(user_input, run_id=run_id, route=route)


@router.get("/runs")
def agent_runs() -> dict[str, object]:
    logger.info("AI Agent runs query", extra={})
    return {"runs": list_runs()}


@router.post("/stream")
def run_agent_stream(req: AgentRunRequest) -> StreamingResponse:
    logger.info("AI Agent stream start", extra={"input": req.input[:100]})
    run_id = uuid4().hex
    route = route_intent(req.input)
    append_run(AgentRunRecord(run_id=run_id, input=req.input, route=route["target"], created_at=now_iso()))

    def event_iter():
        try:
            yield "event: route\ndata: " + json.dumps({"route": route, "run_id": run_id}, ensure_ascii=False) + "\n\n"

            if route["target"] == "graph:morning_brief":
                from langgraph.graph import END, START, StateGraph
                from services.ceo.morning_brief import normalize_params, run_morning_workflow

                def collect(s):
                    p = normalize_params(s)
                    return {
                        "industry_level": p.industry_level,
                        "top_n_industries": p.top_n_industries,
                        "top_n_stocks": p.top_n_stocks,
                        "lookback_days": p.lookback_days,
                        "sample_stocks": p.sample_stocks,
                        "messages": [],
                    }

                sg = StateGraph(dict)
                sg.add_node("collect", collect)
                sg.add_node("run", lambda s: run_morning_workflow(s))
                sg.add_edge(START, "collect")
                sg.add_edge("collect", "run")
                sg.add_edge("run", END)
                compiled = sg.compile()

                for chunk in compiled.stream({"input": req.input}, stream_mode="custom"):
                    node_name = list(chunk.keys())[0]
                    delta = chunk[node_name]
                    yield "event: node_start\ndata: " + json.dumps({"node": node_name, "run_id": run_id}, ensure_ascii=False) + "\n\n"
                    time.sleep(0.1)
                    if "messages" in delta:
                        for m in delta["messages"]:
                            yield "event: message\ndata: " + json.dumps({"message": m, "run_id": run_id}, ensure_ascii=False) + "\n\n"
                    if "report_html" in delta:
                        html = (delta["report_html"] or "")[:2000]
                        yield "event: report\ndata: " + json.dumps({"report_html": html}, ensure_ascii=False) + "\n\n"

                yield "event: done\ndata: " + json.dumps({"run_id": run_id}, ensure_ascii=False) + "\n\n"

            else:
                yield (
                    "event: status\ndata: "
                    + json.dumps(
                        {"status": "thinking", "message": "正在分析您的问题...", "run_id": run_id}, ensure_ascii=False
                    )
                    + "\n\n"
                )
                time.sleep(0.3)

                tools = list_tool_defs()
                yield "event: tools\ndata: " + json.dumps({"tools": tools, "run_id": run_id}, ensure_ascii=False) + "\n\n"

                try:
                    result = _run_sync(req.input, run_id, route)
                    yield "event: status\ndata: " + json.dumps(
                        {"status": "done", "message": "处理完成", "run_id": run_id}, ensure_ascii=False
                    ) + "\n\n"
                    yield "event: done\ndata: " + json.dumps(
                        {"result": result, "run_id": run_id, "route": route}, ensure_ascii=False
                    ) + "\n\n"
                except Exception as exc:
                    yield "event: error\ndata: " + json.dumps({"error": str(exc), "run_id": run_id}, ensure_ascii=False) + "\n\n"

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("stream exception", extra={"run_id": run_id, "error": str(exc), "trace": tb})
            yield "event: error\ndata: " + json.dumps({"error": str(exc), "run_id": run_id}, ensure_ascii=False) + "\n\n"

    logger.info("AI Agent stream done", extra={"run_id": run_id})
    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
