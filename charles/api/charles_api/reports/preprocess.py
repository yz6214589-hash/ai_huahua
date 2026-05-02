from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from PyPDF2 import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
PARSED_DIR = DATA_DIR / "parsed"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"
DB_PATH = DATA_DIR / "documents.db"

STOCK_CODE_MAP = {
    "中芯国际": "688981",
    "贵州茅台": "600519",
    "比亚迪": "002594",
    "宁德时代": "300750",
    "隆基绿能": "601012",
    "招商银行": "600036",
    "中国平安": "601318",
    "五粮液": "000858",
    "海天味业": "603288",
    "恒瑞医药": "600276",
}

REPORT_TYPE_PATTERNS = [
    (r"年度报告|年报", "年报"),
    (r"半年度报告|半年报", "半年报"),
    (r"第一季度报告|一季度报告|一季报", "一季报"),
    (r"第三季度报告|三季度报告|三季报", "三季报"),
    (r"季度报告|季报", "季报"),
    (r"业绩点评|业绩快报", "业绩点评"),
    (r"深度研究|深度报告|研究报告", "深度研报"),
    (r"调研纪要", "调研纪要"),
]


def parse_filename(filename: str) -> Dict:
    name = os.path.splitext(filename)[0]
    result = {"filename": filename, "title": name, "stock_name": "", "source": "", "report_type": ""}
    m = re.match(r"财报[_](.+?)[:：](.+)", name)
    if m:
        result["stock_name"] = m.group(1).strip()
        result["title"] = m.group(2).strip()
        result["source"] = "官方财报"
        _detect_report_type(result)
        return result

    m = re.match(r"【财报】(.+?)[:：](.+)", name)
    if m:
        result["stock_name"] = m.group(1).strip()
        result["title"] = m.group(2).strip()
        result["source"] = "官方财报"
        _detect_report_type(result)
        return result

    m = re.match(r"【(.+?)】(.+)", name)
    if m:
        result["source"] = m.group(1).strip()
        result["title"] = m.group(2).strip()
        _detect_stock_from_title(result)
        _detect_report_type(result)
        if not result["report_type"]:
            result["report_type"] = "研报"
        return result

    _detect_stock_from_title(result)
    _detect_report_type(result)
    return result


def _detect_stock_from_title(result: Dict):
    for stock_name in STOCK_CODE_MAP:
        if stock_name in result["title"]:
            result["stock_name"] = stock_name
            return
    m = re.search(r"[（(](\d{6})[）)]", result["title"])
    if m:
        code = m.group(1)
        for name, c in STOCK_CODE_MAP.items():
            if c == code:
                result["stock_name"] = name
                return


def _detect_report_type(result: Dict):
    for pattern, rtype in REPORT_TYPE_PATTERNS:
        if re.search(pattern, result["title"]):
            result["report_type"] = rtype
            return


def extract_pdf_text(pdf_path: str) -> Tuple[str, List[dict]]:
    reader = PdfReader(pdf_path)
    full_text = ""
    pages = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"page": page_num, "text": text, "char_count": len(text)})
        full_text += text
    return full_text, pages


def extract_stock_code(text: str, stock_name: str = "") -> str:
    if stock_name and stock_name in STOCK_CODE_MAP:
        return STOCK_CODE_MAP[stock_name]
    patterns = [
        r"(?:股票代码|证券代码|A\s*股.*?代码|代码)[：:\s]*(\d{6})",
        r"(?:Stock\s*Code)[：:\s]*(\d{6})",
        r"[（(](\d{6})[）)]",
    ]
    for pattern in patterns:
        m = re.search(pattern, text[:15000])
        if m:
            return m.group(1)
    return ""


def extract_stock_name_from_text(text: str) -> str:
    search_text = text[:8000]
    for stock_name in STOCK_CODE_MAP:
        if stock_name in search_text:
            return stock_name
    return ""


def extract_publish_date(text: str) -> str:
    search_text = text[:15000]
    context_patterns = [
        r"(?:披露日期|公告日期|报告日期|发布日期|编制日期|批准报告日)[：:\s]*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(?:披露日期|公告日期|报告日期|发布日期|编制日期)[：:\s]*(\d{4})-(\d{1,2})-(\d{1,2})",
    ]
    for pattern in context_patterns:
        m = re.search(pattern, search_text)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 2000 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
    all_dates = []
    for m in re.finditer(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", search_text[:3000]):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
            all_dates.append(f"{year:04d}-{month:02d}-{day:02d}")
    if all_dates:
        return all_dates[-1]
    return ""


def extract_report_period(text: str) -> str:
    search_text = text[:8000]
    patterns = [
        r"(\d{4})\s*年\s*(第[一二三四]季度)",
        r"(\d{4})\s*年\s*(半年度)",
        r"(\d{4})\s*年[度]?\s*(年度报告|年报)",
    ]
    for pattern in patterns:
        m = re.search(pattern, search_text)
        if m:
            year = m.group(1)
            period = m.group(2)
            if "年度报告" in period or "年报" in period:
                return f"{year}年度"
            return f"{year}年{period}"
    return ""


def chunk_with_metadata(
    full_text: str,
    pages: List[dict],
    doc_metadata: Dict,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> List[Dict]:
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", ".", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    chunks = splitter.split_text(full_text)
    page_boundaries = []
    offset = 0
    for p in pages:
        page_boundaries.append({"page": p["page"], "start": offset, "end": offset + p["char_count"]})
        offset += p["char_count"]

    result = []
    for idx, chunk_text in enumerate(chunks):
        page_num = -1
        chunk_start = full_text.find(chunk_text[:100])
        if chunk_start >= 0:
            for pb in page_boundaries:
                if pb["start"] <= chunk_start < pb["end"]:
                    page_num = pb["page"]
                    break
        metadata = {
            "doc_id": doc_metadata.get("doc_id", 0),
            "filename": doc_metadata.get("filename", ""),
            "title": doc_metadata.get("title", ""),
            "stock_name": doc_metadata.get("stock_name", ""),
            "stock_code": doc_metadata.get("stock_code", ""),
            "source": doc_metadata.get("source", ""),
            "report_type": doc_metadata.get("report_type", ""),
            "publish_date": doc_metadata.get("publish_date", ""),
            "page": page_num,
            "chunk_index": idx,
            "total_chunks": len(chunks),
            "total_pages": doc_metadata.get("total_pages", 0),
        }
        result.append({"text": chunk_text, "metadata": metadata})
    return result


def init_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            title TEXT,
            stock_name TEXT,
            stock_code TEXT,
            source TEXT,
            report_type TEXT,
            report_period TEXT,
            publish_date TEXT,
            total_pages INTEGER,
            total_chars INTEGER,
            total_chunks INTEGER,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.commit()
    return conn


def get_processed_files(conn: sqlite3.Connection) -> set:
    cursor = conn.execute("SELECT filename FROM documents")
    return {row[0] for row in cursor.fetchall()}


def insert_document(conn: sqlite3.Connection, doc: Dict) -> int:
    conn.execute(
        """
        INSERT OR REPLACE INTO documents
        (filename, title, stock_name, stock_code, source, report_type,
         report_period, publish_date, total_pages, total_chars, total_chunks)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            doc["filename"],
            doc["title"],
            doc["stock_name"],
            doc["stock_code"],
            doc["source"],
            doc["report_type"],
            doc.get("report_period", ""),
            doc["publish_date"],
            doc["total_pages"],
            doc["total_chars"],
            doc["total_chunks"],
        ),
    )
    conn.commit()
    cursor = conn.execute("SELECT id FROM documents WHERE filename = ?", (doc["filename"],))
    return cursor.fetchone()[0]


def process_single_pdf(
    pdf_path: str,
    conn: sqlite3.Connection,
    chunk_size: int = 800,
    chunk_overlap: int = 150,
) -> Tuple[int, List[Dict]]:
    filename = os.path.basename(pdf_path)
    file_meta = parse_filename(filename)

    full_text, pages = extract_pdf_text(pdf_path)
    total_pages = len(pages)
    if not full_text.strip():
        return -1, []

    if not file_meta["stock_name"]:
        file_meta["stock_name"] = extract_stock_name_from_text(full_text)

    stock_code = extract_stock_code(full_text, file_meta["stock_name"])
    publish_date = extract_publish_date(full_text)
    report_period = extract_report_period(full_text)

    if not file_meta["stock_name"] and stock_code:
        for name, code in STOCK_CODE_MAP.items():
            if code == stock_code:
                file_meta["stock_name"] = name
                break

    doc_data = {
        "filename": filename,
        "title": file_meta["title"],
        "stock_name": file_meta["stock_name"],
        "stock_code": stock_code,
        "source": file_meta["source"],
        "report_type": file_meta["report_type"],
        "report_period": report_period,
        "publish_date": publish_date,
        "total_pages": total_pages,
        "total_chars": len(full_text),
        "total_chunks": 0,
    }
    doc_id = insert_document(conn, doc_data)

    doc_metadata = {"doc_id": doc_id, **doc_data, "total_pages": total_pages}
    chunks = chunk_with_metadata(full_text, pages, doc_metadata, chunk_size, chunk_overlap)

    conn.execute("UPDATE documents SET total_chunks = ? WHERE id = ?", (len(chunks), doc_id))
    conn.commit()

    os.makedirs(str(PARSED_DIR), exist_ok=True)
    base = os.path.splitext(filename)[0]
    full_text_path = str(PARSED_DIR / f"{base}_full.txt")
    with open(full_text_path, "w", encoding="utf-8") as f:
        f.write(full_text)
    pages_json_path = str(PARSED_DIR / f"{base}_pages.json")
    with open(pages_json_path, "w", encoding="utf-8") as f:
        json.dump(pages, f, ensure_ascii=False, indent=2)

    return doc_id, chunks


def build_unified_index(all_chunks: List[Dict], index_dir: str, embedding_model: str = "text-embedding-v4"):
    from langchain_community.embeddings import DashScopeEmbeddings
    from langchain_community.vectorstores import FAISS

    api_key = os.getenv("DASHSCOPE_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY required for embeddings")

    embeddings = DashScopeEmbeddings(model=embedding_model, dashscope_api_key=api_key)
    texts = [c["text"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    batch_size = 25
    vectorstore = None
    max_retries = 6
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        for attempt in range(max_retries):
            try:
                if vectorstore is None:
                    vectorstore = FAISS.from_texts(batch_texts, embeddings, metadatas=batch_metas)
                else:
                    vectorstore.add_texts(batch_texts, metadatas=batch_metas)
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    time.sleep(wait)
                else:
                    raise
        if i + batch_size < len(texts):
            time.sleep(1)

    os.makedirs(index_dir, exist_ok=True)
    vectorstore.save_local(index_dir)

    chunks_json_path = os.path.join(index_dir, "chunks.json")
    chunks_data = [{"text": c["text"], "metadata": c["metadata"]} for c in all_chunks]
    with open(chunks_json_path, "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)

    stock_codes = sorted({m.get("stock_code") for m in metadatas if m.get("stock_code")})
    index_meta = {
        "total_chunks": len(texts),
        "embedding_model": embedding_model,
        "chunk_size": 800,
        "chunk_overlap": 150,
        "stock_codes": stock_codes,
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(os.path.join(index_dir, "index_meta.json"), "w", encoding="utf-8") as f:
        json.dump(index_meta, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--reports_dir", default=str(REPORTS_DIR))
    parser.add_argument("--chunk_size", type=int, default=800)
    parser.add_argument("--chunk_overlap", type=int, default=150)
    parser.add_argument("--embedding_model", default="text-embedding-v4")
    args = parser.parse_args()

    os.makedirs(str(DATA_DIR), exist_ok=True)
    conn = init_db(str(DB_PATH))
    if args.list:
        cursor = conn.execute(
            "SELECT id, filename, stock_name, stock_code, report_type, publish_date, total_pages, total_chunks, created_at FROM documents ORDER BY id"
        )
        rows = cursor.fetchall()
        for r in rows:
            print(r)
        conn.close()
        return

    reports_dir = args.reports_dir
    if not os.path.exists(reports_dir):
        raise SystemExit(1)
    pdf_files = sorted([f for f in os.listdir(reports_dir) if f.lower().endswith(".pdf")])
    if not pdf_files:
        conn.close()
        return

    if args.rebuild:
        conn.execute("DELETE FROM documents")
        conn.commit()
        processed = set()
    else:
        processed = get_processed_files(conn)

    new_files = [f for f in pdf_files if f not in processed]
    skip_files = [f for f in pdf_files if f in processed]

    all_chunks: list[Dict] = []

    for filename in new_files:
        pdf_path = os.path.join(reports_dir, filename)
        _, chunks = process_single_pdf(pdf_path, conn, args.chunk_size, args.chunk_overlap)
        if chunks:
            all_chunks.extend(chunks)

    if skip_files:
        for filename in skip_files:
            base = os.path.splitext(filename)[0]
            full_text_path = str(PARSED_DIR / f"{base}_full.txt")
            pages_json_path = str(PARSED_DIR / f"{base}_pages.json")
            if not os.path.exists(full_text_path):
                continue
            with open(full_text_path, "r", encoding="utf-8") as f:
                full_text = f.read()
            pages = []
            if os.path.exists(pages_json_path):
                with open(pages_json_path, "r", encoding="utf-8") as f:
                    pages = json.load(f)
            cursor = conn.execute(
                "SELECT id, title, stock_name, stock_code, source, report_type, report_period, publish_date, total_pages, total_chars FROM documents WHERE filename = ?",
                (filename,),
            )
            row = cursor.fetchone()
            if not row:
                continue
            doc_metadata = {
                "doc_id": row[0],
                "filename": filename,
                "title": row[1],
                "stock_name": row[2],
                "stock_code": row[3],
                "source": row[4],
                "report_type": row[5],
                "report_period": row[6],
                "publish_date": row[7],
                "total_pages": row[8],
                "total_chars": row[9],
            }
            chunks = chunk_with_metadata(full_text, pages, doc_metadata, args.chunk_size, args.chunk_overlap)
            all_chunks.extend(chunks)

    if not args.skip_index and all_chunks:
        os.makedirs(str(VECTOR_STORE_DIR), exist_ok=True)
        build_unified_index(all_chunks, str(VECTOR_STORE_DIR), args.embedding_model)

    conn.close()


if __name__ == "__main__":
    main()

