"""
AI量化交易系统统一API入口模块
本模块负责初始化FastAPI应用、配置中间件、注册路由等核心功能
"""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime

try:
    from dotenv import find_dotenv, load_dotenv

    # 加载.env环境变量文件，支持从当前工作目录查找
    load_dotenv(find_dotenv(usecwd=True), override=False)
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 导入各个业务模块的路由处理器
from .api.agent import router as agent_router
from .api.conversation_api import router as conversation_router
from .api.analysis_zoe import router as analysis_router
from .api.console_ceo import router as console_router
from .api.data_charles import router as data_router
from .api.execution_ethan import router as execution_router
from .api.health import router as health_router
from .api.jobs import router as jobs_router
from .api.logs import router as logs_router
from .api.reports import router as reports_router
from .api.risk_kris import router as risk_router
from .api.sentiment import router as sentiment_router
from .api.summary import router as summary_router
from .api.trading_qmt import router as trading_router
from .api.watchlist import router as watchlist_router
from .api.stock_detail import router as stock_detail_router
from .api.data_status import router as data_status_router
from .api.stock_select import router as stock_select_router
from .api.signals import router as signals_router
from .api.sim_account import router as sim_account_router
from .api.mainforce import router as mainforce_router
from .api.approval import router as approval_router
from .api.performance import router as performance_router
from .api.stock_group import router as stock_group_router
from .api.intraday import router as intraday_router
from .api.workflow_team import router as workflow_team_router
from .config import get_settings, get_logging_settings
from .infra.storage.logging_service import init_logging, get_logger, shutdown_logging


def create_app() -> FastAPI:
    """
    创建并配置FastAPI应用实例
    
    该函数完成以下初始化工作：
    1. 初始化日志系统
    2. 加载应用配置
    3. 配置CORS跨域资源共享
    4. 设置速率限制中间件
    5. 配置API密钥认证中间件
    6. 注册所有业务路由
    
    Returns:
        FastAPI: 配置完成的FastAPI应用实例
    """
    init_logging()
    logger = get_logger("app")
    
    logger.info("应用创建开始", extra={
        "app_name": "AI Quant Unified API",
        "version": "0.1.0"
    })
    
    settings = get_settings()
    logger.info("应用配置加载完成", extra={
        "app_name": settings.app_name,
        "cors_origins": len(settings.cors_origins),
        "api_key_enabled": bool(settings.api_key)
    })
    
    api = FastAPI(title=settings.app_name, version="0.1.0")
    
    logger.info("FastAPI 应用实例创建完成")
    
    # 配置CORS中间件，允许跨域请求
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 配置速率限制参数，默认10秒内最多200次请求
    rl_window_s = 10.0
    rl_max = 200
    try:
        # 从环境变量读取速率限制时间窗口
        rl_window_s = float(str(os.getenv("AI_QUANT_RATE_LIMIT_WINDOW_SECONDS", "10")).strip() or "10")
    except Exception:
        rl_window_s = 10.0
    try:
        # 从环境变量读取速率限制最大请求数
        rl_max = int(str(os.getenv("AI_QUANT_RATE_LIMIT_MAX", "200")).strip() or "200")
    except Exception:
        rl_max = 200
    # 存储每个IP的请求记录：(请求窗口起始时间, 请求计数)
    rl_state: dict[str, tuple[float, int]] = {}

    async def cleanup_rate_limit_state():
        """定期清理过期的速率限制记录"""
        while True:
            try:
                now = time.monotonic()
                expire_threshold = rl_window_s * 3
                expired_ips = [
                    ip for ip, (start, _) in rl_state.items()
                    if now - start > expire_threshold
                ]
                for ip in expired_ips:
                    del rl_state[ip]
            except Exception:
                pass
            await asyncio.sleep(60)

    @api.middleware("http")
    async def api_key_guard(request: Request, call_next):
        """
        HTTP中间件：速率限制和API密钥认证
        
        功能：
        1. 基于IP的速率限制，防止滥用API
        2. 验证API密钥，确保请求合法性
        3. 设置缓存控制头，禁止浏览器缓存
        
        Args:
            request: HTTP请求对象
            call_next: 下一个处理器
            
        Returns:
            JSONResponse: 错误响应或正常响应
        """
        # 获取客户端IP地址
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        start, cnt = rl_state.get(ip, (now, 0))
        
        # 如果超过时间窗口，重置计数器
        if now - start > rl_window_s:
            start, cnt = now, 0
        cnt += 1
        rl_state[ip] = (start, cnt)
        
        # 检查是否超过速率限制
        if rl_max > 0 and cnt > rl_max:
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁"})

        # 验证API密钥（除了健康检查端点）
        key = str(getattr(settings, "api_key", "") or "").strip()
        if key and request.url.path.startswith("/api") and request.url.path not in ("/api/health",):
            req_key = str(request.headers.get("x-api-key") or "").strip()
            if req_key != key:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        
        # 执行后续处理并设置缓存控制头
        resp = await call_next(request)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Pragma"] = "no-cache"
        return resp

    http_logger = get_logger("http")

    @api.middleware("http")
    async def http_access_log(request: Request, call_next):
        """
        HTTP请求日志中间件

        功能：
        1. 记录所有HTTP请求的详细信息
        2. 记录请求方法、路径、参数
        3. 记录响应状态码和耗时
        4. 记录客户端IP地址

        Args:
            request: HTTP请求对象
            call_next: 下一个处理器

        Returns:
            Response: 正常响应或错误响应
        """
        start_time = time.monotonic()
        method = request.method
        path = request.url.path
        ip = request.client.host if request.client else "unknown"
        query_params = str(request.query_params) if request.query_params else ""

        try:
            response = await call_next(request)
            status_code = response.status_code
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if status_code >= 500:
                http_logger.error("HTTP 请求失败", extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "ip": ip,
                    "query_params": query_params
                })
            elif status_code >= 400:
                http_logger.warning("HTTP 请求错误", extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "ip": ip,
                    "query_params": query_params
                })
            else:
                http_logger.info("HTTP 请求成功", extra={
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "ip": ip
                })

            return response
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            http_logger.error("HTTP 请求异常", extra={
                "method": method,
                "path": path,
                "duration_ms": duration_ms,
                "ip": ip,
                "error": str(e)
            })
            raise

    @api.get("/")
    def root() -> dict[str, object]:
        """
        根路径处理器，返回API基本信息
        
        Returns:
            dict: 包含ok状态、文档链接和健康检查链接
        """
        return {"ok": True, "docs": "/docs", "health": "/api/health"}

    @api.get("/health")
    def health_alias() -> dict[str, bool]:
        """
        健康检查端点别名
        
        Returns:
            dict: 健康检查状态
        """
        return {"ok": True}

    # 注册所有业务路由
    api.include_router(health_router)       # 健康检查路由
    api.include_router(summary_router)       # 数据汇总路由
    api.include_router(data_status_router)   # 数据状态路由
    api.include_router(data_router)          # 数据查询路由
    api.include_router(watchlist_router)     # 自选股路由
    api.include_router(stock_detail_router)   # 个股详情路由
    api.include_router(stock_select_router)   # 选股路由
    api.include_router(jobs_router)           # 任务队列路由
    api.include_router(reports_router)        # 报告生成路由
    api.include_router(analysis_router)       # 技术分析路由
    api.include_router(sentiment_router)      # 舆情与宏观路由
    api.include_router(execution_router)      # 交易执行路由
    api.include_router(trading_router)        # QMT交易路由
    api.include_router(risk_router)           # 风险管理路由
    api.include_router(console_router)        # CEO控制台路由
    api.include_router(logs_router)           # 日志查询路由
    api.include_router(agent_router)          # AI智能体路由
    api.include_router(conversation_router)   # 对话会话路由
    api.include_router(signals_router)        # 信号中心路由
    api.include_router(sim_account_router)    # 模拟账户路由
    api.include_router(mainforce_router)      # 主力识别路由
    api.include_router(approval_router)       # 审批流程路由
    api.include_router(performance_router)    # 绩效报告路由
    api.include_router(stock_group_router)     # 股票分组管理路由
    api.include_router(intraday_router)         # 个股分时数据路由
    api.include_router(workflow_team_router)     # 工作流团队路由
    
    logger.info("业务路由注册完成", extra={
        "routers_count": 14,
        "routers": [
            "health", "summary", "data", "watchlist", "jobs",
            "reports", "analysis", "sentiment", "execution",
            "trading", "risk", "console", "agent", "intraday"
        ]
    })

    @api.on_event("startup")
    async def _jobs_scheduler_startup() -> None:
        logger.info("应用启动事件开始")
        try:
            from .api import jobs as _jobs_api

            _jobs_api.start_jobs_scheduler()
            logger.info("任务调度器启动成功")
        except Exception as e:
            logger.warning("任务调度器启动失败", extra={
                "error": str(e)
            })
        
        asyncio.create_task(cleanup_rate_limit_state())
        logger.info("速率限制状态清理任务已启动")
        
        logger.info("应用启动完成", extra={
            "status": "running",
            "api_version": "0.1.0"
        })

    @api.on_event("shutdown")
    def _jobs_scheduler_shutdown() -> None:
        logger.info("应用关闭事件开始")
        try:
            from .api import jobs as _jobs_api

            _jobs_api.stop_jobs_scheduler()
            logger.info("任务调度器关闭成功")
        except Exception as e:
            logger.warning("任务调度器关闭失败", extra={
                "error": str(e)
            })
        
        shutdown_logging()
        logger.info("应用关闭完成", extra={
            "status": "shutdown"
        })

    return api


# 创建应用实例供uvicorn等服务器使用
app = create_app()
