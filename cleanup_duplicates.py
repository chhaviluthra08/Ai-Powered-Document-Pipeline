import sqlite3
from storage import get_connection, delete_document

def cleanup_duplicate_documents():
    """
    Finds duplicate document entries in platform.db for the 5 original test filenames
    (doc1_invoice.pdf, doc2_po.pdf, doc3_scanned.jpg, doc4_bank.pdf, doc5_malformed.pdf)
    and removes all but the most recent entry for each, deleting child rows as well.
    """
    test_filenames = [
        "doc1_invoice.pdf",
        "doc2_po.pdf",
        "doc3_scanned.jpg",
        "doc4_bank.pdf",
        "doc5_malformed.pdf"
    ]
    
    print("Starting duplicate cleanup for test documents...")
    deleted_total = 0
    
    with get_connection() as conn:
        cur = conn.cursor()
        for filename in test_filenames:
            cur.execute(
                "SELECT id, ingestion_time FROM documents WHERE filename = ? ORDER BY ingestion_time DESC",
                (filename,)
            )
            rows = cur.fetchall()
            if len(rows) > 1:
                # Keep the first row (most recent), delete the remaining duplicates
                latest_id = rows[0][0]
                duplicate_rows = rows[1:]
                print(f"File '{filename}': Keeping latest doc_id {latest_id[:8]}..., deleting {len(duplicate_rows)} older duplicate(s)...")
                for dup_id, _ in duplicate_rows:
                    delete_document(dup_id, delete_file=False)
                    deleted_total += 1
            elif len(rows) == 1:
                print(f"File '{filename}': Single clean entry found ({rows[0][0][:8]}...). No cleanup needed.")
            else:
                print(f"File '{filename}': No entries found.")
                
    print(f"Cleanup finished! Removed {deleted_total} duplicate document records and associated child rows.")

if __name__ == '__main__':
    cleanup_duplicate_documents()
