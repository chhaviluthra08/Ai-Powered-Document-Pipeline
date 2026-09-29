import chromadb
import json

CHROMA_PATH = "chroma_db"

def get_chroma_client():
    return chromadb.PersistentClient(path=CHROMA_PATH)

def init_few_shot_examples():
    """
    Initializes the ChromaDB with some dummy few-shot examples for RAG.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="document_examples")
    
    # Check if already populated
    if collection.count() > 0:
        return
        
    examples = [
        {
            "id": "ex_invoice_1",
            "type": "Invoice",
            "text": "INVOICE #1001 Date: 2023-05-10 Vendor: Acme Corp Customer: Global Tech Total: $500.00 Tax: $50.00 Due: 2023-06-10 Line Items: 1x Widget @ $500.00",
            "schema_json": json.dumps({
                "invoice_number": {"value": "1001"},
                "invoice_date": {"value": "2023-05-10"},
                "vendor_name": {"value": "Acme Corp"},
                "customer_name": {"value": "Global Tech"},
                "total_amount": {"value": 550.0},
                "tax_amount": {"value": 50.0},
                "currency": {"value": "USD"},
                "due_date": {"value": "2023-06-10"},
                "line_items": {"value": [{"description": "Widget", "quantity": 1, "unit_price": 500.0}]}
            })
        },
        {
            "id": "ex_po_1",
            "type": "Purchase Order",
            "text": "PURCHASE ORDER PO-5554 Date: 2023-11-01 Vendor: SupplyCo Customer: BuildInc Total: $1200.00 Line Items: 10x Pipes @ $120.00",
            "schema_json": json.dumps({
                "purchase_order_number": {"value": "PO-5554"},
                "invoice_date": {"value": "2023-11-01"},
                "vendor_name": {"value": "SupplyCo"},
                "customer_name": {"value": "BuildInc"},
                "total_amount": {"value": 1200.0},
                "tax_amount": {"value": 0.0},
                "currency": {"value": "USD"},
                "line_items": {"value": [{"description": "Pipes", "quantity": 10, "unit_price": 120.0}]}
            })
        },
        {
            "id": "ex_bank_1",
            "type": "Bank Statement",
            "text": "BANK STATEMENT Account: 4521-0099 Period: 2024-03-01 to 2024-03-31 Customer: Jane Doe Bank: First National Bank Opening Balance: $5000.00 Closing Balance: $4800.00 Total Debits: $450.00 Total Credits: $250.00 Currency: USD",
            "schema_json": json.dumps({
                "invoice_number": {"value": None, "confidence_score": 100},
                "invoice_date": {"value": "2024-03-31", "confidence_score": 90},
                "vendor_name": {"value": "First National Bank", "confidence_score": 95},
                "customer_name": {"value": "Jane Doe", "confidence_score": 98},
                "purchase_order_number": {"value": None, "confidence_score": 100},
                "total_amount": {"value": 4800.0, "confidence_score": 92},
                "tax_amount": {"value": None, "confidence_score": 100},
                "currency": {"value": "USD", "confidence_score": 99},
                "due_date": {"value": None, "confidence_score": 100},
                "line_items": {"value": [], "confidence_score": 100}
            })
        },
        {
            "id": "ex_bank_2",
            "type": "Bank Statement",
            "text": "MONTHLY STATEMENT - April 2024 Customer: Acme Corp Account No: 8872-3310 Bank: City Trust Opening: $12000.00 Closing: $9500.00 Transactions: Payroll -2500.00, Office Supplies -200.00, Client Payment +200.00 Currency: USD",
            "schema_json": json.dumps({
                "invoice_number": {"value": None, "confidence_score": 100},
                "invoice_date": {"value": "2024-04-30", "confidence_score": 88},
                "vendor_name": {"value": "City Trust", "confidence_score": 95},
                "customer_name": {"value": "Acme Corp", "confidence_score": 98},
                "purchase_order_number": {"value": None, "confidence_score": 100},
                "total_amount": {"value": 9500.0, "confidence_score": 90},
                "tax_amount": {"value": None, "confidence_score": 100},
                "currency": {"value": "USD", "confidence_score": 99},
                "due_date": {"value": None, "confidence_score": 100},
                "line_items": {"value": [], "confidence_score": 100}
            })
        },
        {
            "id": "ex_form_1",
            "type": "Form",
            "text": "EXPENSE REIMBURSEMENT FORM Employee: John Smith Department: Engineering Date: 2024-02-10 Total Claimed: $320.00 Currency: USD Items: Travel $200.00, Meals $120.00 Approver: Manager Jane",
            "schema_json": json.dumps({
                "invoice_number": {"value": None, "confidence_score": 100},
                "invoice_date": {"value": "2024-02-10", "confidence_score": 92},
                "vendor_name": {"value": None, "confidence_score": 100},
                "customer_name": {"value": "John Smith", "confidence_score": 95},
                "purchase_order_number": {"value": None, "confidence_score": 100},
                "total_amount": {"value": 320.0, "confidence_score": 94},
                "tax_amount": {"value": None, "confidence_score": 100},
                "currency": {"value": "USD", "confidence_score": 98},
                "due_date": {"value": None, "confidence_score": 100},
                "line_items": {"value": [{"description": "Travel", "quantity": 1, "unit_price": 200.0}, {"description": "Meals", "quantity": 1, "unit_price": 120.0}], "confidence_score": 90}
            })
        },
        {
            "id": "ex_report_1",
            "type": "Report",
            "text": "QUARTERLY FINANCIAL REPORT Q1 2024 Company: GlobalTech Ltd Period: January-March 2024 Total Revenue: $450000.00 Total Expenses: $310000.00 Net Profit: $140000.00 Currency: USD Prepared by: Finance Department",
            "schema_json": json.dumps({
                "invoice_number": {"value": None, "confidence_score": 100},
                "invoice_date": {"value": "2024-03-31", "confidence_score": 85},
                "vendor_name": {"value": "GlobalTech Ltd", "confidence_score": 92},
                "customer_name": {"value": None, "confidence_score": 100},
                "purchase_order_number": {"value": None, "confidence_score": 100},
                "total_amount": {"value": 450000.0, "confidence_score": 88},
                "tax_amount": {"value": None, "confidence_score": 100},
                "currency": {"value": "USD", "confidence_score": 99},
                "due_date": {"value": None, "confidence_score": 100},
                "line_items": {"value": [], "confidence_score": 100}
            })
        },
        {
            "id": "ex_other_1",
            "type": "Other",
            "text": "INTERNAL MEMO To: All Staff From: HR Department Date: 2024-05-01 Subject: Office Closure Notice The office will be closed on May 10th for maintenance. Please plan accordingly.",
            "schema_json": json.dumps({
                "invoice_number": {"value": None, "confidence_score": 100},
                "invoice_date": {"value": "2024-05-01", "confidence_score": 80},
                "vendor_name": {"value": None, "confidence_score": 100},
                "customer_name": {"value": None, "confidence_score": 100},
                "purchase_order_number": {"value": None, "confidence_score": 100},
                "total_amount": {"value": None, "confidence_score": 100},
                "tax_amount": {"value": None, "confidence_score": 100},
                "currency": {"value": None, "confidence_score": 100},
                "due_date": {"value": None, "confidence_score": 100},
                "line_items": {"value": [], "confidence_score": 100}
            })
        }
    ]
    
    for ex in examples:
        collection.add(
            documents=[ex["text"]],
            metadatas=[{"type": ex["type"], "schema_json": ex["schema_json"]}],
            ids=[ex["id"]]
        )

def get_examples_for_type(document_type: str, query_text: str = "", n_results: int = 3) -> list:
    """
    Retrieves few-shot examples for the given document type.
    Clamps n_results to available matching documents to avoid ChromaDB query errors.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="document_examples")
    
    if collection.count() == 0:
        return []
        
    try:
        # Check matching count to avoid ChromaDB ValueError when n_results > matching count
        matching = collection.get(where={"type": document_type})
        matching_count = len(matching['ids']) if matching and 'ids' in matching else 0
        if matching_count == 0:
            return []
            
        effective_n_results = min(n_results, matching_count)
        safe_query = query_text[:500] if query_text else "document"
        
        results = collection.query(
            query_texts=[safe_query],
            n_results=effective_n_results,
            where={"type": document_type}
        )
        
        examples = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for idx, meta in enumerate(results['metadatas'][0]):
                examples.append({
                    "text": results['documents'][0][idx],
                    "schema_json": json.loads(meta['schema_json'])
                })
        return examples
    except Exception as e:
        print(f"Retrieval error: {e}")
        return []

def add_example(document_type: str, text: str, extraction: dict, doc_id: str):
    """
    Adds a human-approved extraction as a new few-shot example for future
    retrieval. Called after a document is approved in the review UI.
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(name="document_examples")

    doc_key = f"human_{doc_id}"
    schema_json = json.dumps(extraction)

    try:
        existing = collection.get(where={"type": document_type})
        if existing and 'ids' in existing and existing['ids']:
            human_ids = [
                existing['ids'][i] for i, meta in enumerate(existing['metadatas'])
                if meta and meta.get('source') == 'human_approved' and existing['ids'][i] != doc_key
            ]
            if len(human_ids) >= 20:
                collection.delete(ids=[human_ids[0]])
    except Exception as e:
        print(f"Warning checking example limit: {e}")

    collection.upsert(
        documents=[text[:2000]],
        metadatas=[{"type": document_type, "schema_json": schema_json, "source": "human_approved"}],
        ids=[doc_key]
    )

if __name__ == '__main__':
    init_few_shot_examples()
    print("ChromaDB initialized.")

