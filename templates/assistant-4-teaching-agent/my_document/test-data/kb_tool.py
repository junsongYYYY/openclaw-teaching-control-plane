#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库工具 - SQLite FTS5 全文检索
PDF 文本提取 → FTS5 索引 → 关键词检索返回相关段落
支持增量重建索引（检测 PDF 文件变化）
"""

import os
import sys
import re
import json
import sqlite3
import hashlib
import time
from datetime import datetime
from pdfminer.high_level import extract_text

# ─── 路径配置 ───
KB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(KB_DIR, "kb_index.db")
PDF_DIRS = {
    "reference": os.path.join(KB_DIR, "reference"),
    "teaching": os.path.join(KB_DIR, "teaching"),
    "research": os.path.join(KB_DIR, "research"),
}
CHUNK_SIZE = 500  # 每个段落大约字符数


def get_connection(db_path=None):
    """获取数据库连接"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=4000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn=None):
    """初始化数据库表结构"""
    if conn is None:
        conn = get_connection()
        auto_close = True
    else:
        auto_close = False

    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            filepath TEXT NOT NULL,
            category TEXT DEFAULT 'reference',
            chapter TEXT DEFAULT '',
            page_count INTEGER DEFAULT 0,
            file_hash TEXT DEFAULT '',
            file_size INTEGER DEFAULT 0,
            last_modified TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chapter TEXT DEFAULT '',
            page_num INTEGER DEFAULT 0,
            text TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    c.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
            text,
            content='content',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 0'
        )
    """)
    c.execute("""
        CREATE TRIGGER IF NOT EXISTS content_ai AFTER INSERT ON content BEGIN
            INSERT INTO fts_content(rowid, text) VALUES (new.id, new.text);
        END
    """)
    c.execute("""
        CREATE TRIGGER IF NOT EXISTS content_ad AFTER DELETE ON content BEGIN
            INSERT INTO fts_content(fts_content, rowid, text) VALUES('delete', old.id, old.text);
        END
    """)
    c.execute("""
        CREATE TRIGGER IF NOT EXISTS content_au AFTER UPDATE ON content BEGIN
            INSERT INTO fts_content(fts_content, rowid, text) VALUES('delete', old.id, old.text);
            INSERT INTO fts_content(rowid, text) VALUES (new.id, new.text);
        END
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_content_doc_id ON content(doc_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_documents_filename ON documents(filename)")
    conn.commit()

    if auto_close:
        conn.close()


def file_hash(filepath):
    """计算文件 SHA256 哈希"""
    h = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def extract_pdf_text(filepath):
    """提取 PDF 文本，返回按段落分割的列表"""
    try:
        raw_text = extract_text(filepath)
        if not raw_text or not raw_text.strip():
            return []
        return raw_text
    except Exception as e:
        print(f"  [WARN] PDF 提取失败 {os.path.basename(filepath)}: {e}", file=sys.stderr)
        return ""


def split_into_chunks(text, chunk_size=CHUNK_SIZE):
    """
    将文本按语义边界（换行、句号、分号）分割成段落块
    尊重原文结构，尽量在自然断点处切分
    """
    if not text:
        return []

    # 先按换行分割
    paragraphs = re.split(r'\n\s*\n|\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        # 如果单个段落就超过 chunk_size，强制切分
        if para_len > chunk_size * 2:
            # 先保存已有的
            if current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            # 按句号/分号强制切分长段落
            sentences = re.split(r'([。；；.\n])', para)
            sent_chunk = []
            sent_len = 0
            for s in sentences:
                s_len = len(s)
                if sent_len + s_len > chunk_size and sent_chunk:
                    chunks.append("".join(sent_chunk).strip())
                    sent_chunk = [s]
                    sent_len = s_len
                else:
                    sent_chunk.append(s)
                    sent_len += s_len
            if sent_chunk:
                chunks.append("".join(sent_chunk).strip())
            continue

        # 正常段落合并
        if current_len + para_len > chunk_size and current:
            chunks.append(" ".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def build_index(category=None, force_rebuild=False):
    """
    构建索引
    - 增量模式：只处理新增或修改的 PDF
    - force_rebuild=True：全量重建
    """
    conn = get_connection()
    init_db(conn)

    if category and category in PDF_DIRS:
        scan_dirs = {category: PDF_DIRS[category]}
    else:
        scan_dirs = PDF_DIRS

    total_files = 0
    total_chunks = 0
    updated_files = 0
    skipped_files = 0

    for cat, dir_path in scan_dirs.items():
        if not os.path.isdir(dir_path):
            continue

        pdf_files = [f for f in os.listdir(dir_path) if f.lower().endswith(".pdf")]
        total_files += len(pdf_files)

        for pdf_file in sorted(pdf_files):
            filepath = os.path.join(dir_path, pdf_file)
            file_size = os.path.getsize(filepath)
            last_mod = datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
            h = file_hash(filepath)

            # 检查是否已存在且未修改
            row = conn.execute(
                "SELECT id, file_hash, file_size FROM documents WHERE filename = ?",
                (pdf_file,)
            ).fetchone()

            if row and not force_rebuild:
                if row["file_hash"] == h and row["file_size"] == file_size:
                    skipped_files += 1
                    continue
                else:
                    # 文件已修改，删除旧数据重新索引
                    doc_id = row["id"]
                    conn.execute("DELETE FROM content WHERE doc_id = ?", (doc_id,))
                    conn.execute("UPDATE documents SET updated_at = datetime('now','localtime') WHERE id = ?", (doc_id,))
                    updated_files += 1

            # 提取文本
            print(f"  提取: {pdf_file}")
            text = extract_pdf_text(filepath)
            if not text:
                continue

            # 分割段落
            chunks = split_into_chunks(text)

            # 插入文档记录
            if row and not force_rebuild:
                doc_id = row["id"]
                conn.execute(
                    """UPDATE documents SET file_hash=?, file_size=?, last_modified=?,
                       filepath=?, category=?, page_count=?, updated_at=datetime('now','localtime')
                       WHERE id=?""",
                    (h, file_size, last_mod, filepath, cat, len(chunks), doc_id)
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO documents (filename, filepath, category, chapter, page_count, file_hash, file_size, last_modified)
                       VALUES (?, ?, ?, '', ?, ?, ?, ?)""",
                    (pdf_file, filepath, cat, len(chunks), h, file_size, last_mod)
                )
                doc_id = cursor.lastrowid
                updated_files += 1

            # 插入段落（分批提交，避免长事务）
            batch_count = 0
            for i, chunk in enumerate(chunks):
                conn.execute(
                    "INSERT INTO content (doc_id, chapter, text) VALUES (?, '', ?)",
                    (doc_id, chunk)
                )
                batch_count += 1
                total_chunks += 1
                if batch_count % 100 == 0:
                    conn.commit()

    conn.commit()

    # 优化 FTS5
    conn.execute("INSERT INTO fts_content(fts_content) VALUES('optimize')")
    conn.commit()
    conn.close()

    result = {
        "total_files": total_files,
        "indexed_files": updated_files,
        "skipped_files": skipped_files,
        "total_chunks": total_chunks,
        "timestamp": datetime.now().isoformat(),
    }
    return result


def search(query, limit=10, snippet_len=200):
    """
    全文检索
    返回相关段落列表，包含来源文件名
    """
    conn = get_connection()

    # 清理查询词
    query = query.strip()
    if not query:
        conn.close()
        return []

    try:
        rows = conn.execute(
            """SELECT c.id, c.text, c.doc_id, d.filename, d.category,
                      snippet(fts_content, '<b>', '</b>', '...', 32) as snippet
               FROM fts_content
               JOIN content c ON c.id = fts_content.rowid
               JOIN documents d ON d.id = c.doc_id
               WHERE fts_content MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit)
        ).fetchall()
    except Exception as e:
        # FTS5 查询失败时回退到 LIKE
        like_query = "%" + query.replace("*", "") + "%"
        rows = conn.execute(
            """SELECT c.id, c.text, c.doc_id, d.filename, d.category, '' as snippet
               FROM content c
               JOIN documents d ON d.id = c.doc_id
               WHERE c.text LIKE ?
               LIMIT ?""",
            (like_query, limit)
        ).fetchall()

    results = []
    for row in rows:
        results.append({
            "doc_id": row["doc_id"],
            "filename": row["filename"],
            "category": row["category"],
            "text": row["text"][:snippet_len] + "..." if len(row["text"]) > snippet_len else row["text"],
            "snippet": row["snippet"] if row["snippet"] else row["text"][:snippet_len],
        })

    conn.close()
    return results


def list_documents():
    """列出所有已索引的文档"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, filename, category, page_count, file_size, last_modified, created_at FROM documents ORDER BY filename"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_doc_content(doc_id, max_chunks=20):
    """获取某文档的完整内容"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT text FROM content WHERE doc_id = ? LIMIT ?",
        (doc_id, max_chunks)
    ).fetchall()
    conn.close()
    return [r["text"] for r in rows]


# ─── CLI 入口 ───
def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 kb_tool.py build [category]        # 构建索引 (增量)")
        print("  python3 kb_tool.py rebuild [category]      # 全量重建")
        print("  python3 kb_tool.py search '关键词' [limit]  # 全文检索")
        print("  python3 kb_tool.py list                     # 列出已索引文档")
        print("  python3 kb_tool.py info                     # 显示索引状态")
        return

    cmd = sys.argv[1]

    if cmd in ("build", "rebuild"):
        force = cmd == "rebuild"
        category = sys.argv[2] if len(sys.argv) > 2 else None
        t0 = time.time()
        result = build_index(category, force_rebuild=force)
        elapsed = time.time() - t0
        print(f"\n{'='*50}")
        print(f"索引构建完成 ({cmd})")
        print(f"  扫描文件: {result['total_files']}")
        print(f"  新/更新: {result['indexed_files']}")
        print(f"  跳过(未变): {result['skipped_files']}")
        print(f"  总段落数: {result['total_chunks']}")
        print(f"  耗时: {elapsed:.1f}s")
        print(f"{'='*50}")

    elif cmd == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else ""
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
        t0 = time.time()
        results = search(query, limit)
        elapsed = time.time() - t0
        print(f"\n搜索: '{query}' (耗时: {elapsed:.3f}s, 命中 {len(results)} 条)")
        print("=" * 60)
        for i, r in enumerate(results, 1):
            print(f"\n[{i}] 📄 {r['filename']}")
            print(f"    {r['text'][:150]}...")

    elif cmd == "list":
        docs = list_documents()
        print(f"\n已索引文档 ({len(docs)} 个):")
        print("-" * 60)
        for d in docs:
            size_kb = d['file_size'] / 1024
            print(f"  [{d['category']}] {d['filename']} ({size_kb:.0f}KB)")

    elif cmd == "info":
        conn = get_connection()
        doc_count = conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()["cnt"]
        chunk_count = conn.execute("SELECT COUNT(*) as cnt FROM content").fetchone()["cnt"]
        db_size = os.path.getsize(DB_PATH) / 1024 / 1024 if os.path.exists(DB_PATH) else 0
        conn.close()
        print(f"\n📊 索引状态:")
        print(f"  文档数: {doc_count}")
        print(f"  段落数: {chunk_count}")
        print(f"  数据库大小: {db_size:.1f}MB")
        print(f"  数据库路径: {DB_PATH}")


if __name__ == "__main__":
    main()
