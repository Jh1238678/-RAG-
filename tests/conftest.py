"""pytest 全局 fixtures。"""
import sys
import tempfile
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def tmp_data_dir():
    """创建临时数据目录，测试期间隔离。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        (tmp_path / "uploads").mkdir()
        (tmp_path / "processed").mkdir()
        (tmp_path / "faiss_index").mkdir()
        yield tmp_path
