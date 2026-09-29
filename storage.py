import sqlite3
import os
import uuid
import hashlib
import json
from datetime import datetime

DB_PATH = 'platform.db'
SCHEMA_PATH = 'db_schema.sql'

def get_connection():
    # Use 30s timeout and autocommit mode (isolation_level=None) to handle concurrent writers
    conn = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    if not os.path.exists(SCHEMA_PATH):
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_PATH}")
    
    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        with open(SCHEMA_PATH, 'r') as f:
            conn.executescript(f.read())
        
        # Check and apply migrations for existing DB
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(documents);")
        columns = [row[1] for row in cur.fetchall()]
        if 'content_hash' not in columns:
            cur.execute("ALTER TABLE documents ADD COLUMN content_hash TEXT;")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);")

def compute_file_hash(file_path: str) -> str:
    """Computes SHA-256 hash of a file for content-based deduplication."""
    if not os.path.exists(file_path):
        return ""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def is_duplicate_document(file_hash: str) -> bool:
    """Checks if a document with the same content hash has already been inserted."""
    if not file_hash:
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM documents WHERE content_hash = ?", (file_hash,))
        return cur.fetchone() is not None

def is_email_processed(message_id: str) -> bool:
    """Checks if a Gmail message_id has already been processed."""
    if not message_id:
        return False
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT message_id FROM processed_emails WHERE message_id = ?", (message_id,))
        return cur.fetchone() is not None

def mark_email_processed(message_id: str, subject: str = "", sender: str = ""):
    """Records a Gmail message_id as processed."""
    if not message_id:
        return
    with get_connection() as conn:
        conn.execute(
            '''INSERT OR IGNORE INTO processed_emails (message_id, subject, sender)
               VALUES (?, ?, ?)''',
            (message_id, subject, sender)
        )

def log_audit(document_id: str, step: str, action: str, model_used: str = None, confidence: int = None, details: str = None):
    with get_connection() as conn:
        conn.execute(
            '''INSERT INTO audit_log (document_id, step, action, model_used, confidence, details) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (document_id, step, action, model_used, confidence, details)
        )

def insert_document(filename: str, file_path: str, content_hash: str = None, force: bool = False) -> str:
    if force:
        content_hash = None
    elif content_hash is None:
        content_hash = compute_file_hash(file_path)
        
    doc_id = str(uuid.uuid4())
    with get_connection() as conn:
        conn.execute(
            '''INSERT INTO documents (id, filename, file_path, content_hash, status) VALUES (?, ?, ?, ?, ?)''',
            (doc_id, filename, file_path, content_hash, 'processing')
        )
    log_audit(doc_id, 'Ingestion', 'Document inserted', details=f"File: {filename}")
    return doc_id

def update_document(doc_id: str, status: str, document_type: str = None, confidence_score: int = None, raw_text: str = None):
    with get_connection() as conn:
        query = 'UPDATE documents SET status = ?'
        params = [status]
        
        if document_type is not None:
            query += ', document_type = ?'
            params.append(document_type)
        if confidence_score is not None:
            query += ', confidence_score = ?'
            params.append(confidence_score)
        if raw_text is not None:
            query += ', raw_text = ?'
            params.append(raw_text)
            
        query += ' WHERE id = ?'
        params.append(doc_id)
        
        conn.execute(query, tuple(params))

def insert_extractions(doc_id: str, extractions: dict):
    # extractions format: { "field_name": {"value": "X" or dict or list, "confidence_score": 90} }
    with get_connection() as conn:
        for field, data in extractions.items():
            if field == 'document_type': 
                continue # stored in documents table
            
            if not isinstance(data, dict):
                val = data
                conf = 100
            else:
                val = data.get('value')
                conf = data.get('confidence_score', 100)
                
            if isinstance(val, (list, dict)):
                val = json.dumps(val)
                
            conn.execute(
                '''INSERT INTO extractions (document_id, field_name, extracted_value, confidence, is_valid)
                   VALUES (?, ?, ?, ?, ?)''',
                (doc_id, field, val, conf, True)
            )

def route_to_review(doc_id: str, reason: str):
    with get_connection() as conn:
        conn.execute(
            '''INSERT INTO review_queue (document_id, reason) VALUES (?, ?)''',
            (doc_id, reason)
        )
    update_document(doc_id, 'review_required')
    log_audit(doc_id, 'Validation', 'Routed to review queue', details=reason)

def get_review_queue():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM review_queue WHERE status = 'pending'")
        return [dict(row) for row in cur.fetchall()]

def log_correction(doc_id: str, field_name: str, original_value: str, corrected_value: str, corrected_by: str = 'human'):
    with get_connection() as conn:
        conn.execute(
            '''INSERT INTO corrections_log (document_id, field_name, original_value, corrected_value, corrected_by)
               VALUES (?, ?, ?, ?, ?)''',
            (doc_id, field_name, original_value, corrected_value, corrected_by)
        )

def delete_document(doc_id: str, delete_file: bool = True):
    """Cascading delete of a document and all related database rows.
    
    If delete_file is True (default), also removes the physical file from disk.
    Pass delete_file=False to remove only DB rows (e.g. dedup cleanup).
    """
    file_path = None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        if row:
            file_path = row[0]

        conn.execute("DELETE FROM extractions WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM review_queue WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM audit_log WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM corrections_log WHERE document_id = ?", (doc_id,))
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    if delete_file and file_path:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            else:
                print(f"[storage] Warning: File '{file_path}' not found on disk during deletion.")
        except Exception as e:
            print(f"[storage] Warning: Failed to remove file '{file_path}': {e}")

if __name__ == '__main__':
    init_db()
    print("Database initialized.")

