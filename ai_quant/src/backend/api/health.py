"""
健康检查API模块
提供系统健康状态检查接口，用于监控应用运行状态
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
def health() -> dict[str, bool]:
    """
    健康检查端点
    
    返回系统健康状态，用于负载均衡器和监控系统检测应用是否正常运行
    
    Returns:
        dict: 包含ok字段，值为True表示健康
    """
    return {"ok": True}
