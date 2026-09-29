import os
import json
import glob

def scan_input_folder(input_dir: str):
    """
    Scans the input folder for document files (PDF, PNG, JPG, JPEG).
    Returns a list of dicts: {'file_path': str, 'metadata': dict}
    
    PRODUCTION SUBSTITUTION: This simulates an email inbox by reading local files.
    For production, replace this with a Microsoft Graph API integration that 
    listens for new emails, downloads attachments, and extracts real email metadata.
    """
    documents = []
    
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        print(f"Created input directory at {input_dir}")
        return documents

    valid_extensions = ('.pdf', '.png', '.jpg', '.jpeg')
    
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(valid_extensions):
            file_path = os.path.join(input_dir, filename)
            
            # Look for companion metadata file (e.g. filename.json)
            base_name, _ = os.path.splitext(filename)
            meta_path = os.path.join(input_dir, f"{base_name}.json")
            
            metadata = {
                "sender": "unknown@example.com",
                "subject": f"Document {filename}",
                "received_date": "2023-01-01T00:00:00Z"
            }
            
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r') as f:
                        loaded_meta = json.load(f)
                        metadata.update(loaded_meta)
                except Exception as e:
                    print(f"Error reading metadata for {filename}: {e}")
                    
            documents.append({
                'file_path': file_path,
                'metadata': metadata
            })
            
    return documents
