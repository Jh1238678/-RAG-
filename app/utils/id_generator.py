"""ID 生成工具。"""
import uuid


def gen_uuid() -> str:
    """生成 UUID（去掉横线，更紧凑）。"""
    return uuid.uuid4().hex
