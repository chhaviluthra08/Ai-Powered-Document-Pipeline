import os
import argparse
from ingestion import scan_input_folder
from ocr import extract_text
from classification import classify_document
from retrieval import init_few_shot_examples, get_examples_for_type
from extraction import extract_fields
from storage import (
    init_db,
    insert_document,
    update_document,
    insert_extractions,
    route_to_review,
    log_audit,
    compute_file_hash,
    is_duplicate_document,
    is_email_processed,
    mark_email_processed
)

CONFIDENCE_THRESHOLD = 85

def process_document(file_path: str, metadata: dict, force: bool = False):
    print(f"\nProcessing {file_path}...")
    filename = os.path.basename(file_path)
    
    # Check email deduplication if message_id is provided
    message_id = metadata.get('message_id')
    if not force and message_id and is_email_processed(message_id):
        print(f"  Skipping {filename}: Email message_id '{message_id}' already processed.")
        return

    # Check file content deduplication
    file_hash = compute_file_hash(file_path)
    if not force and is_duplicate_document(file_hash):
        print(f"  Skipping {filename}: Content hash '{file_hash[:10]}...' already processed.")
        if message_id:
            mark_email_processed(message_id, metadata.get('subject', ''), metadata.get('sender', ''))
        return

    # 1. Ingestion
    doc_id = insert_document(filename, file_path, content_hash=file_hash, force=force)
    if message_id:
        mark_email_processed(message_id, metadata.get('subject', ''), metadata.get('sender', ''))

    
    try:
        # 2. OCR
        print(f"  [{doc_id}] Running OCR...")
        text = extract_text(file_path)
        update_document(doc_id, status='ocr_completed', raw_text=text)
        log_audit(doc_id, 'OCR', 'Text extracted', details=f"Extracted {len(text)} characters")
        
        if not text.strip():
            route_to_review(doc_id, "OCR yielded no text")
            return
            
        # 3. Classification
        print(f"  [{doc_id}] Classifying...")
        class_result = classify_document(text)
        doc_type = class_result['document_type']
        doc_conf = class_result['confidence']
        update_document(doc_id, status='classified', document_type=doc_type, confidence_score=doc_conf)
        log_audit(doc_id, 'Classification', f'Classified as {doc_type}', confidence=doc_conf)
        
        # 4. Retrieval (Few-shot)
        print(f"  [{doc_id}] Retrieving examples for {doc_type}...")
        examples = get_examples_for_type(doc_type, text)
        log_audit(doc_id, 'Retrieval', f'Retrieved {len(examples)} examples')
        
        # 5. Extraction
        print(f"  [{doc_id}] Extracting fields...")
        extracted_data = extract_fields(text, doc_type, examples)
        
        if not extracted_data:
            route_to_review(doc_id, "Extraction failed: no fields returned (API error or empty response)")
            log_audit(doc_id, 'Extraction', 'Extraction returned empty result', details='Routed to review')
            return

        # Inject email metadata
        extracted_data['email_metadata'] = {
            "value": metadata,
            "confidence_score": 100 # Metadata is assumed correct from system
        }
        extracted_data['document_type'] = {
            "value": doc_type,
            "confidence_score": doc_conf
        }
        
        insert_extractions(doc_id, extracted_data)
        log_audit(doc_id, 'Extraction', 'Fields extracted')
        
        # 6. Validation & Routing
        below_threshold = False
        low_confidence_fields = []
        for field, data in extracted_data.items():
            conf = data.get('confidence_score', 0)
            if conf < CONFIDENCE_THRESHOLD:
                below_threshold = True
                low_confidence_fields.append(f"{field} ({conf}%)")
                
        if below_threshold:
            print(f"  [{doc_id}] Routed to review queue due to low confidence on: {', '.join(low_confidence_fields)}")
            route_to_review(doc_id, f"Low confidence on fields: {', '.join(low_confidence_fields)}")
        else:
            print(f"  [{doc_id}] Processing completed successfully.")
            update_document(doc_id, status='completed')
            log_audit(doc_id, 'Validation', 'Passed all thresholds, marked as completed')
            
    except Exception as e:
        print(f"  [{doc_id}] Error processing: {e}")
        route_to_review(doc_id, f"Pipeline Error: {e}")
        log_audit(doc_id, 'Error', f'Pipeline error: {e}')

def main():
    parser = argparse.ArgumentParser(description="AI Document Processing Pipeline")
    parser.add_argument("--input", default="input_docs", help="Folder containing input documents")
    parser.add_argument("--force", action="store_true", help="Reprocess documents even if already ingested (bypasses dedup)")
    args = parser.parse_args()
    
    print("Initializing Database...")
    init_db()
    print("Initializing ChromaDB examples...")
    init_few_shot_examples()
    
    print(f"Scanning input folder: {args.input}...")
    documents = scan_input_folder(args.input)
    
    if not documents:
        print("No documents found.")
        return
        
    for doc in documents:
        process_document(doc['file_path'], doc['metadata'], force=args.force)

if __name__ == '__main__':
    main()
