import os
import json
import re
from groq import Groq, APIError, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

def load_schema():
    with open('schema.json', 'r') as f:
        return json.load(f)

def validate_extraction(extractions: dict) -> dict:
    """
    Cross-checks self-reported confidence against regex/format validations.
    Lowers confidence to 0 if validation fails.
    """
    date_regex = re.compile(r'^\d{4}-\d{2}-\d{2}$')
    
    for field, data in extractions.items():
        if field in ['document_type', 'email_metadata']: 
            continue
        
        if not isinstance(data, dict):
            continue
            
        val = data.get('value')
        conf = data.get('confidence_score', 0)
        
        if val is None:
            continue
            
        # Date validation
        if field in ['invoice_date', 'due_date']:
            if not isinstance(val, str) or not date_regex.match(val):
                data['confidence_score'] = 0
                
        # Numeric validation
        elif field in ['total_amount', 'tax_amount']:
            if not isinstance(val, (int, float)):
                data['confidence_score'] = 0
                
        # Currency validation
        elif field == 'currency':
            if not isinstance(val, str) or len(val) != 3:
                data['confidence_score'] = 0
                
    return extractions

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError, TimeoutError)),
    reraise=True
)
def _call_extraction_api(client, system_prompt: str, text: str):
    return client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Extract the data from this document text:\n\n{text}"}
        ],
        response_format={ "type": "json_object" }
    )

def extract_fields(text: str, document_type: str, examples: list) -> dict:
    """
    Uses Groq JSON mode to extract fields according to schema.json.
    Retries transient failures up to 3 times with exponential backoff.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("MOCK EXTRACTION: No GROQ_API_KEY found. Using mock extraction.")
        mock_data = {
            "invoice_number": {"value": "MOCK-123", "confidence_score": 90},
            "invoice_date": {"value": "2024-01-15", "confidence_score": 90},
            "total_amount": {"value": 2500.0, "confidence_score": 90},
            "currency": {"value": "USD", "confidence_score": 90}
        }
        # Simulate low confidence for "Other" or "malformed"
        if document_type == "Other" or "malformed" in text.lower():
            mock_data["total_amount"] = {"value": 5.0, "confidence_score": 40} # force review queue
        
        return validate_extraction(mock_data)

    client = get_groq_client()
    schema = load_schema()
    
    system_prompt = f"You are an expert document data extractor. Extract data according to this JSON Schema exactly:\n{json.dumps(schema)}\n\nThe document is classified as a {document_type}. Respond with ONLY a valid JSON object matching this schema, no other text."
    
    if examples:
        system_prompt += "\n\nHere are some examples of correctly extracted data for this document type:\n"
        for i, ex in enumerate(examples):
            system_prompt += f"\nExample {i+1}:\nText:\n{ex['text']}\nExtraction:\n{json.dumps(ex['schema_json'])}\n"
            
    system_prompt += "\n\nEnsure every field includes a 'confidence_score' between 0 and 100 representing how sure you are about the extraction. If a field is not present, set its value to null and confidence to 100 (confident it is missing)."

    try:
        response = _call_extraction_api(client, system_prompt, text)
        content = response.choices[0].message.content
        extracted_data = json.loads(content)
        return validate_extraction(extracted_data)
    except Exception as e:
        print(f"EXTRACTION FAILURE (all retries exhausted): {e}")
        return {}