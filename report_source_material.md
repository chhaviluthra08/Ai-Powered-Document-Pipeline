# Report Source Material — AI-Powered Document Processing Platform
*Extracted from codebase on 2026-08-13. Read-only investigation; no code was changed.*

---

## 1. Project Identity

### Formal Project Title
**AI-Powered Business Document Processing Platform with Human-in-the-Loop Review and Continuous Learning**

### Elevator Pitch
The project is an end-to-end, AI-driven document processing platform that automatically ingests business documents (invoices, purchase orders, bank statements, forms, and reports) arriving either as email attachments or from a local folder, extracts their content using optical character recognition, classifies them using a large language model (Llama-3.3-70b via the Groq API), retrieves relevant few-shot examples from a vector database (ChromaDB), and then extracts structured financial data according to a fixed JSON schema. Every extracted field carries a machine-generated confidence score; documents where any field falls below an 85% confidence threshold are automatically routed to a human review queue exposed through a Streamlit web interface. When a human reviewer corrects and approves a document, the approved extraction is fed back into ChromaDB as a new few-shot example, creating a continuous self-improvement loop. The platform targets finance, accounts-payable, and operations teams at organisations that receive high volumes of structured business documents and wish to reduce manual data-entry effort, error rates, and processing latency.

### Domain
Business document processing / intelligent automation / Retrieval-Augmented Generation (RAG).

---

## 2. Problem Statement Material

### Manual Process Being Replaced
Before systems like this, accounts-payable and finance teams receive business documents (invoices, POs, bank statements) as email attachments or scanned paper. A human operator must: open each attachment, visually locate key fields (invoice number, vendor, total amount, dates, line items), manually type those values into an ERP or accounting system, and route the document for approval if uncertain.

### Why the Manual Process Is Slow / Error-Prone / Does Not Scale
- **Volume**: A medium-to-large organisation may receive hundreds of invoices per day; linear human effort does not scale.
- **Format variability**: Different vendors use different layouts, fonts, and file types (native PDF, scanned PDF, JPG image). Humans must context-switch constantly.
- **Transcription errors**: Misreading a digit in a total amount or entering a wrong due date can cause late payments, penalties, or audit failures.
- **Lack of audit trail**: Manual processes rarely produce a machine-readable log of who captured what value from which document and when.
- **Scanned documents**: Image-only PDFs require extra effort; humans often skip detail under time pressure.

### What "Done Well" Looks Like
- Near-zero data-entry effort for routine, high-confidence documents.
- Every extraction decision is logged (full audit trail: which model, which confidence, when, what correction was made).
- Low-confidence or ambiguous documents are automatically surfaced to a human, not silently passed through.
- Human corrections are fed back into the retrieval system so the model improves over time without retraining.
- Deduplication ensures documents are never processed twice even if re-submitted via email or folder rescan.
- The system handles both native-text PDFs and scanned/image documents uniformly.

---

## 3. Complete Technology Stack

### Python
- **What it is**: General-purpose, high-level programming language.
- **Version used**: Python 3.10+ (stated in README.md; walrus operator used in storage.py line 40 requires >= 3.8; f-string expressions confirm 3.10+ target).
- **Why chosen**: Dominant language for AI/ML tooling; virtually all required libraries have first-class Python support.
- **Used in**: Every .py file in the project.

### Groq API / Llama-3.3-70b-versatile
- **What it is**: Groq is a cloud inference provider offering extremely fast LLM inference. llama-3.3-70b-versatile is Meta's open-source 70-billion-parameter instruction-following model.
- **Why chosen**: Groq's inference is significantly faster than OpenAI GPT-4 for the same prompts; the model supports JSON-mode structured outputs. The project originally referenced OpenAI (gpt-4o-mini, gpt-4o) in README.md but the code was migrated to Groq. Groq also provides a free API tier suitable for an MVP. The openai==2.45.0 package remains in requirements.txt from the earlier version.
- **Used in**: classification.py (model "llama-3.3-70b-versatile", JSON-mode, classifies into six categories), extraction.py (same model, extracts all schema fields with per-field confidence scores), .env (GROQ_API_KEY stored as environment variable).

### ChromaDB (Vector Database / RAG)
- **What it is**: An open-source, embedded vector database that stores text embeddings and supports semantic similarity search.
- **Why chosen**: Runs entirely locally with persistent disk storage (chroma_db/ directory), requires no external service, and natively supports metadata filtering (used to filter by document_type before similarity ranking). Also explicitly listed as a compliant production choice in README.md.
- **Used in**: retrieval.py (PersistentClient(path="chroma_db"), collection "document_examples", functions: init_few_shot_examples(), get_examples_for_type(), add_example()), pipeline.py (calls init and get functions), app.py (calls add_example() after human approval).

### SQLite (Relational Storage)
- **What it is**: Serverless, file-based SQL relational database.
- **Why chosen**: Zero-configuration, no network dependency, adequate for MVP-scale throughput. WAL (Write-Ahead Logging) journal mode is explicitly enabled (PRAGMA journal_mode=WAL in storage.py).
- **Used in**: storage.py (all CRUD operations, schema migration, deduplication checks, audit logging), app.py (queries via pandas.read_sql_query), db_schema.sql (DDL for all six tables), backfill_hashes.py (one-time migration), cleanup_duplicates.py (one-time cleanup).

### Streamlit
- **What it is**: A Python framework for building data-focused web UIs from pure Python scripts.
- **Version**: streamlit==1.59.2.
- **Why chosen**: Allows rapid construction of a functional review interface without writing HTML/JS/CSS; sufficient for an internal human-review tool.
- **Used in**: app.py — the entire review/management UI (three tabs).

### Tesseract OCR + pdfplumber + PyMuPDF
- **pytesseract** (0.3.13): Python wrapper for Tesseract OCR engine; converts images to text.
- **pdfplumber** (0.11.10): Pure-Python PDF text extraction; works on native (text-embedded) PDFs.
- **PyMuPDF / fitz** (1.28.0): Fast PDF rendering library; used to rasterise scanned PDF pages into PIL images for Tesseract.
- **Why chosen**: Together they form a complete, zero-cost local OCR pipeline. pdfplumber handles native PDFs. When native extraction yields fewer than 50 characters, PyMuPDF rasterises pages and Tesseract reads the images.
- **Used in**: ocr.py — extract_text() dispatches to extract_text_from_pdf() (pdfplumber first, PyMuPDF+Tesseract fallback) or extract_text_from_image() (Tesseract directly).

### Gmail API (OAuth2)
- **What it is**: Google's REST API for reading Gmail mailboxes, authenticated via OAuth 2.0 (gmail.readonly scope).
- **Why chosen**: Automates attachment ingestion directly from a live Gmail inbox; uses standard OAuth2 for security.
- **Libraries**: google-api-python-client==2.198.0, google-auth==2.56.2, google-auth-oauthlib==1.4.0, google-auth-httplib2==0.4.0.
- **Used in**: email_ingestor.py — get_gmail_service() (OAuth2 flow + token refresh), parse_email_headers(), download_attachment(), process_single_message(), run_email_poll(). MIME tree walked recursively (walk_parts() inner function) to handle multipart email structures.

### IMAP (imaplib)
- **What it is**: Standard Internet Message Access Protocol for reading email; uses Python's built-in imaplib.
- **Why chosen**: Provider-agnostic; works with any IMAP-capable mailbox. Configured via environment variables: EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD, EMAIL_FOLDER.
- **Used in**: email_ingestion.py — fetch_unread_email_attachments(), run_email_poller(). Smart filtering: is_likely_document() filters out attachments smaller than 20 KB and filenames matching 12 marketing/logo patterns (icon, logo, banner, social, facebook, twitter, instagram, linkedin, youtube, glassdoor, ibm-black, ibm-logo).

### tenacity (Retry / Backoff Library)
- **What it is**: A Python library providing declarative retry logic with configurable backoff strategies.
- **Version**: tenacity==9.1.4.
- **Why chosen**: LLM API calls are transient-failure-prone (network blips, rate limits). Exponential backoff retry prevents single transient errors from failing an entire document processing job.
- **Configuration used**: stop_after_attempt(3), wait_exponential(multiplier=1, min=2, max=10), retrying on APIError, APIConnectionError, RateLimitError, TimeoutError.
- **Used in**: classification.py (@retry on _call_classification_api()), extraction.py (@retry on _call_extraction_api()).

### python-dotenv
- **Version**: python-dotenv==1.2.2. Loads key-value pairs from .env into os.environ. Used in: classification.py, extraction.py, email_ingestion.py, app.py.

### pandas
- **Version**: pandas==3.0.3. Used in: app.py via pd.read_sql_query() to query SQLite tables and display as Streamlit dataframes.

### reportlab
- **Version**: reportlab==5.0.0. Used in: generate_mocks.py (creates synthetic PDF test documents), email_ingestor.py run_mock_ingestion() (generates mock PDF for demo purposes).

### Pillow (PIL)
- **Version**: pillow==11.3.0. Used in: ocr.py (Image.open() for image files, Image.frombytes() to convert PyMuPDF pixel maps for Tesseract), generate_mocks.py (creates scanned JPG mock document).

### uuid, hashlib, base64 (stdlib)
- **uuid**: storage.py uses str(uuid.uuid4()) to generate document primary keys.
- **hashlib**: storage.py compute_file_hash() uses hashlib.sha256() for deduplication.
- **base64**: email_ingestor.py decodes Gmail attachment binary data; app.py encodes PDFs for inline browser display.

### Other notable packages in requirements.txt

| Package | Version | Role |
|---|---|---|
| openai | 2.45.0 | Legacy dependency (README originally referenced OpenAI; replaced by Groq in actual code) |
| grpcio | 1.82.1 | gRPC transport, required by ChromaDB and OpenTelemetry |
| opentelemetry-* | 1.43.0 | Observability stack pulled in as ChromaDB dependency |
| onnxruntime | 1.27.0 | ChromaDB embedding model inference |
| tokenizers | 0.23.1 | Tokenisation for ChromaDB embedding model |
| altair | 6.2.2 | Charting, pulled in by Streamlit |
| kubernetes | 36.0.3 | ChromaDB dependency for distributed mode |
| mmh3 | 5.2.1 | MurmurHash3, used by ChromaDB for hashing |
| pyarrow | 24.0.0 | Columnar data, used by pandas and ChromaDB |
| re (stdlib) | — | Regex validation in extraction.py validate_extraction() |
| argparse (stdlib) | — | CLI argument parsing in pipeline.py, main.py, email_ingestor.py |

---

## 4. System Architecture — Stage-by-Stage Breakdown

### Stage 0: Initialisation (pipeline.py::main(), main.py)
- **What it does**: Calls init_db() (creates/migrates SQLite tables) and init_few_shot_examples() (seeds ChromaDB with 7 baseline examples if empty).
- **Files**: storage.py, retrieval.py, pipeline.py.
- **Design decision**: ChromaDB is seeded idempotently (if collection.count() > 0: return), so initial state is always predictable without a separate setup script.

### Stage 1: Ingestion (ingestion.py, email_ingestor.py, email_ingestion.py, main.py)

Sub-mode A — Local Folder Scan (ingestion.py): Scans input_docs/ for .pdf, .png, .jpg, .jpeg files. For each file, looks for a companion .json sidecar (e.g., doc1_invoice.json) containing email metadata (sender, subject, received_date). Returns a list of {file_path, metadata} dicts.

Sub-mode B — Gmail API Poller (email_ingestor.py): Authenticates via OAuth2 (gmail.readonly scope, token cached in token.json). Queries Gmail with a configurable search query (default: has:attachment subject:invoice OR subject:receipt...). Downloads valid attachments to input_docs/. MIME tree walked recursively (walk_parts() inner function). Supports single-pass or continuous polling (--poll-interval). Supports --mock-test mode using reportlab to generate a PDF without live credentials.

Sub-mode C — IMAP Poller (email_ingestion.py): Connects to any IMAP server via imaplib.IMAP4_SSL. Fetches UNSEEN messages only; marks processed emails as \Seen after ingestion. is_likely_document() filters out files smaller than 20 KB and 12 marketing-image filename patterns. Decodes MIME-encoded headers via decode_header().

Entry point orchestration (main.py): --source local (default) calls scan_input_folder(); --source email calls fetch_unread_email_attachments() for single pass or run_email_poller() for continuous loop; --force flag bypasses deduplication.

### Stage 2: Deduplication (storage.py)
- **What it does**: Two-layer deduplication before any document is committed to the database.
  - Layer 1 (email message-level): is_email_processed(message_id) checks processed_emails table for the Message-ID header.
  - Layer 2 (file content-level): compute_file_hash(file_path) computes SHA-256 of file bytes in 8 KB chunks. is_duplicate_document(file_hash) checks documents.content_hash (unique index).
- **Why SHA-256**: Collision-resistant; 64-character hex digest fits in a database index; standard library (hashlib), no dependency.
- **Why two layers**: Email dedup alone fails if the same attachment arrives from a different sender/thread. Content-hash dedup alone fails for email-specific tracking. Together they are redundant and thorough.
- **Files**: storage.py, pipeline.py, email_ingestion.py.

### Stage 3: OCR — Text Extraction (ocr.py)
- **What it does**: Extracts raw text from the document file, returning a single string.
- **Decision logic**: (1) If PDF: try pdfplumber native extraction. (2) If fewer than 50 characters returned, fall back to PyMuPDF rasterise + Tesseract. (3) If PNG/JPG/JPEG: run Tesseract directly.
- **Why 50-character threshold**: A native text PDF always has more than 50 characters. Fewer signals image-only PDF, triggering OCR fallback.
- **Output**: Raw text stored in documents.raw_text. Status updated to ocr_completed.

### Stage 4: Classification (classification.py)
- **What it does**: Sends the first 2,000 characters of document text to llama-3.3-70b-versatile in JSON mode.
- **Prompt**: System: "You are a document classification assistant. Output ONLY valid JSON." User: classification task + text.
- **Output categories**: Invoice, Purchase Order, Bank Statement, Form, Report, Other.
- **Response format**: {"document_type": "Invoice", "confidence": 92}.
- **Retry**: @retry with stop_after_attempt(3), exponential backoff 2-10 seconds.
- **Graceful fallback**: If no GROQ_API_KEY, uses keyword matching (INVOICE, PURCHASE ORDER, BANK) with hardcoded confidence values.
- **Output stored to**: documents.document_type, documents.confidence_score.

### Stage 5: RAG Retrieval (retrieval.py)
- **What it does**: Queries ChromaDB for the top-N most semantically similar few-shot examples matching the classified document type.
- **Query mechanism**: collection.query(query_texts=[text[:500]], n_results=effective_n_results, where={"type": document_type}). The where filter pre-filters by document type before semantic ranking.
- **Clamping**: effective_n_results = min(n_results, matching_count) prevents a ValueError when the collection has fewer than n_results matching documents.
- **Default seed examples**: 7 examples covering all 6 categories: ex_invoice_1, ex_po_1, ex_bank_1, ex_bank_2, ex_form_1, ex_report_1, ex_other_1.
- **Human-feedback examples**: After human approval, add_example() upserts a new entry with source="human_approved". Capped at 20 per document type (oldest evicted).
- **Why RAG over static prompts**: Semantic retrieval means the most similar past document is used, not a fixed generic example. Few-shot examples dramatically improve structured extraction accuracy.

### Stage 6: Field Extraction (extraction.py)
- **What it does**: Constructs a system prompt with schema.json, document type, and retrieved examples. Sends document text to llama-3.3-70b-versatile in JSON mode. Receives a structured extraction.
- **Schema**: schema.json — 12 top-level fields, each wrapped in {"value": ..., "confidence_score": int} objects.
- **Post-processing — validate_extraction()**: invoice_date, due_date must match YYYY-MM-DD regex (confidence zeroed on failure); total_amount, tax_amount must be numeric (confidence zeroed on failure); currency must be exactly 3 characters (confidence zeroed on failure).
- **Fail-safe**: If extract_fields() returns an empty dict (all retries exhausted), the document is routed to review queue. This prevents silent failures.
- **Mock mode**: If no GROQ_API_KEY, returns hardcoded mock values with controlled low-confidence scenarios.

### Stage 7: Confidence Routing (pipeline.py::process_document())
- **What it does**: After extraction, iterates over all extracted fields. If any field's confidence_score is below CONFIDENCE_THRESHOLD = 85, the document is routed to the review queue.
- **Why 85%**: High enough to avoid most errors while not being so strict that every document requires review. Defined as a named constant at the top of pipeline.py for easy tuning.
- **Review reason logged**: Human-readable string listing which fields failed and at what confidence (e.g., "Low confidence on fields: total_amount (40%), due_date (0%)").
- **Storage**: route_to_review() in storage.py inserts to review_queue, updates documents.status to review_required, logs to audit_log.

### Stage 8: Human Review (app.py)
- **What it does**: The Streamlit UI's "Needs Review" tab shows pending items. Reviewer sees document preview and editable field form. Fields below 85% are labelled [Low Confidence].
- **Approve & Save — resolve_review()**: Logs changed fields to corrections_log, updates extractions with corrected values (confidence set to 100), marks review_queue entry resolved, sets documents.status to completed, writes audit log entry, calls add_example() for ChromaDB feedback.
- **Reprocess**: Button re-runs process_document() with force=True.

### Stage 9: Continuous Learning (retrieval.py::add_example())
- **What it does**: Every human-approved extraction is stored in ChromaDB with source="human_approved". On the next similar document, this correction is retrieved as a few-shot example.
- **Eviction policy**: Maximum 20 human-approved examples per document type. Oldest deleted when cap is hit.
- **Why this design**: Retraining an LLM requires compute resources and weeks of effort. RAG-based continuous learning achieves similar improvement at inference time.

---

## 5. Database Schema — Full Detail

### Table: documents
| Column | Type | Purpose |
|---|---|---|
| id | TEXT PRIMARY KEY | UUID v4, generated at insert time; FK target for all child tables |
| filename | TEXT NOT NULL | Original filename (e.g., doc1_invoice.pdf) |
| file_path | TEXT NOT NULL | Absolute or relative path to file on disk; used by UI for document preview |
| content_hash | TEXT | SHA-256 hex digest of file bytes; unique index enforces deduplication; added as migration column if not present |
| ingestion_time | DATETIME | Auto-set to CURRENT_TIMESTAMP on insert; used for ordering in UI queries |
| status | TEXT NOT NULL | Pipeline stage marker: processing, ocr_completed, classified, completed, review_required |
| document_type | TEXT | Classification result: Invoice, Purchase Order, Bank Statement, Form, Report, Other |
| confidence_score | INTEGER | Classification confidence 0-100 |
| raw_text | TEXT | Full OCR/extracted text; stored for re-use in add_example() after review |

Relationships: id is referenced as document_id FK in extractions, review_queue, corrections_log, audit_log.

### Table: processed_emails
| Column | Type | Purpose |
|---|---|---|
| message_id | TEXT PRIMARY KEY | Gmail or IMAP Message-ID header; prevents double-processing of same email thread |
| processed_at | DATETIME | Auto-set to CURRENT_TIMESTAMP |
| subject | TEXT | Email subject line; stored for reference/debugging |
| sender | TEXT | Email sender address; stored for reference |

Relationships: No FK; intentionally independent of documents (an email may be skipped without creating a document row).

### Table: extractions
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key |
| document_id | TEXT NOT NULL | FK to documents.id |
| field_name | TEXT NOT NULL | Name of extracted field (e.g., invoice_number, total_amount, line_items) |
| extracted_value | TEXT | Extracted value as string; complex types (lists, dicts) are JSON-serialised via json.dumps() |
| confidence | INTEGER | Per-field confidence score 0-100; post-validate_extraction() value |
| is_valid | BOOLEAN | Set to True on insert; updated to True (with confidence=100) after human correction |

Relationships: FK to documents.id. One document produces multiple rows (one per schema field).

### Table: review_queue
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key; used as queue_id in the UI |
| document_id | TEXT NOT NULL | FK to documents.id |
| reason | TEXT NOT NULL | Human-readable reason for routing (e.g., "Low confidence on fields: total_amount (40%)", "OCR yielded no text", "Extraction failed: no fields returned") |
| added_at | DATETIME | Auto-set to CURRENT_TIMESTAMP |
| status | TEXT DEFAULT 'pending' | pending = awaiting human review; resolved = approved or reprocessed |

Relationships: FK to documents.id.

### Table: corrections_log
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key |
| document_id | TEXT NOT NULL | FK to documents.id |
| field_name | TEXT NOT NULL | Name of the field that was corrected |
| original_value | TEXT | The AI-extracted value before human edit |
| corrected_value | TEXT | The human-corrected value |
| corrected_by | TEXT | Hardcoded to 'human' in current implementation; designed to support named users |
| timestamp | DATETIME | Auto-set to CURRENT_TIMESTAMP |

Relationships: FK to documents.id. Written by log_correction() in storage.py, called from resolve_review() in app.py.

### Table: audit_log
| Column | Type | Purpose |
|---|---|---|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Surrogate key |
| document_id | TEXT NOT NULL | FK to documents.id |
| step | TEXT NOT NULL | Pipeline stage: Ingestion, OCR, Classification, Retrieval, Extraction, Validation, Review, Error |
| action | TEXT NOT NULL | Human-readable description of what happened at this step |
| model_used | TEXT | Intended to record model name; currently passed as None in all calls (parameter is available but not yet populated) |
| confidence | INTEGER | Confidence value at this step if applicable (used for Classification entries) |
| timestamp | DATETIME | Auto-set to CURRENT_TIMESTAMP |
| details | TEXT | Additional free-text detail (e.g., character count for OCR, error message for failures) |

Relationships: FK to documents.id. Written via log_audit() in storage.py at every major pipeline step.

Inter-table relationships summary:
- documents.id is the root FK target
- extractions, review_queue, corrections_log, audit_log all reference documents.id
- processed_emails is standalone (no FK to documents)
- delete_document() in storage.py performs cascading manual delete across all four child tables before deleting from documents

---

## 6. User Flow / Workflow (End-to-End Document Journey, 18 Steps)

1. Arrival: A business document (PDF, JPG, PNG) arrives as an email attachment (Gmail OAuth2 via email_ingestor.py, or IMAP via email_ingestion.py), is placed in input_docs/ folder (local scan mode), or is uploaded directly via the Streamlit "Upload & Manage" tab.
2. Email deduplication check: Pipeline checks processed_emails for the email's Message-ID. If already processed, document is skipped entirely.
3. Content hash deduplication: compute_file_hash() computes the SHA-256 of file bytes. If hash already exists in documents.content_hash, document is skipped.
4. Database insert: insert_document() generates a new UUID, inserts document with status='processing', logs an Ingestion audit entry.
5. Email ID tracking: mark_email_processed() inserts the Message-ID into processed_emails so future polling passes skip it.
6. OCR: extract_text() is called. For native PDFs, pdfplumber extracts text. If fewer than 50 characters returned, PyMuPDF rasterises pages and Tesseract OCR reads the images. For image files, Tesseract runs directly. Raw text stored in documents.raw_text. Status updated to 'ocr_completed'.
7. Empty text check: If OCR returns an empty string, route_to_review(doc_id, "OCR yielded no text") is called and processing stops for this document.
8. Classification: First 2,000 characters of extracted text sent to Groq llama-3.3-70b-versatile. Model returns document_type and confidence integer. Stored in documents.document_type and documents.confidence_score. Status updated to 'classified'.
9. RAG retrieval: get_examples_for_type(document_type, text) queries ChromaDB for up to 3 semantically similar examples of the same document type (using first 500 characters as query vector).
10. Field extraction: extract_fields(text, document_type, examples) builds a prompt with schema.json, document type, and retrieved examples. Groq returns a JSON object with all 12 schema fields, each with value and confidence_score. validate_extraction() cross-checks format validity and zeroes out confidence for invalid values.
11. Empty extraction check: If extract_fields() returns an empty dict (all 3 API retries exhausted), route_to_review(doc_id, "Extraction failed: no fields returned") is called. Document is not marked as completed.
12. Metadata injection: email_metadata (sender, subject, received_date, message_id) is injected into the extraction dict with confidence_score: 100. document_type field also added with its confidence.
13. Extractions saved: insert_extractions() iterates the extraction dict and inserts one row per field into the extractions table. Lists/dicts are JSON-serialised.
14. Confidence routing: All extracted fields are checked. If any field's confidence_score is below 85, document is routed to review_queue with a reason listing all low-confidence fields. Otherwise, documents.status is set to 'completed'.
15. Human review (if routed): Reviewer opens the Streamlit "Needs Review" tab. Selects document from sidebar. Sees document preview (image or embedded PDF) on the left and extracted fields form on the right. Fields below 85% confidence labelled [Low Confidence]. Reviewer edits values and clicks "Approve & Save".
16. Correction logging: resolve_review() logs any changed fields to corrections_log, updates extractions with corrected values (confidence set to 100), marks review_queue entry as 'resolved', sets documents.status to 'completed'.
17. Continuous learning feedback: add_example() stores the approved extraction (raw text + corrected field values) in ChromaDB with source="human_approved". Future documents of the same type will retrieve this real-world example.
18. Final state: Document appears in "Processed" tab with status='completed', all extracted fields in read-only view. Full trail queryable in audit_log and corrections_log.

---

## 7. Frontend / UI Description (app.py, streamlit run app.py)

Page title: "AI Document Processing Platform". Layout: wide. Three tabs with live document counts from the database.

### Tab 1: "Needs Review (N)"
Purpose: Human review queue for low-confidence or failed documents.

What the user sees:
- Sidebar (st.sidebar) listing pending documents as a selectbox (filename + first 8 chars of UUID).
- Header showing selected filename.
- st.warning banner showing the reason the document was flagged.
- "Reprocess Document" button: re-runs full pipeline with force=True if original file is still on disk.
- Two equal columns:
  - Left column: Document preview — image file rendered with st.image; PDF embedded inline in iframe via base64 encoding; otherwise raw text in st.text_area.
  - Right column: "Extracted Data" heading; st.form("review_form") with one st.text_input per field. Fields with confidence below 85 have label prefixed with [Low Confidence].
- "Approve & Save" submit button triggers resolve_review() and st.rerun().

What the user can do: Edit any field value, approve the document (logs corrections and adds to RAG), or reprocess from scratch.

### Tab 2: "Processed (N)"
Purpose: Read-only archive of successfully completed documents.

What the user sees:
- Full-width st.dataframe of all status='completed' documents (columns: id, filename, status, document_type, confidence_score, ingestion_time), ordered newest first.
- st.selectbox to pick a specific document for detail view.
- Two-column layout (same as Tab 1) but right column is read-only: st.dataframe of field_name, extracted_value, confidence, is_valid — no edit inputs.

What the user can do: Browse completed documents, view document previews and extracted data for audit or reference.

### Tab 3: "Upload & Manage (N)"
Purpose: Manual file upload and document lifecycle management.

What the user sees:
- st.file_uploader accepting multiple files (pdf, png, jpg, jpeg).
- "Process Uploaded Files" button saves each file to input_docs/ and runs process_document(). Per-file status shown with st.success (completed), st.warning (routed to review with reason), or st.info / st.error.
- st.dataframe of all documents (any status) with columns: id, filename, status, document_type, confidence_score, ingestion_time.
- st.selectbox to select a document for deletion.
- st.checkbox for deletion confirmation ("Confirm deletion of selected document, its database entries, and file from disk").
- "Delete Selected Document" button calls delete_document() (cascading DB delete + physical file removal) and st.rerun().

What the user can do: Upload new documents, trigger processing, monitor all document statuses, permanently delete documents.

---

## 8. Key Engineering Challenges Solved

### 8.1 Content-Based Deduplication (Preventing Double Processing)
Challenge: Email pollers may revisit the same email across runs; users may upload the same file via both email and the UI; file rescanning may encounter already-processed files.
Solution: SHA-256 content hash stored in documents.content_hash with a unique database index. Pre-insert check via is_duplicate_document() short-circuits processing. Secondary email-level dedup via processed_emails table. Two-layer redundancy covers all ingestion paths.
Files: storage.py, pipeline.py, email_ingestion.py.
Evidence in code: backfill_hashes.py and cleanup_duplicates.py exist as migration/cleanup scripts — direct evidence that deduplication was added after initial development and back-populated into existing records.

### 8.2 Preventing Silent Extraction Failures
Challenge: If the Groq API fails all 3 retries, extract_fields() returns an empty dict {}. An earlier version might have processed this as "no fields extracted = completed successfully" — a silent data-quality failure.
Solution: Explicit guard in pipeline.py (lines 75-78): if not extracted_data: route_to_review(doc_id, "Extraction failed: no fields returned (API error or empty response)"); return. Document is routed to human review rather than auto-completed.
Files: pipeline.py.

### 8.3 ChromaDB n_results Overflow Bug
Challenge: collection.query(n_results=3) raises a ValueError if the collection contains fewer than 3 matching documents (e.g., only 1 example for "Other" type).
Solution: get_examples_for_type() in retrieval.py first counts matching documents with collection.get(where={"type": document_type}), then clamps: effective_n_results = min(n_results, matching_count). Guards against matching_count == 0 with an early return.
Files: retrieval.py.
Comment in code: "Clamps n_results to available matching documents to avoid ChromaDB query errors." (line 148).

### 8.4 Self-Improving RAG via Human Feedback
Challenge: Static few-shot examples cannot cover all document formats seen in production. Retraining an LLM requires significant resources.
Solution: add_example() in retrieval.py upserts human-approved extractions into ChromaDB, tagged source="human_approved". Capped at 20 per document type with LRU-style eviction. Each new document retrieves the most semantically similar real-world example as a shot.
Files: retrieval.py, app.py.

### 8.5 Handling Both Native-Text and Scanned PDFs in One Pipeline
Challenge: The same pipeline receives native PDFs, scanned PDFs (image-only), and standalone image files. Different tools are needed for each.
Solution: extract_text() in ocr.py uses a three-path decision: pdfplumber for native PDFs → PyMuPDF rasterise + Tesseract for scanned PDFs (triggered when native yield is fewer than 50 chars) → Tesseract directly for image files. One unified function interface hides all branching from the caller.
Files: ocr.py.

### 8.6 Marketing Attachment Filtering in IMAP Ingestion
Challenge: Real-world email inboxes contain thousands of tiny marketing images (company logos, social media icons, tracking pixels) as inline attachments. These are not business documents.
Solution: is_likely_document() in email_ingestion.py rejects any attachment smaller than 20 KB (MIN_ATTACHMENT_SIZE = 20 * 1024) and any file whose name matches a list of 12 marketing-image keyword patterns. Only attachments passing both checks are saved and processed.
Files: email_ingestion.py.

### 8.7 Format Validation Cross-Check After LLM Extraction
Challenge: LLMs may return dates in non-standard formats ("January 15, 2024" instead of "2024-01-15") or currency values as strings ("$2500" instead of 2500.0). If passed through unchecked, these silently corrupt the database.
Solution: validate_extraction() in extraction.py applies post-hoc regex/type validation: dates must match YYYY-MM-DD regex; amounts must be int or float; currency code must be exactly 3 characters. Failing fields have confidence_score forced to 0, triggering routing threshold check and sending document to human review.
Files: extraction.py.

### 8.8 Cascading Document Deletion
Challenge: SQLite foreign keys enforce referential integrity; deleting a document without first deleting child rows raises an integrity error. The physical file on disk must also be removed.
Solution: delete_document() in storage.py manually deletes rows from extractions, review_queue, audit_log, and corrections_log in the correct order before deleting from documents. Then optionally removes the physical file. The delete_file=False variant is used by cleanup_duplicates.py to remove only DB records for legacy duplicates whose files should not be deleted.
Files: storage.py.

### 8.9 SQLite WAL Mode for Concurrent Access
Challenge: The Streamlit UI and the pipeline can both write to the database simultaneously (e.g., user approves a document while a background email poll is running). Default SQLite journal mode uses file-level locks causing write collisions.
Solution: PRAGMA journal_mode=WAL enabled in init_db(). WAL mode allows concurrent readers and one writer, reducing lock contention. Connection uses timeout=30.0 and isolation_level=None (autocommit).
Files: storage.py.

---

## 9. Screenshots / Artifacts Available

### 9.1 Architecture Flowcharts (Recreatable from Codebase)
Three logical sub-system flowcharts can be drawn for the report:
1. Ingestion and Deduplication Pipeline — three ingestion paths (Local Folder scan via ingestion.py, Gmail API via email_ingestor.py, IMAP via email_ingestion.py), two-layer dedup check, document DB insert.
2. Processing Pipeline — OCR (ocr.py) → Classification (classification.py) → RAG Retrieval (retrieval.py) → Extraction (extraction.py) → Validation → Confidence Routing → Completed or Review Queue.
3. Review and Continuous Learning Loop — Streamlit review UI (app.py), human correction, correction logging to corrections_log, ChromaDB add_example() feedback loop back into RAG retrieval.

### 9.2 Mock Test Documents
generate_mocks.py creates 5 test documents in input_docs/:
- doc1_invoice.pdf — native PDF invoice (FastTech Solutions, Invoice #9901, $2500.00)
- doc2_po.pdf — native PDF purchase order (OfficeSupplies Co, PO-4432, $150.00)
- doc3_scanned.jpg — simulated scanned image invoice (OldSchool Paperworks, Invoice #7788, $450.00)
- doc4_bank.pdf — bank statement (Jane Doe, ending balance $4800.00)
- doc5_malformed.pdf — intentionally confusing "Internal Memo / pizza" document to test low-confidence routing

One additional test image exists in input_docs/: basic-invoice-template.png.

### 9.3 Streamlit UI Screenshots
The UI running via streamlit run app.py produces three distinct screens that can be screenshot:
1. Tab 1 — Needs Review: Sidebar with pending document selectbox; two-column layout with embedded PDF/image preview and editable field form with [Low Confidence] labels.
2. Tab 2 — Processed: Full-width sortable dataframe of completed documents + two-column detail view with read-only extraction table.
3. Tab 3 — Upload and Manage: Multi-file uploader, per-file processing status, full document list dataframe, delete controls with confirmation checkbox.

### 9.4 Database Schema Diagram
The db_schema.sql file contains the full DDL for all 6 tables with their FK relationships — suitable for generating an ER diagram with any standard diagramming tool.

---

## 10. Limitations and Future Scope

### Current Limitations

**1. RAG Example Coverage is Limited at Baseline**
ChromaDB collection seeds with only 7 static examples (one to two per document type). For novel document layouts not yet seen in the system, initial few-shot quality may be poor. Coverage grows organically as documents are approved through the review UI, but early-stage deployment requires more manual review than steady-state operation.

**2. Email Ingestion Under Real-World Conditions**
Both email_ingestor.py (Gmail OAuth2) and email_ingestion.py (IMAP) are functionally implemented but tested primarily in mock/controlled conditions. Real-world mailboxes contain edge cases: nested multipart MIME structures, email threading, attachments in non-standard encodings, very large files, or non-UTF-8 headers.

**3. OCR Quality for Complex Layouts**
Tesseract OCR performs well on clean, plain-text scans but degrades on multi-column layouts, tables, forms with checkboxes, or low-resolution images. The current threshold (fewer than 50 characters) that triggers the OCR fallback is a heuristic, not a guaranteed quality gate.

**4. Single Unified Extraction Schema**
schema.json uses a single unified schema for all document types. Some fields are irrelevant for certain types (e.g., invoice_number for a bank statement is always null). A per-type schema would improve extraction accuracy and reduce unnecessary null fields.

**5. No User Authentication**
The Streamlit UI has no login or access control. Any user on the network can access, modify, or delete documents. The corrected_by field in corrections_log is hardcoded to 'human' rather than a named user.

**6. Local Storage Only**
Documents are stored as local files and SQLite on disk. Not suitable for multi-user, distributed, or cloud-hosted deployments without migration to cloud storage and a cloud database.

### Future Scope

**1. Production-Grade OCR**
Replace pytesseract and pdfplumber with Azure AI Document Intelligence (or Google Document AI), which provides layout-aware text extraction with bounding box coordinates, enabling text-region highlighting in the review UI.

**2. Per-Document-Type Schemas**
Define a separate JSON schema for each document type (Invoice, PO, Bank Statement, etc.) to avoid schema mismatch noise and improve LLM extraction precision.

**3. Broader Document Type Support**
Extend classification categories beyond the current six: contracts, shipping manifests, tax forms, payslips, insurance documents, etc.

**4. Named User Authentication and Role Management**
Integrate OAuth2 (e.g., Google Sign-In or Azure AD) so reviewer identity is captured in corrections_log.corrected_by. Add role-based access (reviewer vs. admin vs. read-only).

**5. Production Infrastructure Migration**
Local SQLite → Azure SQL or Cosmos DB. Local file storage → Azure Blob Storage. Streamlit UI → React + FastAPI for a production-grade, embeddable web application. ChromaDB local → ChromaDB hosted or Azure AI Search for multi-instance deployment.

**6. Analytics and Reporting Dashboard**
Add a dashboard showing: documents processed per day, average confidence scores by document type, most frequently corrected fields, review queue age, and RAG example growth over time.

**7. Webhook / Real-Time Ingestion**
Replace polling with event-driven ingestion (Gmail Push Notifications or Microsoft Graph webhooks) to reduce latency from email arrival to processing from minutes to seconds.

**8. Confidence Score Calibration**
The 85% threshold is a fixed constant. A future version could learn per-field or per-document-type thresholds from the corrections_log (e.g., if total_amount corrections are rare above 70%, lower its threshold accordingly).

---
*End of source material. Ready to be used as the basis for writing the formal Dronacharya College of Engineering B.Tech training report chapters.*
