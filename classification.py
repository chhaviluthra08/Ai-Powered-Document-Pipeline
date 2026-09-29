import os
import json
from groq import Groq, APIError, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

load_dotenv()

def get_groq_client():
    return Groq(api_key=os.environ.get("GROQ_API_KEY"))

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError, TimeoutError)),
    reraise=True
)
def _call_classification_api(client, text: str):
    prompt = """
    Analyze the following document text and classify it into one of these categories:
    Invoice, Purchase Order, Bank Statement, Form, Report, Other.
    
    Provide your response as a JSON object with:
    - "document_type": the classified category
    - "confidence": an integer from 0 to 100 representing your confidence in the classification.
    """
    return client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a document classification assistant. Output ONLY valid JSON."},
            {"role": "user", "content": f"{prompt}\n\nDocument Text (first 2000 chars):\n{text[:2000]}"}
        ],
        response_format={ "type": "json_object" }
    )

def classify_document(text: str) -> dict:
    """
    Classifies the document into one of the known types based on the text.
    Uses exponential backoff retry for transient API failures.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("MOCK CLASSIFICATION: No GROQ_API_KEY found. Using mock classification.")
        if "INVOICE" in text.upper(): return {"document_type": "Invoice", "confidence": 95}
        if "PURCHASE ORDER" in text.upper(): return {"document_type": "Purchase Order", "confidence": 90}
        if "BANK" in text.upper(): return {"document_type": "Bank Statement", "confidence": 88}
        return {"document_type": "Other", "confidence": 50}
        
    client = get_groq_client()
    
    try:
        response = _call_classification_api(client, text)
        content = response.choices[0].message.content
        result = json.loads(content)
        return {
            "document_type": result.get("document_type", "Other"),
            "confidence": result.get("confidence", 0)
        }
    except Exception as e:
        print(f"Classification failure after retries: {e}")
        return {"document_type": "Other", "confidence": 0}