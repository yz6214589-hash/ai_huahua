import hashlib
import math
import os
import sqlite3
from typing import Any

import pytest

from services.reports import rag


class FakeEmbeddings:
    def _vec(self, text: str) -> list[float]:
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vals = []
        for i in range(0, 32, 4):
            n = int.from_bytes(h[i : i + 4], "big", signed=False)
            vals.append(((n % 10000) / 5000.0) - 1.0)
        s = math.sqrt(sum(x * x for x in vals)) or 1.0
        return [x / s for x in vals]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)

    def __call__(self, text: str) -> list[float]:
        return self.embed_query(text)


def _connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def test_rag_build_and_query_with_fake_embeddings(tmp_path, monkeypatch) -> None:
    pytest.importorskip("faiss")
    pdf_dir = tmp_path / "pdfs"
    db_path = tmp_path / "documents.db"
    index_dir = tmp_path / "vector_store"
    pdf_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("AI_QUANT_REPORT_RAG_PDF_DIR", str(pdf_dir))
    monkeypatch.setenv("AI_QUANT_REPORT_RAG_DB_PATH", str(db_path))
    monkeypatch.setenv("AI_QUANT_REPORT_INDEX_DIR", str(index_dir))

    _ = rag.rag_status()

    conn = _connect(str(db_path))
    try:
        doc_id = "doc1"
        now = "2026-01-01T00:00:00"
        conn.execute(
            """
            INSERT INTO documents(
              doc_id, filename, path, sha256, size_bytes, mtime_ns,
              title, stock_name, stock_code, source, report_type, publish_date,
              created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_id,
                "【研报】贵州茅台：深度研究.pdf",
                "/tmp/a.pdf",
                "x",
                1,
                1,
                "贵州茅台：深度研究",
                "贵州茅台",
                "600519",
                "测试券商",
                "深度研报",
                "2026-01-01",
                now,
                now,
            ),
        )
        conn.executemany(
            """
            INSERT INTO chunks(
              chunk_id, doc_id, page, chunk_index, content, content_sha256,
              stock_name, stock_code, title, source, report_type, publish_date,
              indexed, created_at
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "c1",
                    doc_id,
                    1,
                    0,
                    "贵州茅台 2025 年营收增长，现金流质量改善。",
                    "s1",
                    "贵州茅台",
                    "600519",
                    "贵州茅台：深度研究",
                    "测试券商",
                    "深度研报",
                    "2026-01-01",
                    0,
                    now,
                ),
                (
                    "c2",
                    doc_id,
                    2,
                    1,
                    "风险提示：需求波动与渠道库存变化。",
                    "s2",
                    "贵州茅台",
                    "600519",
                    "贵州茅台：深度研究",
                    "测试券商",
                    "深度研报",
                    "2026-01-01",
                    0,
                    now,
                ),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    built = rag.build_faiss_index(rebuild=True, embeddings=FakeEmbeddings())
    assert built.get("added") == 2
    assert (index_dir / "index.faiss").exists()
    assert (index_dir / "index.pkl").exists()

    r1 = rag.rag_query(q="营收", k=3, embeddings=FakeEmbeddings())
    items1 = r1.get("items") or []
    assert any("营收增长" in (it.get("content") or "") for it in items1)

    r2 = rag.rag_query(q="营收", stock="600519", k=3, embeddings=FakeEmbeddings())
    items2 = r2.get("items") or []
    assert any((it.get("meta") or {}).get("stock_code") == "600519" for it in items2)
