"""鉴权预留模块。当前为占位实现，后续接入 JWT。"""
from fastapi import Depends, Header, Optional


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> dict:
    """获取当前用户。MVP 阶段返回默认用户。

    后续扩展：解析 Authorization header 中的 JWT，校验签名并返回用户信息。
    """
    return {"user_id": "default", "username": "guest"}


# 占位：用于后续接入鉴权时在路由上 Depends(get_current_user)
AuthDependency = Depends(get_current_user)
