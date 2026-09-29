import os
import sqlite3
from storage import get_connection, compute_file_hash

def backfill_content_hashes():
    print("Starting content_hash backfill migration...")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, file_path FROM documents WHERE content_hash IS NULL ORDER BY ingestion_time DESC")
        rows = cur.fetchall()
        
        updated_count = 0
        skipped_count = 0
        duplicate_hash_count = 0
        
        for doc_id, file_path in rows:
            if file_path and os.path.exists(file_path):
                file_hash = compute_file_hash(file_path)
                try:
                    cur.execute("UPDATE documents SET content_hash = ? WHERE id = ?", (file_hash, doc_id))
                    updated_count += 1
                except sqlite3.IntegrityError:
                    duplicate_hash_count += 1
            else:
                skipped_count += 1
                
        # One-time cleanup for legacy stale errors (IDs 1, 2, 3, 4)
        cur.execute("UPDATE review_queue SET status = 'resolved' WHERE id IN (1, 2, 3, 4)")
        resolved_count = cur.rowcount
        
    print(f"Migration completed:")
    print(f"  - Updated content_hash for {updated_count} documents.")
    print(f"  - Duplicate hash skipped for {duplicate_hash_count} legacy duplicate records.")
    print(f"  - Skipped {skipped_count} documents (file missing or path invalid).")
    print(f"  - Resolved {resolved_count} legacy review_queue entries (IDs 1-4).")

if __name__ == '__main__':
    backfill_content_hashes()
