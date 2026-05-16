from __future__ import annotations

import json
import time
import traceback
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.deepagent_agent import run_agent as run_deep_agent
from agents.router_agent import route_intent
from llm.tools import list_tool_defs, run_tool
from workflow import run_trading_workflow
from workflow.morning_brief_graph import build_graph as build_morning_graph
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


_route_handlers: dict[str, str] = {
    "none": "无需处理",
    "graph:morning_brief": "晨会工作流",
    "tool:quant_assistant": "量化助手",
    "deepagent": "通用智能体",
}


@router.get("/status")
def agent_status() -> dict[str, object]:
    frameworks = ["deepagent", "trading-team", "morning-brief", "router"]
    logger.info("AI Agent 状态查询", extra={"frameworks": frameworks})
    return {"status": "ready", "frameworks": frameworks}


@router.get("/tools")
def agent_tools() -> dict[str, object]:
    logger.info("AI Agent 工具列表查询", extra={})
    tools = list_tool_defs()
    logger.info("AI Agent 工具列表查询完成", extra={"tool_count": len(tools)})
    return {"items": tools}


@router.post("/tools/{tool_name}/run")
def agent_run_tool(tool_name: str, body: dict[str, object]) -> dict[str, object]:
    logger.info("AI Agent 工具执行请求", extra={"tool_name": tool_name, "params_keys": list(body.keys())})
    try:
        result = run_tool(tool_name, dict(body))
        logger.info("AI Agent 工具执行成功", extra={
            "tool_name": tool_name,
            "result_type": type(result).__name__,
        })
    except KeyError:
        logger.warning("AI Agent 工具不存在", extra={"tool_name": tool_name})
        raise HTTPException(status_code=404, detail=f"tool not found: {tool_name}")
    except Exception as exc:
        logger.error("AI Agent 工具执行失败", extra={
            "tool_name": tool_name,
            "error": str(exc),
            "error_type": type(exc).__name__,
        })
        raise HTTPException(status_code=400, detail=str(exc))
    return {"tool": tool_name, "result": result}


@router.post("/run")
def run_agent(req: AgentRunRequest) -> dict[str, object]:
    input_text = str(req.input or "").strip()
    input_len = len(input_text)
    logger.info("AI Agent 运行请求开始", extra={
        "input_length": input_len,
        "input_preview": input_text[:100] if input_text else "(空)",
    })
    try:
        route = route_intent(input_text)
        route_target = route["target"]
        route_reason = route["reason"]
        handler_name = _route_handlers.get(route_target, "未知")
        logger.info("AI Agent 路由决策完成", extra={
            "target": route_target,
            "reason": route_reason,
            "handler": handler_name,
        })

        run_id = uuid4().hex
        logger.info("AI Agent 生成运行ID", extra={"run_id": run_id})

        append_run(AgentRunRecord(run_id=run_id, input=input_text, route=route_target, created_at=now_iso()))
        logger.info("AI Agent 运行记录已写入", extra={"run_id": run_id, "target": route_target})

        if route_target == "none":
            result_text = "请提出您的问题，例如：生成今日晨会简报、分析贵州茅台等。"
            logger.info("AI Agent 空输入处理完成，返回提示", extra={
                "run_id": run_id,
                "response_length": len(result_text),
            })
            return {
                "run_id": run_id,
                "route": route,
                "result": {"text": result_text},
            }

        if route_target == "graph:morning_brief":
            logger.info("AI Agent 开始执行晨会工作流", extra={"run_id": run_id})
            try:
                logger.debug("AI Agent 构建晨会工作流图", extra={"run_id": run_id})
                morning_graph = build_morning_graph()
                logger.info("AI Agent 晨会工作流图构建完成，开始执行", extra={"run_id": run_id})
                morning_result = morning_graph.invoke({"input": input_text})
                report_html_len = len(str(morning_result.get("report_html", "") or ""))
                report_md_len = len(str(morning_result.get("report_md", "") or ""))
                logger.info("AI Agent 晨会工作流执行完成", extra={
                    "run_id": run_id,
                    "has_report_html": bool(report_html_len),
                    "report_html_length": report_html_len,
                    "report_md_length": report_md_len,
                    "result_keys": list(morning_result.keys()) if isinstance(morning_result, dict) else [],
                })
                return {
                    "run_id": run_id,
                    "route": route,
                    "result": {"text": "晨会简报已生成", "morning_brief": morning_result},
                }
            except Exception as exc:
                logger.error("AI Agent 晨会工作流执行失败", extra={
                    "run_id": run_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                })
                err_msg = f"晨会简报生成失败：{str(exc)}"
                return {
                    "run_id": run_id,
                    "route": route,
                    "result": {"text": err_msg},
                }

        logger.info("AI Agent 开始执行通用智能体", extra={
            "run_id": run_id,
            "target_route": route_target,
        })
        result = run_deep_agent(input_text, thread_id=run_id)
        result_text = str((result or {}).get("text") or "")
        logger.info("AI Agent 通用智能体执行完成", extra={
            "run_id": run_id,
            "result_text_length": len(result_text),
            "result_text_preview": result_text[:100] if result_text else "(空)",
            "result_keys": list(result.keys()) if isinstance(result, dict) else [],
        })
        return {"run_id": run_id, "route": route, "result": result}
    except Exception as exc:
        logger.error("AI Agent 运行请求异常", extra={
            "input_preview": input_text[:100] if input_text else "(空)",
            "error": str(exc),
            "error_type": type(exc).__name__,
        })
        raise


@router.get("/runs")
def agent_runs() -> dict[str, object]:
    logger.info("AI Agent 运行记录列表查询", extra={})
    runs = list_runs()
    logger.info("AI Agent 运行记录列表查询完成", extra={"count": len(runs)})
    return {"runs": runs}


@router.post("/stream")
def run_agent_stream(req: AgentRunRequest) -> StreamingResponse:
    input_text = str(req.input or "").strip()
    logger.info("AI Agent 流式请求开始", extra={
        "input_length": len(input_text),
        "input_preview": input_text[:100] if input_text else "(空)",
    })
    run_id = uuid4().hex
    route = route_intent(input_text)
    route_target = route["target"]
    handler_name = _route_handlers.get(route_target, "未知")
    logger.info("AI Agent 流式路由决策完成", extra={
        "run_id": run_id,
        "target": route_target,
        "reason": route["reason"],
        "handler": handler_name,
    })
    append_run(AgentRunRecord(run_id=run_id, input=input_text, route=route_target, created_at=now_iso()))
    logger.info("AI Agent 流式运行记录已写入", extra={"run_id": run_id})

    def event_iter():
        try:
            logger.debug("AI Agent 流式输出 route 事件", extra={"run_id": run_id, "target": route_target})
            yield "event: route\ndata: " + json.dumps({"route": route, "run_id": run_id}, ensure_ascii=False) + "\n\n"
            yield (
                "event: status\ndata: "
                + json.dumps({"status": "thinking", "message": "正在分析您的问题...", "run_id": run_id}, ensure_ascii=False)
                + "\n\n"
            )
            time.sleep(0.2)

            routing_msg = f"路由到: {handler_name}"
            logger.debug("AI Agent 流式输出路由状态", extra={"run_id": run_id, "routing_message": routing_msg})
            yield "event: status\ndata: " + json.dumps(
                {"status": "routing", "message": routing_msg, "run_id": run_id},
                ensure_ascii=False,
            ) + "\n\n"

            if route_target == "none":
                prompt_text = "请提出您的问题，例如：生成今日晨会简报、分析贵州茅台等。"
                logger.info("AI Agent 流式空输入处理", extra={"run_id": run_id, "response_length": len(prompt_text)})
                yield "event: message\ndata: " + json.dumps(
                    {"message": {"role": "assistant", "content": prompt_text}, "run_id": run_id},
                    ensure_ascii=False,
                ) + "\n\n"

            elif route_target == "graph:morning_brief":
                logger.info("AI Agent 流式开始执行晨会工作流", extra={"run_id": run_id})
                yield "event: status\ndata: " + json.dumps(
                    {"status": "generating", "message": "正在生成晨会简报...", "run_id": run_id},
                    ensure_ascii=False,
                ) + "\n\n"
                try:
                    logger.debug("AI Agent 流式构建晨会工作流图", extra={"run_id": run_id})
                    morning_graph = build_morning_graph()
                    morning_result = morning_graph.invoke({"input": input_text})
                    report_html = str((morning_result or {}).get("report_html", "") or "")
                    logger.info("AI Agent 流式晨会工作流执行完成", extra={
                        "run_id": run_id,
                        "has_report_html": bool(report_html),
                        "report_html_length": len(report_html),
                    })
                    yield "event: message\ndata: " + json.dumps(
                        {"message": {"role": "assistant", "content": "晨会简报已生成"}, "run_id": run_id},
                        ensure_ascii=False,
                    ) + "\n\n"
                    if report_html:
                        logger.debug("AI Agent 流式输出晨会HTML报告", extra={
                            "run_id": run_id,
                            "html_length": len(report_html),
                        })
                        yield "event: report\ndata: " + json.dumps(
                            {"report_html": report_html, "run_id": run_id},
                            ensure_ascii=False,
                        ) + "\n\n"
                except Exception as exc:
                    logger.error("AI Agent 流式晨会工作流执行失败", extra={
                        "run_id": run_id,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    })
                    yield "event: error\ndata: " + json.dumps(
                        {"error": f"晨会简报生成失败: {str(exc)}", "run_id": run_id},
                        ensure_ascii=False,
                    ) + "\n\n"
            else:
                logger.info("AI Agent 流式开始执行通用智能体", extra={"run_id": run_id, "target": route_target})
                tools = agent_tools().get("items", [])
                logger.debug("AI Agent 流式输出工具列表", extra={
                    "run_id": run_id,
                    "tool_count": len(tools),
                })
                yield "event: tools\ndata: " + json.dumps({"tools": tools, "run_id": run_id}, ensure_ascii=False) + "\n\n"

                result = run_deep_agent(input_text, thread_id=run_id)
                text = str((result or {}).get("text") or "")
                logger.info("AI Agent 流式通用智能体执行完成", extra={
                    "run_id": run_id,
                    "result_text_length": len(text),
                    "result_text_preview": text[:100] if text else "(空)",
                })
                if text:
                    yield "event: message\ndata: " + json.dumps(
                        {"message": {"role": "assistant", "content": text}, "run_id": run_id}, ensure_ascii=False
                    ) + "\n\n"

            logger.debug("AI Agent 流式输出完成状态", extra={"run_id": run_id})
            yield "event: status\ndata: " + json.dumps(
                {"status": "done", "message": "处理完成", "run_id": run_id}, ensure_ascii=False
            ) + "\n\n"
            yield "event: done\ndata: " + json.dumps(
                {"result": {"text": "处理完成"}, "run_id": run_id, "route": route}, ensure_ascii=False
            ) + "\n\n"

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("AI Agent 流式处理异常", extra={
                "run_id": run_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "trace": tb,
            })
            yield "event: error\ndata: " + json.dumps({"error": str(exc), "run_id": run_id}, ensure_ascii=False) + "\n\n"

    logger.info("AI Agent 流式响应返回", extra={
        "run_id": run_id,
        "target": route_target,
    })
    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/trading-workflow")
def run_trading_workflow_api(req: TradingWorkflowRequest) -> dict[str, object]:
    """运行交易团队工作流（Charles -> Zoe -> Kris -> Human -> Trader）"""
    logger.info("交易工作流运行请求", extra={
        "stock_code": req.stock_code,
        "capital": req.capital,
        "user_question_length": len(req.user_question),
        "max_retry": req.max_retry,
    })
    try:
        logger.info("交易工作流开始执行", extra={"stock": req.stock_code})
        result = run_trading_workflow(
            stock_code=req.stock_code,
            capital=req.capital,
            user_question=req.user_question,
            max_retry=req.max_retry,
        )
        result_type = type(result).__name__
        result_keys = list(result.keys()) if isinstance(result, dict) else []
        logger.info("交易工作流执行完成", extra={
            "stock": req.stock_code,
            "result_type": result_type,
            "result_keys": result_keys,
        })
        return {
            "workflow": "trading-team",
            "stock_code": req.stock_code,
            "result": result,
        }
    except Exception as exc:
        logger.error("交易工作流执行失败", extra={
            "stock": req.stock_code,
            "error": str(exc),
            "error_type": type(exc).__name__,
        })
        raise HTTPException(status_code=500, detail=str(exc))
