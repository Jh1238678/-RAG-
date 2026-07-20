"""分块服务单元测试。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.chunk_service import ChunkService, ChunkData
from app.parsers.base import PageInfo


def test_split_short_text():
    """短文本切成单块。"""
    service = ChunkService(chunk_size=512, overlap=50)
    chunks = service.split("这是一段简短的文本。")
    assert len(chunks) == 1
    assert "简短的文本" in chunks[0].content


def test_split_empty_text():
    """空文本返回空列表。"""
    service = ChunkService()
    assert service.split("") == []
    assert service.split("   ") == []


def test_split_multiple_paragraphs():
    """多段落文本切分。"""
    service = ChunkService(chunk_size=100, overlap=10)
    # 构造多段文本
    paragraphs = [f"这是第{i}段文本，内容足够长以触发分块。" for i in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = service.split(text)
    assert len(chunks) > 1
    # 每个 chunk 应有 chunk_index
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_split_preserves_page_num():
    """单页文档 chunk 应有 page_num。"""
    service = ChunkService(chunk_size=512, overlap=50)
    pages = [PageInfo(page_num=1, text="单页文档内容。")]
    chunks = service.split("单页文档内容。", pages=pages)
    assert len(chunks) >= 1
    assert chunks[0].page_num == 1


def test_chunk_data_metadata_default():
    """ChunkData 默认 metadata 为空 dict。"""
    cd = ChunkData(chunk_index=0, content="test")
    assert cd.metadata == {}
    assert cd.char_count == 4
    assert cd.token_count > 0
