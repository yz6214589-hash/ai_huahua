from __future__ import annotations

import json
import time
import traceback
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.deepagent_agent import run_agent as run_deep_agent
from llm.tools import list_tool_defs, run_tool
from workflow import run_trading_workflow
from infra.storage.job_store import AgentRunRecord, append_run, list_runs, now_iso
from infra.storage.logging_service import get_logger

logger = get_logger("ai")

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    input: str


class TradingWorkflowRequest(BaseModel):
    stock_code: str
    capital: float = 100000.0
    user_question: str = ""
    max_retry: int = 2


@router.get("/status")
def agent_status() -> dict[str, object]:
    logger.info("AI Agent status check", extra={})
    return {"status": "ready", "frameworks": ["deepagent", "trading-team"]}


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
        route = {"target": "deepagent", "reason": "deepagents"}
        run_id = uuid4().hex
        append_run(AgentRunRecord(run_id=run_id, input=req.input, route=route["target"], created_at=now_iso()))
        logger.info("AI Agent routed", extra={"run_id": run_id, "target": route["target"]})

        result = run_deep_agent(req.input, thread_id=run_id)
        logger.info("AI Agent done", extra={"run_id": run_id, "target": route["target"]})
        return {"run_id": run_id, "route": route, "result": result}
    except Exception as exc:
        logger.error("AI Agent failed", extra={"input": req.input[:100], "error": str(exc)})
        raise


@router.get("/runs")
def agent_runs() -> dict[str, object]:
    logger.info("AI Agent runs query", extra={})
    return {"runs": list_runs()}


@router.post("/stream")
def run_agent_stream(req: AgentRunRequest) -> StreamingResponse:
    logger.info("AI Agent stream start", extra={"input": req.input[:100]})
    run_id = uuid4().hex
    route = {"target": "deepagent", "reason": "deepagents"}
    append_run(AgentRunRecord(run_id=run_id, input=req.input, route=route["target"], created_at=now_iso()))

    def event_iter():
        try:
            yield "event: route\ndata: " + json.dumps({"route": route, "run_id": run_id}, ensure_ascii=False) + "\n\n"
            yield (
                "event: status\ndata: "
                + json.dumps({"status": "thinking", "message": "正在分析您的问题...", "run_id": run_id}, ensure_ascii=False)
                + "\n\n"
            )
            time.sleep(0.2)

            tools = agent_tools().get("items", [])
            yield "event: tools\ndata: " + json.dumps({"tools": tools, "run_id": run_id}, ensure_ascii=False) + "\n\n"

            result = run_deep_agent(req.input, thread_id=run_id)
            text = str((result or {}).get("text") or "")
            if text:
                yield "event: message\ndata: " + json.dumps(
                    {"message": {"role": "assistant", "content": text}, "run_id": run_id}, ensure_ascii=False
                ) + "\n\n"

            yield "event: status\ndata: " + json.dumps(
                {"status": "done", "message": "处理完成", "run_id": run_id}, ensure_ascii=False
            ) + "\n\n"
            yield "event: done\ndata: " + json.dumps(
                {"result": result, "run_id": run_id, "route": route}, ensure_ascii=False
            ) + "\n\n"

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


@router.post("/trading-workflow")
def run_trading_workflow_api(req: TradingWorkflowRequest) -> dict[str, object]:
    """运行交易团队工作流（Charles -> Zoe -> Kris -> Human -> Trader）"""
    logger.info("Trading workflow start", extra={"stock": req.stock_code, "capital": req.capital})
    try:
        result = run_trading_workflow(
            stock_code=req.stock_code,
            capital=req.capital,
            user_question=req.user_question,
            max_retry=req.max_retry,
        )
        logger.info("Trading workflow done", extra={"stock": req.stock_code})
        return {
            "workflow": "trading-team",
            "stock_code": req.stock_code,
            "result": result,
        }
    except Exception as exc:
        logger.error("Trading workflow failed", extra={"stock": req.stock_code, "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc))
