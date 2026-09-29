import os
import pdfplumber
import pytesseract
from PIL import Image

def is_pdf(file_path: str) -> bool:
    return file_path.lower().endswith('.pdf')

def extract_text_from_pdf(file_path: str) -> str:
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()

def extract_text_from_image(file_path: str) -> str:
    image = Image.open(file_path)
    try:
        text = pytesseract.image_to_string(image)
    except Exception as e:
        print(f"Tesseract OCR failed: {e}")
        raise e
    return text.strip()

def extract_text(file_path: str) -> str:
    """
    Extracts text from a given file (PDF or Image).
    PRODUCTION SUBSTITUTION: This local implementation uses Tesseract and pdfplumber.
    For production, replace this entire function with a call to Azure AI Document Intelligence
    which handles both native and scanned documents natively and returns layout-aware text.
    """
    if is_pdf(file_path):
        # Try native extraction first
        text = extract_text_from_pdf(file_path)
        
        # If native extraction yields very little text, it might be a scanned PDF.
        # For a full MVP we'd rasterize the PDF and run OCR, but for simplicity in this MVP,
        # we will assume we can get text out of native PDFs or the user provides images for scans.
        # Let's add a basic check:
        if len(text.strip()) < 50:
            import fitz # PyMuPDF
            print(f"Warning: Low text yield from native PDF extraction for {file_path}. Attempting OCR...")
            doc = fitz.open(file_path)
            ocr_text = ""
            for page in doc:
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text += pytesseract.image_to_string(img) + "\n"
            text = ocr_text.strip()
        return text
    else:
        # Assume it's an image
        return extract_text_from_image(file_path)
