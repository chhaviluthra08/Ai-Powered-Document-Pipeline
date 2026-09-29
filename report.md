# AI Document Processing Platform
## A Retrieval-Augmented, Human-in-the-Loop Intelligent Document Intelligence System

---

**Course Submission Report**
**Subject:** Intelligent Systems / Applied Artificial Intelligence
**Date:** July 2026

---

## Abstract

This report presents the design, architecture, and implementation of an AI-powered Document Processing Platform — an end-to-end intelligent system capable of automatically ingesting business documents from multiple sources, extracting structured data from them using large language models (LLMs), and improving over time through a continuous learning mechanism driven by human feedback. The platform addresses a pervasive operational challenge in enterprise environments: the manual, error-prone, and labour-intensive process of entering data from physical and digital documents such as invoices, purchase orders, bank statements, and financial forms into structured databases. The system combines Optical Character Recognition (OCR), LLM-based document classification, Retrieval-Augmented Generation (RAG), schema-constrained structured extraction, and a Streamlit-based human review interface to create a robust pipeline that is both highly automated and thoroughly auditable. By feeding human-verified corrections back into the RAG example set, the platform implements a closed-loop learning mechanism that progressively improves extraction accuracy over time without requiring manual retraining of any model.

---

## 1. Problem Statement

Businesses of all scales routinely receive large volumes of documents — invoices from vendors, purchase orders from clients, bank statements from financial institutions, expense reimbursement forms from employees, and quarterly financial reports. The data contained within these documents must typically be transcribed into structured records in enterprise resource planning (ERP) systems, accounting platforms, or internal databases.

This transcription process is almost universally performed manually. Human data entry operators read each document, identify relevant fields (such as vendor name, invoice total, or due date), and key the information into a system. This approach suffers from three fundamental limitations:

1. **Scale constraints.** Manual data entry cannot keep pace with large or growing document volumes without proportionally increasing headcount. Processing speed is bounded by the number of available operators.

2. **Error proneness.** Human transcription introduces typographic errors, field misidentifications, and omissions at a non-trivial rate. These errors propagate into downstream financial and operational systems, where they are costly to detect and correct.

3. **Lack of adaptability.** Manual processes do not improve automatically. The institutional knowledge that an experienced operator builds about common document formats is not transferable without explicit training, and is lost entirely if the operator leaves.

The ideal solution is an intelligent system capable of reading documents in arbitrary formats (native digital PDFs, scanned images, email attachments), understanding their content well enough to classify and extract structured fields, flagging uncertain extractions for human review, and — critically — learning from every human correction to improve future performance automatically. This is the problem this platform is designed to solve.

---

## 2. Objectives

The system was designed to fulfil the following explicit objectives:

- **Multi-source automatic ingestion:** Accept documents from a local file system folder and from a live Gmail inbox, without requiring manual intervention for each document.
- **Robust OCR:** Extract raw text from both native-text PDFs and scanned (image-based) documents, with intelligent fallback from native extraction to Tesseract OCR for low-yield PDFs.
- **AI-powered classification:** Automatically identify the document type (Invoice, Purchase Order, Bank Statement, Form, Report, or Other) using a large language model, with a self-reported confidence score.
- **Retrieval-Augmented Generation (RAG):** Retrieve semantically relevant few-shot extraction examples from a vector database to guide the LLM during structured data extraction, improving accuracy and consistency.
- **Schema-constrained structured extraction:** Extract a standardised set of business fields from each document in a machine-readable JSON format that conforms to a predefined schema, with per-field confidence scores and format validation.
- **Confidence-based routing:** Automatically route documents to human review when any extracted field falls below a configurable confidence threshold, and mark documents as completed without human intervention when all fields exceed the threshold.
- **Human-in-the-loop review and correction:** Provide a graphical user interface through which human operators can review flagged documents, inspect low-confidence fields, and apply corrections.
- **Continuous learning:** Feed every human-approved extraction back into the ChromaDB vector store as a new few-shot example, so that future documents of the same type benefit from accumulated real-world corrections.
- **Content-hash deduplication:** Prevent the same physical document from being processed multiple times, regardless of how it entered the system.
- **Full audit trail:** Record every step of every document's lifecycle — ingestion, OCR, classification, retrieval, extraction, routing decision, and human review — in a structured audit log for compliance and debugging.

---

## 3. System Architecture

The platform is organised as a sequential processing pipeline in which each stage consumes the output of the previous one. The following sections describe each stage in detail.

### 3.1 High-Level Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        INGESTION LAYER                           │
│  ┌─────────────────────┐       ┌───────────────────────────────┐ │
│  │  Folder Scanner     │       │   Gmail API Ingestor          │ │
│  │  (ingestion.py)     │       │   (email_ingestor.py)         │ │
│  │  Scans input_docs/  │       │   OAuth2, polls inbox,        │ │
│  │  for PDF/PNG/JPG    │       │   downloads attachments       │ │
│  └──────────┬──────────┘       └──────────────┬────────────────┘ │
└─────────────┼──────────────────────────────────┼─────────────────┘
              │                                  │
              └──────────────┬───────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │         DEDUPLICATION            │
              │   SHA-256 content hash check     │
              │   + email message_id check       │
              │   (storage.py)                   │
              └──────────────┬───────────────────┘
                             │ (new document only)
                             ▼
              ┌──────────────────────────────────┐
              │         OCR STAGE                │
              │   pdfplumber (native PDF text)   │
              │   ↓ fallback if <50 chars        │
              │   PyMuPDF rasterise + Tesseract  │
              │   Tesseract (images: PNG/JPG)    │
              │   (ocr.py)                       │
              └──────────────┬───────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │      CLASSIFICATION STAGE        │
              │   Groq API / Llama-3.3-70b       │
              │   Returns: document_type +       │
              │            confidence score      │
              │   (classification.py)            │
              └──────────────┬───────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │     RAG RETRIEVAL STAGE          │
              │   ChromaDB vector query          │
              │   Retrieves up to 3 semantically │
              │   similar examples for doc type  │
              │   (retrieval.py)                 │
              └──────────────┬───────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │       EXTRACTION STAGE           │
              │   Groq API / Llama-3.3-70b       │
              │   JSON mode, schema-constrained  │
              │   Few-shot examples in prompt    │
              │   Per-field confidence scores    │
              │   Post-extraction validation     │
              │   (extraction.py)                │
              └──────────────┬───────────────────┘
                             ▼
              ┌──────────────────────────────────┐
              │   CONFIDENCE ROUTING STAGE       │
              │   Threshold: 85%                 │
              │   Any field below → review queue │
              │   All fields above → completed   │
              │   (pipeline.py)                  │
              └──────────┬───────────────────────┘
                         │                │
                         ▼                ▼
           ┌─────────────────┐   ┌──────────────────────┐
           │  review_queue   │   │  documents.status     │
           │  (SQLite)       │   │  = 'completed'        │
           └────────┬────────┘   └──────────────────────┘
                    ▼
        ┌───────────────────────────────┐
        │    STREAMLIT REVIEW UI        │
        │    (app.py)                   │
        │    Human inspects fields,     │
        │    edits values, approves     │
        └───────────────┬───────────────┘
                        ▼
        ┌───────────────────────────────┐
        │  CONTINUOUS LEARNING LOOP     │
        │  Approved extraction → upsert │
        │  into ChromaDB as new example │
        │  (retrieval.add_example)      │
        └───────────────────────────────┘
```

### 3.2 Data Storage Layer

All persistent state is maintained in two stores:

- **SQLite (`platform.db`):** Structured relational store for document records, extracted field values, the human review queue, audit logs, correction history, and email deduplication records. Write-ahead logging (WAL mode) is enabled to support concurrent reads and writes.
- **ChromaDB (`chroma_db/`):** Persistent vector store for few-shot RAG examples. Documents are stored alongside their metadata and embeddings, enabling semantic similarity queries.

---

## 4. Technology Stack

| Technology | Role | Justification |
|---|---|---|
| **Python 3.12** | Core implementation language | Rich ecosystem for AI/ML libraries; strong support for all required integrations |
| **Groq API (Llama-3.3-70b-versatile)** | Document classification and structured field extraction | Fast inference, JSON mode support for schema-constrained output, cost-effective for high-volume document processing |
| **ChromaDB 1.5.x** | Vector database for RAG few-shot examples | Lightweight, embeddable, persistent; no separate server required; native semantic similarity via embeddings |
| **SQLite** | Relational database for all structured document data | Zero-configuration, serverless, sufficient for the document volumes targeted; WAL mode provides concurrency safety |
| **Streamlit 1.59** | Human review web interface | Rapid deployment of interactive data applications in Python; no front-end engineering required |
| **Tesseract OCR 5.5** | Text extraction from scanned images and image-only PDFs | Industry-standard open-source OCR engine; high accuracy on clean document scans |
| **pdfplumber 0.11** | Native text extraction from digital PDFs | Accurate positional text extraction from PDF objects without rasterisation overhead |
| **PyMuPDF (fitz)** | Rasterisation of scanned PDFs for Tesseract | Converts PDF pages to images when native text extraction fails, enabling Tesseract fallback |
| **Google APIs (gmail)** | Live email inbox polling and attachment downloading | Official Google API client library for OAuth2-authenticated Gmail access |
| **python-dotenv** | Environment variable management | Secures sensitive credentials (API keys, OAuth tokens) out of source code |
| **tenacity** | Retry logic for all LLM API calls | Exponential backoff on transient API errors (rate limits, connection failures) prevents pipeline crashes |

---

## 5. Key Modules and Features

### 5.1 Ingestion Layer (`ingestion.py`, `email_ingestor.py`)

The ingestion layer provides two complementary document intake mechanisms.

**Folder-based ingestion** (`ingestion.py`) scans a designated `input_docs/` directory for files with extensions `.pdf`, `.png`, `.jpg`, or `.jpeg`. For each document, it looks for a companion `.json` metadata file containing sender, subject, and received-date fields, which are ingested alongside the document content and stored as part of the extraction output. This approach simulates an email attachment inbox for development and testing environments.

**Gmail API ingestion** (`email_ingestor.py`) connects to a live Gmail account via OAuth2 and queries the inbox using a configurable search filter. It recursively walks the MIME tree of matching messages to find document attachments, downloads them to the local file system, and routes each to the processing pipeline along with the parsed email headers (sender, subject, received date, and message ID). The module supports both a single-pass mode and a continuous polling loop with a configurable interval. A `--mock-test` flag allows end-to-end testing of the email path without live Gmail credentials.

Both paths converge at the `process_document()` function in `pipeline.py`, which is the single entry point into the processing pipeline.

### 5.2 Content Deduplication (`storage.py`)

Before a document is inserted into the database, the system computes its SHA-256 content hash using an 8 KB streaming read. This hash is checked against the `content_hash` column of the `documents` table. If a matching hash is found, the document is skipped as a duplicate without being reprocessed.

For email-sourced documents, a secondary deduplication check is performed using the Gmail `message_id` header. This prevents the same email from being processed again if it matches the search query in a subsequent polling cycle, even if the attachment binary has changed.

The `--force` flag in `pipeline.py` bypasses both deduplication checks, which is useful for reprocessing documents after schema changes or pipeline updates.

### 5.3 OCR Pipeline (`ocr.py`)

The OCR module implements a two-tier text extraction strategy:

1. **Native PDF extraction** using `pdfplumber`, which reads the text objects embedded in the PDF structure directly. This is fast, accurate, and preserves formatting for digitally-created documents.
2. **Scanned document fallback** using `PyMuPDF` (fitz) to rasterise each page at full resolution, followed by `Tesseract OCR` to extract text from the resulting images. This path is triggered automatically when native extraction yields fewer than 50 characters — a reliable heuristic for detecting image-only PDFs.

For `.png`, `.jpg`, and `.jpeg` files, Tesseract is invoked directly via the `pytesseract` wrapper around Pillow image loading.

### 5.4 AI Document Classification (`classification.py`)

Document classification is performed by submitting the first 2,000 characters of the extracted text to the Groq API using the Llama-3.3-70b-versatile model. The model is prompted in JSON mode and instructed to return a single JSON object containing two fields: `document_type` (one of six enumerated categories: Invoice, Purchase Order, Bank Statement, Form, Report, Other) and `confidence` (an integer from 0 to 100).

The prompt instructs the model to act as a document classification assistant and to output only valid JSON, leveraging the Groq API's `response_format: json_object` constraint to guarantee parseable output. All API calls are wrapped in a `tenacity` retry decorator configured for three attempts with exponential backoff (2–10 seconds) on transient errors including rate limits, connection failures, and timeouts.

### 5.5 Retrieval-Augmented Generation (`retrieval.py`)

Before extraction is attempted, the system queries a ChromaDB collection named `document_examples` for semantically similar documents of the same type. This collection is pre-seeded with seven high-quality, human-authored examples spanning all six document categories, each containing representative document text paired with a complete, correctly structured extraction in the target schema format.

The query uses the first 500 characters of the current document's text as the semantic query vector and retrieves up to three matching examples, filtered by document type using ChromaDB's metadata filtering. These examples are included in the extraction prompt, providing the LLM with concrete demonstrations of the expected input-output mapping for the specific document category it is processing.

This RAG approach addresses a key limitation of zero-shot extraction: LLMs benefit significantly from concrete examples of the desired output format and field semantics, particularly for domain-specific business documents where field names may be ambiguous (e.g., the distinction between `invoice_date` and `due_date` in various document layouts).

The `n_results` parameter is clamped to the number of available matching examples using a pre-query count check, avoiding a known ChromaDB error that occurs when the requested result count exceeds the collection size.

### 5.6 Schema-Constrained Structured Extraction (`extraction.py`, `schema.json`)

Field extraction is performed by a second Groq API call in JSON mode. The extraction prompt includes the full JSON Schema definition from `schema.json`, the document type identified in the classification stage, and the few-shot examples retrieved from ChromaDB. The model is instructed to return a JSON object conforming exactly to the schema — with every field including both a `value` and a `confidence_score` between 0 and 100.

The schema defines eleven top-level fields:

| Field | Type | Description |
|---|---|---|
| `document_type` | string (enum) | Classification result |
| `invoice_number` | string or null | Document identifier |
| `invoice_date` | string (YYYY-MM-DD) or null | Document date |
| `vendor_name` | string or null | Issuing organisation |
| `customer_name` | string or null | Receiving party |
| `purchase_order_number` | string or null | Associated PO reference |
| `total_amount` | number or null | Total monetary value |
| `tax_amount` | number or null | Tax component |
| `currency` | string (3-letter ISO) or null | Currency code |
| `due_date` | string (YYYY-MM-DD) or null | Payment due date |
| `line_items` | array of objects or null | Itemised transaction details |
| `email_metadata` | object | Source email provenance |

After the model returns the extraction, a `validate_extraction()` function cross-checks self-reported confidence scores against deterministic format rules: dates are validated against the `YYYY-MM-DD` regular expression, numeric fields are checked to be of type `int` or `float`, and currency codes are checked to be exactly three characters. If a field fails its format validation, its `confidence_score` is set to zero, overriding the model's self-assessment and ensuring the document is routed to human review regardless of the model's stated certainty.

### 5.7 Confidence-Based Routing (`pipeline.py`)

Once extraction is complete, every field in the extracted output is checked against a configurable confidence threshold of 85%. If any single field's `confidence_score` falls below this threshold, the document is inserted into the `review_queue` table with a detailed reason string listing all offending fields and their scores. The document's status is set to `review_required`. If all fields meet or exceed the threshold, the document's status is set to `completed` without requiring any human action.

This routing decision is intentionally conservative: a single uncertain field is sufficient to trigger human review. This design prioritises accuracy over throughput, reflecting the business cost of an undetected extraction error propagating into a financial system.

### 5.8 Human-in-the-Loop Review Interface (`app.py`)

The Streamlit web application provides a three-tabbed interface:

- **Needs Review:** Lists all documents currently pending in the review queue. The reviewer selects a document from the sidebar and sees the original document (rendered as a PDF iframe or image) alongside an editable form showing each extracted field labelled with its confidence score. Fields with confidence below 85% are prefixed with `[Low Confidence]` to draw attention. The reviewer can correct any field value directly in the form and click **Approve & Save** to finalise the document.

- **Processed:** Displays all documents that have been marked as completed, either automatically by the pipeline or by a human reviewer. Each document's extraction results are shown in a read-only table.

- **Upload & Manage:** Provides a file uploader accepting PDF, PNG, JPG, and JPEG files. Uploaded documents are saved to the `input_docs/` folder and immediately submitted to `process_document()` for processing. The full document table is displayed, and individual documents can be permanently deleted from both the database and the file system.

### 5.9 Continuous Learning Mechanism (`retrieval.py`, `app.py`)

The continuous learning loop is the mechanism by which the system improves over time. Each time a human operator approves a document in the **Needs Review** tab, the platform executes the following additional step after recording the corrections and updating the document status:

1. The document's `raw_text` and `document_type` are retrieved from the `documents` table.
2. The final approved field values (post-correction) are read from the `extractions` table and assembled into the schema-compliant dictionary format used by the existing seed examples.
3. The `add_example()` function in `retrieval.py` is called with the document type, raw text, extraction dictionary, and document ID.
4. `add_example()` performs a ChromaDB `upsert` operation using the key `human_{doc_id}`. This ensures that re-approving the same document after reprocessing overwrites the previous entry rather than creating a duplicate.
5. Before inserting, the function counts the number of existing `human_approved` examples for the document type. If the count is 20 or greater, the oldest human-approved example for that type is deleted, enforcing a sliding-window cap that prevents unbounded growth of the ChromaDB collection.

The `add_example()` call is wrapped in a `try-except` block in `app.py`, ensuring that a failure in this non-critical step never blocks or rolls back the approval itself.

By incorporating human-verified extractions as first-class retrieval examples, the system closes the learning loop: each approval makes future extractions of the same document type more accurate, without requiring any explicit model fine-tuning or retraining.

### 5.10 Audit Logging and Correction History (`storage.py`)

Every significant action during a document's lifecycle is recorded in the `audit_log` table, including the pipeline step name, a human-readable action description, the model used (if applicable), the confidence score at that step, and any additional details. This produces a complete, timestamped record of how every document was processed, which steps it passed through, and what decisions were made at each stage.

Human corrections are additionally recorded in the `corrections_log` table, which stores the original extracted value, the corrected value, and the identity of the corrector (defaulting to `'human'`). This log provides a granular history of where the AI extraction pipeline made errors and what the correct values were, which can be used for performance monitoring and future analysis.

---

## 6. Database Design

The platform uses a SQLite relational database with six tables:

| Table | Purpose |
|---|---|
| `documents` | Master record for each ingested document. Contains filename, file path, content hash (for deduplication), ingestion timestamp, current status, classified document type, overall confidence score, and full raw extracted text. |
| `extractions` | One row per extracted field per document. Stores field name, extracted value (serialised to text for complex types), confidence score, and validity flag. |
| `review_queue` | Tracks documents awaiting human review. Contains a foreign key to `documents`, the reason for routing, the timestamp of routing, and the status (`pending` or `resolved`). |
| `corrections_log` | Immutable record of every human correction applied during review. Stores original value, corrected value, field name, corrector identity, and timestamp. |
| `audit_log` | Append-only log of every pipeline action. Each row records the document ID, pipeline step, action description, model used, confidence at that step, and a details string. |
| `processed_emails` | Deduplication table for email-sourced documents. Stores the Gmail `message_id`, sender, subject, and processing timestamp to prevent duplicate ingestion across polling cycles. |

Foreign key constraints are enforced at the SQLite level (via `PRAGMA foreign_keys = ON`) and the database operates in WAL (Write-Ahead Logging) journal mode to handle concurrent reads from the Streamlit application while pipeline writes are in progress.

---

## 7. End-to-End Workflow

The following describes the complete journey of a document through the system, from arrival to final storage.

**Step 1 — Arrival.** A document arrives either by being placed in the `input_docs/` folder or as an email attachment in the connected Gmail inbox. The ingestion module detects it during the next scan or poll cycle.

**Step 2 — Deduplication.** The system computes a SHA-256 hash of the document's binary content and checks it against previously processed documents. For email-sourced documents, the Gmail `message_id` is additionally checked. If the document is a duplicate, it is skipped silently.

**Step 3 — Database registration.** A new row is inserted into the `documents` table with `status = 'processing'` and a UUID primary key. The document's metadata (source email sender, subject, received date) is carried forward for later storage in the extractions.

**Step 4 — OCR.** The text extraction module attempts native PDF parsing (for PDFs) or direct Tesseract OCR (for images). For PDFs that yield fewer than 50 characters from native extraction, PyMuPDF rasterises the pages and Tesseract is applied to the resulting images. The extracted text is stored in `documents.raw_text` and the document status advances to `ocr_completed`.

**Step 5 — Classification.** The first 2,000 characters of the extracted text are submitted to the Groq LLM, which returns a document type and a confidence score. The result is stored in the `documents` table (`document_type`, `confidence_score`) and the status advances to `classified`.

**Step 6 — RAG retrieval.** The system queries ChromaDB for the top-3 most semantically similar examples of the identified document type, using the document text as the query vector. These examples (text snippet + structured extraction pairs) are assembled for inclusion in the extraction prompt.

**Step 7 — Extraction.** A second LLM call, incorporating the JSON Schema, the document type, and the retrieved examples, extracts all defined fields. The model returns per-field values and confidence scores. A post-extraction validator overrides confidence scores for fields that fail deterministic format checks (date format, numeric type, currency code length).

**Step 8 — Routing.** The pipeline evaluates every field's confidence score. If all scores are 85% or above, the document is marked `completed`. If any score falls below the threshold, the document is inserted into `review_queue` with a reason string listing the offending fields, and its status is set to `review_required`.

**Step 9 — Human review (conditional).** Documents in `review_required` appear in the Streamlit **Needs Review** tab. The reviewer can read the original document alongside the extracted fields, edit any values, and click **Approve & Save**. Changed fields are logged in `corrections_log`, the extraction values in the database are updated to the corrected values with confidence set to 100, and the document status is advanced to `completed`.

**Step 10 — Continuous learning.** After approval, the platform automatically adds the final approved extraction to ChromaDB as a new `human_approved` few-shot example for that document type. This example will be retrieved by the RAG stage when future documents of the same type are processed, closing the learning loop.

---

## 8. Conclusion

The AI Document Processing Platform demonstrates that a highly capable document intelligence pipeline can be constructed by integrating modern large language model APIs, vector databases, and traditional OCR tooling within a well-structured Python application. The system eliminates the need for manual document triage and initial data entry for the majority of documents — those for which all fields can be extracted with sufficient confidence — while preserving human oversight for the cases where automation is uncertain.

The continuous learning mechanism is a particularly significant architectural feature: rather than treating the AI system as a static tool, the platform treats every human correction as a training signal. Over time, as human reviewers approve more documents of each type, the RAG example set grows richer and more representative of the real documents the system encounters in production. This progressively reduces the fraction of documents that require human review, without requiring expensive model retraining or manual prompt engineering.

The full audit trail — recording every pipeline step for every document — provides the transparency and traceability required for business and regulatory compliance, making the system suitable for deployment in regulated domains such as financial services and healthcare administration.

---

## 9. Future Scope

The current implementation lays a strong foundation that can be extended in several natural directions as requirements evolve:

- **Production-grade OCR integration.** The current Tesseract-based OCR performs well on clean scans but can struggle with low-resolution, skewed, or heavily formatted documents. Integrating a managed cloud OCR service such as Azure AI Document Intelligence or Google Document AI would substantially improve accuracy on such inputs, particularly for structured forms with complex layouts.

- **Expanded document type support.** The current taxonomy covers six broad categories. Many business verticals require more granular classification — for example, distinguishing between credit notes, proforma invoices, and tax invoices within the Invoice category. Expanding the schema and example set to cover domain-specific sub-types would increase the platform's applicability.

- **Adaptive confidence thresholds.** The current 85% confidence threshold is applied uniformly across all document types and fields. A more sophisticated routing policy might set lower thresholds for fields that are routinely difficult to extract (e.g., line items in non-standard invoice layouts) while maintaining higher standards for high-stakes fields such as total amount.

- **Active learning and example quality ranking.** The current continuous learning mechanism adds human-approved examples on a first-in, first-out basis with a simple count cap. A more sophisticated approach might rank stored examples by their measured impact on extraction accuracy, preferring examples that cover unusual document layouts or edge cases over examples that duplicate already-well-covered patterns.

- **Real-time pipeline triggering.** The current architecture operates in a polling mode. A production deployment could integrate with an event-driven messaging system (such as Google Pub/Sub or AWS SQS) to trigger document processing immediately upon receipt, reducing end-to-end latency for time-sensitive documents such as payment-due invoices.

- **Role-based access control and multi-user review.** The current Streamlit interface does not enforce authentication or reviewer assignment. Adding user authentication and a queue assignment model would allow the platform to scale across multiple reviewers in a department, with workload distribution and per-reviewer audit trails.

---

*End of Report*
