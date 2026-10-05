# AI-Powered Document Processing Platform

This project is a minimum viable product (MVP) for an end-to-end AI-powered document processing platform. It ingests simulated email attachments, extracts and classifies text, extracts structured data according to a fixed schema, evaluates confidence, and provides a human-in-the-loop review interface.

## Quick Start

1. Ensure Python 3.10+ is installed.
2. Install dependencies: `pip install -r requirements.txt` (or install manually: `google-api-python-client google-auth-oauthlib tenacity openai chromadb pytesseract pdfplumber pymupdf streamlit pydantic python-dotenv`).
3. Set your OpenAI API Key: `export OPENAI_API_KEY="your-api-key"`
4. Place sample documents (PDF, JPG, PNG) and their optional metadata JSON files in `input_docs/`.
5. Run the pipeline: `python pipeline.py`
6. Run the review UI: `streamlit run app.py`

## Gmail Ingestion (`email_ingestor.py`)

The platform includes an automated Gmail API ingestion poller using OAuth2 (`gmail.readonly`).

### Gmail OAuth Setup
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project, enable the **Gmail API**, and configure an OAuth Consent Screen.
3. Create an **OAuth 2.0 Client ID** (Desktop Application) and download `credentials.json` into the root directory of this repository.

### Running the Email Ingestor
- **Single Polling Pass**:
  ```bash
  python email_ingestor.py
  ```
- **Continuous Polling Loop** (e.g. check every 60 seconds):
  ```bash
  python email_ingestor.py --poll-interval 60 --query "has:attachment (subject:invoice OR subject:statement)"
  ```
- **Mock Test Mode** (No credentials required):
  ```bash
  python email_ingestor.py --mock-test
  ```


## Architecture & Production Substitutions

This MVP was built over 2 days using local and free equivalents to accelerate development without incurring cloud resource provisioning delays. The system is designed so that swapping these components for their Azure equivalents is primarily a configuration or single-function change.

Here are the exact substitutions made and how to transition them to production:

### 1. Ingestion
- **MVP**: Local folder watcher (`ingestion.py`) simulating email drops. Reads `.json` sidecar files for email metadata.
- **Production**: Microsoft Graph API.
- **How to migrate**: Replace the `scan_input_folder` function to authenticate with Azure AD, subscribe to an Outlook inbox webhook, download attachments, and extract real email metadata natively.

### 2. OCR / Text Extraction
- **MVP**: `pytesseract` (Tesseract) for images/scanned PDFs, `pdfplumber` / `PyMuPDF` for native PDFs (`ocr.py`).
- **Production**: Azure AI Document Intelligence.
- **How to migrate**: Replace the `extract_text` function in `ocr.py` to call the `DocumentAnalysisClient`. This will yield significantly better layout-aware text extraction natively, reducing the need for format-specific handling.

### 3. Classification & Extraction (LLM)
- **MVP**: Direct OpenAI API calls (`gpt-4o-mini`, `gpt-4o`) via the official `openai` python package.
- **Production**: Azure OpenAI Service.
- **How to migrate**: Change the client initialization in `classification.py` and `extraction.py` to use `AzureOpenAI` instead of `OpenAI`. Update the endpoint and keys in the environment. The actual function calling and JSON mode payload structure remains identical.

### 4. Few-Shot Retrieval (RAG)
- **MVP**: ChromaDB (local persistence).
- **Production**: ChromaDB, Azure AI Search, Pinecone, or FAISS.
- **Note**: ChromaDB is explicitly permitted as a compliant choice for production in the requirements. No strict substitution is required, but it can be easily hosted or swapped for Azure AI Search by updating the `retrieval.py` client and query mechanisms.

### 5. Storage & Database
- **MVP**: Local SQLite database (`platform.db`) and local disk for files.
- **Production**: Azure Cosmos DB / Azure SQL and Azure Blob Storage.
- **How to migrate**: 
  - Translate `db_schema.sql` to the target database dialect (it relies on standard SQL types).
  - Update `storage.py` to use an appropriate ORM (like SQLAlchemy) or direct Azure SDKs for Cosmos DB.
  - Instead of passing local `file_path`s, upload files to Blob Storage during ingestion and pass blob URIs through the pipeline.

### 6. Review UI
- **MVP**: Streamlit (`app.py`).
- **Production**: React + FastAPI (or remain with Streamlit if suitable for internal tools).
- **How to migrate**: Build a FastAPI backend exposing the `storage.py` functions as REST endpoints, and build a React frontend to consume them. To implement Phase 2 (OCR-text highlighting), pass the bounding box data from Azure Document Intelligence to the React frontend.
