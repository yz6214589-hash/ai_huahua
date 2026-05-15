"""
AI量化交易系统统一API入口模块
本模块负责初始化FastAPI应用、配置中间件、注册路由等核心功能
"""

from __future__ import annotations

import hashlib
import hmac
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

    def _get_real_client_ip(request: Request) -> str:
        """
        获取真实客户端IP地址
        
        安全地获取客户端 IP，优先从代理头获取，
        但会验证是否是可信代理（X-Forwarded-For, X-Real-IP）
        
        Args:
            request: HTTP请求对象
            
        Returns:
            str: 真实客户端 IP 地址
        """
        # 检查是否通过可信代理（仅当存在可信代理头时使用）
        # 只有当请求来自本地或已知代理时才信任这些头
        trusted_proxies = os.getenv("AI_QUANT_TRUSTED_PROXIES", "127.0.0.1,localhost").split(",")
        client_host = request.client.host if request.client else ""
        
        # 如果请求来自可信代理，尝试从代理头获取真实 IP
        if client_host in trusted_proxies:
            # X-Forwarded-For 可能包含多个 IP，第一个是真实客户端
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                # 取第一个 IP（最原始的客户端）
                real_ip = forwarded_for.split(",")[0].strip()
                if real_ip:
                    return real_ip
            
            # X-Real-IP 头
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
        
        # 回退到直接连接的客户端 IP
        return client_host or "unknown"

    def _verify_api_key(provided_key: str, stored_key_hash: str) -> bool:
        """
        安全验证 API 密钥
        
        支持两种模式：
        1. 密钥哈希验证（推荐）：环境变量存储密钥的 SHA256 哈希
        2. 直接比较（兼容）：环境变量存储原始密钥
        
        Args:
            provided_key: 请求提供的密钥
            stored_key_hash: 环境变量中存储的密钥或密钥哈希
            
        Returns:
            bool: 验证是否通过
        """
        if not provided_key or not stored_key_hash:
            return False
        
        # 如果存储的密钥以 "hash:" 前缀开头，使用哈希验证
        if stored_key_hash.startswith("hash:"):
            stored_hash = stored_key_hash[5:]  # 去掉 "hash:" 前缀
            provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
            return hmac.compare_digest(provided_hash, stored_hash)
        
        # 兼容模式：直接比较（不推荐用于生产环境）
        return hmac.compare_digest(provided_key, stored_key_hash)

    # 获取并验证 API 密钥配置
    raw_api_key = str(getattr(settings, "api_key", "") or "").strip()
    api_key_configured = bool(raw_api_key)
    # 缓存 API 密钥哈希用于常量时间比较
    _api_key_hash = raw_api_key if raw_api_key.startswith("hash:") else None

    @api.middleware("http")
    async def api_key_guard(request: Request, call_next):
        """
        HTTP中间件：速率限制和API密钥认证
        
        功能：
        1. 基于IP的速率限制，防止滥用API（使用安全 IP 检测）
        2. 验证API密钥，确保请求合法性（使用哈希验证）
        3. 设置缓存控制头，禁止浏览器缓存
        
        Args:
            request: HTTP请求对象
            call_next: 下一个处理器
            
        Returns:
            JSONResponse: 错误响应或正常响应
        """
        # 获取真实客户端IP地址（防止代理头伪造）
        ip = _get_real_client_ip(request)
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
        if api_key_configured and request.url.path.startswith("/api") and request.url.path not in ("/api/health",):
            req_key = str(request.headers.get("x-api-key") or "").strip()
            if not _verify_api_key(req_key, raw_api_key):
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
    api.include_router(data_router)          # 数据查询路由
    api.include_router(watchlist_router)     # 自选股路由
    api.include_router(stock_detail_router)   # 个股详情路由
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
    
    logger.info("业务路由注册完成", extra={
        "routers_count": 13,
        "routers": [
            "health", "summary", "data", "watchlist", "jobs",
            "reports", "analysis", "sentiment", "execution",
            "trading", "risk", "console", "agent"
        ]
    })

    @api.on_event("startup")
    def _jobs_scheduler_startup() -> None:
        logger.info("应用启动事件开始")
        try:
            from .api import jobs as _jobs_api

            _jobs_api.start_jobs_scheduler()
            logger.info("任务调度器启动成功")
        except Exception as e:
            logger.warning("任务调度器启动失败", extra={
                "error": str(e)
            })
        
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
