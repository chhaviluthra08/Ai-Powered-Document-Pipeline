import os
import argparse
import time
from ingestion import scan_input_folder
from email_ingestion import fetch_unread_email_attachments, run_email_poller
from pipeline import process_document
from retrieval import init_few_shot_examples
from storage import init_db

def run_pipeline_for_source(source: str, input_dir: str, force: bool = False, poll_interval: int = 0):
    print("Initializing Database...")
    init_db()
    print("Initializing ChromaDB examples...")
    init_few_shot_examples()

    if source == "email":
        print(f"Running pipeline in EMAIL auto-ingestion mode (input_dir: '{input_dir}')...")
        if poll_interval > 0:
            def process_callback(file_path, metadata):
                process_document(file_path, metadata, force=force)
                
            run_email_poller(poll_interval=poll_interval, input_dir=input_dir, callback=process_callback)
        else:
            documents = fetch_unread_email_attachments(input_dir)
            if not documents:
                print("No new qualifying email attachments found.")
                return
            for doc in documents:
                process_document(doc['file_path'], doc['metadata'], force=force)
    else:
        print(f"Running pipeline in LOCAL folder scan mode (input_dir: '{input_dir}')...")
        documents = scan_input_folder(input_dir)
        if not documents:
            print("No documents found in input directory.")
            return
        for doc in documents:
            process_document(doc['file_path'], doc['metadata'], force=force)

def main():
    parser = argparse.ArgumentParser(description="AI Document Processing Pipeline CLI")
    parser.add_argument(
        "--source",
        choices=["local", "email"],
        default="local",
        help="Source mode for document ingestion: 'local' (scan folder) or 'email' (IMAP poller)"
    )
    parser.add_argument(
        "--input",
        default="input_docs",
        help="Input folder path for document files"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force reprocessing of documents even if content hash exists"
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=0,
        help="Interval in seconds for continuous email polling loop (0 = single pass)"
    )

    args = parser.parse_args()
    run_pipeline_for_source(
        source=args.source,
        input_dir=args.input,
        force=args.force,
        poll_interval=args.poll_interval
    )

if __name__ == '__main__':
    main()
