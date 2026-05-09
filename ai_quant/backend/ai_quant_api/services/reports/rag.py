from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class RagSettings:
    pdf_dir: Path
    db_path: Path
    index_dir: Path
    chunk_size: int
    chunk_overlap: int
    top_k_default: int


def get_rag_settings() -> RagSettings:
    base = _project_root() / ".ai_quant" / "reports_rag"
    pdf_dir = Path(str(os.getenv("AI_QUANT_REPORT_RAG_PDF_DIR", "")).strip() or str(base / "pdfs"))
    db_path = Path(str(os.getenv("AI_QUANT_REPORT_RAG_DB_PATH", "")).strip() or str(base / "documents.db"))
    index_dir = Path(str(os.getenv("AI_QUANT_REPORT_INDEX_DIR", "")).strip() or str(base / "vector_store"))

    def _int(name: str, default: int) -> int:
        raw = str(os.getenv(name, "")).strip()
        try:
            return int(raw or default)
        except Exception:
            return default

    return RagSettings(
        pdf_dir=pdf_dir,
        db_path=db_path,
        index_dir=index_dir,
        chunk_size=max(200, min(_int("AI_QUANT_REPORT_RAG_CHUNK_SIZE", 900), 3000)),
        chunk_overlap=max(0, min(_int("AI_QUANT_REPORT_RAG_CHUNK_OVERLAP", 150), 800)),
        top_k_default=max(1, min(_int("AI_QUANT_REPORT_RAG_TOP_K", 6), 20)),
    )


def _connect_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
          doc_id TEXT PRIMARY KEY,
          filename TEXT NOT NULL,
          path TEXT NOT NULL,
          sha256 TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          mtime_ns INTEGER NOT NULL,
          title TEXT,
          stock_name TEXT,
          stock_code TEXT,
          source TEXT,
          report_type TEXT,
          publish_date TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
          chunk_id TEXT PRIMARY KEY,
          doc_id TEXT NOT NULL,
          page INTEGER,
          chunk_index INTEGER NOT NULL,
          content TEXT NOT NULL,
          content_sha256 TEXT NOT NULL,
          stock_name TEXT,
          stock_code TEXT,
          title TEXT,
          source TEXT,
          report_type TEXT,
          publish_date TEXT,
          indexed INTEGER NOT NULL DEFAULT 0,
          created_at TEXT NOT NULL,
          FOREIGN KEY(doc_id) REFERENCES documents(doc_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_indexed ON chunks(indexed)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_stock_code ON chunks(stock_code)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_stock_name ON chunks(stock_name)")
    conn.commit()


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


_REPORT_TYPE_PATTERNS: list[tuple[str, str]] = [
    (r"年度报告|年报", "年报"),
    (r"半年度报告|半年报", "半年报"),
    (r"第一季度报告|一季度报告|一季报", "一季报"),
    (r"第三季度报告|三季度报告|三季报", "三季报"),
    (r"季度报告|季报", "季报"),
    (r"业绩点评|业绩快报", "业绩点评"),
    (r"深度研究|深度报告|研究报告", "深度研报"),
    (r"调研纪要", "调研纪要"),
]


def _detect_report_type(title: str) -> str:
    t = str(title or "")
    for pattern, rtype in _REPORT_TYPE_PATTERNS:
        if re.search(pattern, t):
            return rtype
    return ""


def _extract_stock_code(text: str) -> str:
    search_text = str(text or "")[:15000]
    patterns = [
        r"(?:股票代码|证券代码|A\s*股.*?代码|代码)[：:\s]*(\d{6})",
        r"(?:Stock\s*Code)[：:\s]*(\d{6})",
        r"[（(](\d{6})[）)]",
    ]
    for pattern in patterns:
        m = re.search(pattern, search_text)
        if m:
            return m.group(1)
    return ""


def _extract_publish_date(text: str) -> str:
    search_text = str(text or "")[:15000]
    context_patterns = [
        r"(?:披露日期|公告日期|报告日期|发布日期|编制日期|批准报告日)[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(?:披露日期|公告日期|报告日期|发布日期|编制日期)[：:\s]*(\d{4})-(\d{1,2})-(\d{1,2})",
    ]
    for pattern in context_patterns:
        m = re.search(pattern, search_text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= year <= 2035 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def _parse_filename(filename: str) -> dict[str, str]:
    base = os.path.splitext(filename)[0]
    title = base
    stock_name = ""
    source = ""

    m = re.match(r"财报[_](.+?)[:：](.+)", base)
    if m:
        stock_name = m.group(1).strip()
        title = m.group(2).strip()
        source = "官方财报"
    else:
        m2 = re.match(r"【财报】(.+?)[:：](.+)", base)
        if m2:
            stock_name = m2.group(1).strip()
            title = m2.group(2).strip()
            source = "官方财报"
        else:
            m3 = re.match(r"【(.+?)】(.+)", base)
            if m3:
                source = m3.group(1).strip()
                title = m3.group(2).strip()

    report_type = _detect_report_type(title)
    if source and not report_type:
        report_type = "研报"

    return {
        "title": title,
        "stock_name": stock_name,
        "source": source,
        "report_type": report_type,
    }


def _extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    from PyPDF2 import PdfReader

    reader = PdfReader(str(pdf_path))
    pages: list[dict[str, Any]] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": page_num, "text": text})
    return pages


def _split_pages_to_docs(
    pages: list[dict[str, Any]],
    *,
    metadata: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", ".", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )

    out: list[Document] = []
    for p in pages:
        page_num = int(p.get("page") or 0) or None
        text = str(p.get("text") or "")
        if not text.strip():
            continue
        chunks = splitter.split_text(text)
        for idx, chunk in enumerate(chunks):
            meta = dict(metadata)
            meta["page"] = page_num
            meta["chunk_index_in_page"] = idx
            out.append(Document(page_content=chunk, metadata=meta))
    return out


def _upsert_document(
    conn: sqlite3.Connection,
    *,
    doc_id: str,
    pdf_path: Path,
    sha256: str,
    title: str,
    stock_name: str,
    stock_code: str,
    source: str,
    report_type: str,
    publish_date: str,
) -> None:
    now = _now_iso()
    st = pdf_path.stat()
    conn.execute(
        """
        INSERT INTO documents(
          doc_id, filename, path, sha256, size_bytes, mtime_ns,
          title, stock_name, stock_code, source, report_type, publish_date,
          created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
          sha256=excluded.sha256,
          size_bytes=excluded.size_bytes,
          mtime_ns=excluded.mtime_ns,
          title=excluded.title,
          stock_name=excluded.stock_name,
          stock_code=excluded.stock_code,
          source=excluded.source,
          report_type=excluded.report_type,
          publish_date=excluded.publish_date,
          updated_at=excluded.updated_at
        """,
        (
            doc_id,
            pdf_path.name,
            str(pdf_path),
            sha256,
            int(st.st_size),
            int(st.st_mtime_ns),
            title,
            stock_name,
            stock_code,
            source,
            report_type,
            publish_date,
            now,
            now,
        ),
    )


def _delete_document_chunks(conn: sqlite3.Connection, doc_id: str) -> None:
    conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))


def _insert_chunks(conn: sqlite3.Connection, doc_id: str, docs: list[Document]) -> int:
    now = _now_iso()
    rows: list[tuple[Any, ...]] = []
    for i, d in enumerate(docs):
        content = str(d.page_content or "")
        if not content.strip():
            continue
        chunk_id = hashlib.sha256(f"{doc_id}:{i}:{content}".encode("utf-8")).hexdigest()
        content_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        md = d.metadata or {}
        rows.append(
            (
                chunk_id,
                doc_id,
                int(md.get("page") or 0) or None,
                int(i),
                content,
                content_sha,
                str(md.get("stock_name") or ""),
                str(md.get("stock_code") or ""),
                str(md.get("title") or ""),
                str(md.get("source") or ""),
                str(md.get("report_type") or ""),
                str(md.get("publish_date") or ""),
                0,
                now,
            )
        )

    if not rows:
        return 0
    conn.executemany(
        """
        INSERT INTO chunks(
          chunk_id, doc_id, page, chunk_index, content, content_sha256,
          stock_name, stock_code, title, source, report_type, publish_date,
          indexed, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return len(rows)


def ingest_pdfs(*, rebuild: bool = False, limit: int | None = None) -> dict[str, Any]:
    s = get_rag_settings()
    s.pdf_dir.mkdir(parents=True, exist_ok=True)
    conn = _connect_db(s.db_path)
    try:
        _init_db(conn)
        pdfs = sorted([p for p in s.pdf_dir.glob("*.pdf") if p.is_file()], key=lambda x: x.name)
        if limit is not None:
            pdfs = pdfs[: max(0, int(limit))]

        processed = 0
        chunks_written = 0
        for pdf_path in pdfs:
            sha256 = _sha256_file(pdf_path)
            doc_id = sha256
            row = conn.execute("SELECT sha256 FROM documents WHERE doc_id=?", (doc_id,)).fetchone()
            if row and not rebuild:
                continue

            meta = _parse_filename(pdf_path.name)
            pages = _extract_pdf_pages(pdf_path)
            full_text = "\n".join([str(p.get("text") or "") for p in pages])
            stock_code = _extract_stock_code(full_text) or ""
            publish_date = _extract_publish_date(full_text) or ""

            title = meta.get("title") or pdf_path.stem
            stock_name = meta.get("stock_name") or ""
            source = meta.get("source") or ""
            report_type = meta.get("report_type") or ""

            _upsert_document(
                conn,
                doc_id=doc_id,
                pdf_path=pdf_path,
                sha256=sha256,
                title=title,
                stock_name=stock_name,
                stock_code=stock_code,
                source=source,
                report_type=report_type,
                publish_date=publish_date,
            )
            _delete_document_chunks(conn, doc_id)

            base_md = {
                "doc_id": doc_id,
                "filename": pdf_path.name,
                "title": title,
                "stock_name": stock_name,
                "stock_code": stock_code,
                "source": source,
                "report_type": report_type,
                "publish_date": publish_date,
            }

            docs = _split_pages_to_docs(
                pages,
                metadata=base_md,
                chunk_size=s.chunk_size,
                chunk_overlap=s.chunk_overlap,
            )
            chunks_written += _insert_chunks(conn, doc_id, docs)
            processed += 1

        conn.commit()
        total_docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        pending_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks WHERE indexed=0").fetchone()[0])

        return {
            "pdf_dir": str(s.pdf_dir),
            "db_path": str(s.db_path),
            "index_dir": str(s.index_dir),
            "processed_docs": processed,
            "chunks_written": chunks_written,
            "total_docs": total_docs,
            "total_chunks": total_chunks,
            "pending_chunks": pending_chunks,
        }
    finally:
        conn.close()


def _load_embeddings():
    from langchain_community.embeddings import DashScopeEmbeddings

    api_key = str(os.getenv("DASHSCOPE_API_KEY", "")).strip()
    if not api_key:
        raise RuntimeError("missing env: DASHSCOPE_API_KEY")
    return DashScopeEmbeddings(model="text-embedding-v4", dashscope_api_key=api_key)


def _iter_pending_chunks(conn: sqlite3.Connection, limit: int | None = None) -> Iterable[dict[str, Any]]:
    sql = """
        SELECT chunk_id, content, page, stock_name, stock_code, title, source, report_type, publish_date, doc_id
        FROM chunks
        WHERE indexed=0
        ORDER BY created_at ASC
    """
    if limit is None:
        cur = conn.execute(sql)
    else:
        cur = conn.execute(sql + " LIMIT ?", (int(limit),))
    cols = [d[0] for d in cur.description]
    for row in cur.fetchall():
        yield {cols[i]: row[i] for i in range(len(cols))}


def build_faiss_index(*, rebuild: bool = False, embeddings: Any | None = None, batch: int = 128) -> dict[str, Any]:
    s = get_rag_settings()
    conn = _connect_db(s.db_path)
    try:
        _init_db(conn)
        s.index_dir.mkdir(parents=True, exist_ok=True)

        if embeddings is None:
            embeddings = _load_embeddings()

        from langchain_community.vectorstores import FAISS

        vectorstore: FAISS | None = None
        if not rebuild:
            idx_f = s.index_dir / "index.faiss"
            idx_p = s.index_dir / "index.pkl"
            if idx_f.exists() and idx_p.exists():
                vectorstore = FAISS.load_local(str(s.index_dir), embeddings, allow_dangerous_deserialization=True)

        if rebuild or vectorstore is None:
            conn.execute("UPDATE chunks SET indexed=0")
            conn.commit()
            vectorstore = None

        docs_buffer: list[Document] = []
        chunk_ids: list[str] = []
        added = 0

        def flush() -> None:
            nonlocal vectorstore, added, docs_buffer, chunk_ids
            if not docs_buffer:
                return
            if vectorstore is None:
                vectorstore = FAISS.from_documents(docs_buffer, embeddings)
            else:
                vectorstore.add_documents(docs_buffer)
            conn.executemany("UPDATE chunks SET indexed=1 WHERE chunk_id=?", [(cid,) for cid in chunk_ids])
            conn.commit()
            added += len(docs_buffer)
            docs_buffer = []
            chunk_ids = []

        for r in _iter_pending_chunks(conn):
            content = str(r.get("content") or "")
            if not content.strip():
                conn.execute("UPDATE chunks SET indexed=1 WHERE chunk_id=?", (str(r.get("chunk_id") or ""),))
                continue
            md = {
                "doc_id": str(r.get("doc_id") or ""),
                "chunk_id": str(r.get("chunk_id") or ""),
                "page": int(r.get("page") or 0) or None,
                "stock_name": str(r.get("stock_name") or ""),
                "stock_code": str(r.get("stock_code") or ""),
                "title": str(r.get("title") or ""),
                "source": str(r.get("source") or ""),
                "report_type": str(r.get("report_type") or ""),
                "publish_date": str(r.get("publish_date") or ""),
            }
            docs_buffer.append(Document(page_content=content, metadata=md))
            chunk_ids.append(str(r.get("chunk_id") or ""))
            if len(docs_buffer) >= int(batch):
                flush()
        flush()

        if vectorstore is None:
            return {
                "index_dir": str(s.index_dir),
                "db_path": str(s.db_path),
                "added": 0,
                "total_chunks": 0,
            }

        vectorstore.save_local(str(s.index_dir))
        page_info: dict[str, int] = {}
        cur = conn.execute("SELECT content, page FROM chunks WHERE indexed=1")
        for content, page in cur.fetchall():
            try:
                k = str(content or "").strip()
                if not k:
                    continue
                page_info[k] = int(page or -1)
            except Exception:
                continue
        import pickle

        with (s.index_dir / "page_info.pkl").open("wb") as f:
            pickle.dump(page_info, f)

        total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        pending_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks WHERE indexed=0").fetchone()[0])
        return {
            "index_dir": str(s.index_dir),
            "db_path": str(s.db_path),
            "added": int(added),
            "total_chunks": total_chunks,
            "pending_chunks": pending_chunks,
        }
    finally:
        conn.close()


def rag_status() -> dict[str, Any]:
    s = get_rag_settings()
    conn = _connect_db(s.db_path)
    try:
        _init_db(conn)
        total_docs = int(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        total_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0])
        pending_chunks = int(conn.execute("SELECT COUNT(*) FROM chunks WHERE indexed=0").fetchone()[0])
        idx_f = s.index_dir / "index.faiss"
        idx_p = s.index_dir / "index.pkl"
        return {
            "pdf_dir": str(s.pdf_dir),
            "db_path": str(s.db_path),
            "index_dir": str(s.index_dir),
            "docs": total_docs,
            "chunks": total_chunks,
            "pending_chunks": pending_chunks,
            "index_ready": bool(idx_f.exists() and idx_p.exists()),
            "index_files": {
                "index.faiss": bool(idx_f.exists()),
                "index.pkl": bool(idx_p.exists()),
                "page_info.pkl": bool((s.index_dir / "page_info.pkl").exists()),
            },
        }
    finally:
        conn.close()


def rag_query(
    *,
    q: str,
    stock: str = "",
    k: int | None = None,
    embeddings: Any | None = None,
) -> dict[str, Any]:
    s = get_rag_settings()
    query = str(q or "").strip()
    if not query:
        return {"items": []}

    if embeddings is None:
        embeddings = _load_embeddings()

    from langchain_community.vectorstores import FAISS

    idx_f = s.index_dir / "index.faiss"
    idx_p = s.index_dir / "index.pkl"
    if not (idx_f.exists() and idx_p.exists()):
        return {"items": []}

    vs = FAISS.load_local(str(s.index_dir), embeddings, allow_dangerous_deserialization=True)
    top_k = s.top_k_default if k is None else max(1, min(int(k), 20))

    stock_text = str(stock or "").strip()
    flt: dict[str, Any] | None = None
    if stock_text:
        if stock_text.isdigit() and len(stock_text) == 6:
            flt = {"stock_code": stock_text}
        else:
            flt = {"stock_name": stock_text}

    docs = vs.similarity_search_with_score(query, k=top_k, filter=flt)
    out = []
    for d, score in docs:
        md = d.metadata or {}
        out.append(
            {
                "content": d.page_content,
                "score": float(score) if score is not None else None,
                "meta": {
                    "doc_id": md.get("doc_id"),
                    "chunk_id": md.get("chunk_id"),
                    "page": md.get("page"),
                    "stock_name": md.get("stock_name"),
                    "stock_code": md.get("stock_code"),
                    "title": md.get("title"),
                    "source": md.get("source"),
                    "report_type": md.get("report_type"),
                    "publish_date": md.get("publish_date"),
                },
            }
        )
    return {"items": out}


def resolve_stock_name_by_code(code: str) -> str | None:
    c = str(code or "").strip()
    if not c:
        return None
    if "." in c:
        c = c.split(".", 1)[0]
    if not (c.isdigit() and len(c) == 6):
        return None

    s = get_rag_settings()
    conn = _connect_db(s.db_path)
    try:
        _init_db(conn)
        row = conn.execute(
            """
            SELECT stock_name
            FROM documents
            WHERE stock_code=? AND stock_name IS NOT NULL AND stock_name <> ''
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (c,),
        ).fetchone()
        if row and row[0]:
            return str(row[0])
        return None
    finally:
        conn.close()

