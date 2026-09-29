import os
import json
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

def create_mocks():
    out_dir = "input_docs"
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Native PDF Invoice
    c = canvas.Canvas(os.path.join(out_dir, "doc1_invoice.pdf"))
    c.drawString(100, 800, "INVOICE #9901")
    c.drawString(100, 780, "Date: 2024-01-15")
    c.drawString(100, 760, "Vendor: FastTech Solutions")
    c.drawString(100, 740, "Customer: StartUp Inc")
    c.drawString(100, 720, "Total Amount: $2500.00")
    c.drawString(100, 700, "Tax Amount: $250.00")
    c.drawString(100, 680, "Currency: USD")
    c.drawString(100, 660, "Due Date: 2024-02-15")
    c.drawString(100, 640, "Line Items:")
    c.drawString(120, 620, "- Web Development (Qty: 1, Price: 2500.00)")
    c.save()
    
    with open(os.path.join(out_dir, "doc1_invoice.json"), "w") as f:
        json.dump({"sender": "billing@fasttech.com", "subject": "Your Invoice 9901", "received_date": "2024-01-16T10:00:00Z"}, f)

    # 2. Native PDF Purchase Order
    c = canvas.Canvas(os.path.join(out_dir, "doc2_po.pdf"))
    c.drawString(100, 800, "PURCHASE ORDER PO-4432")
    c.drawString(100, 780, "Date: 2024-03-10")
    c.drawString(100, 760, "Vendor: OfficeSupplies Co")
    c.drawString(100, 740, "Customer: Big Corp")
    c.drawString(100, 720, "Total Amount: 150.00")
    c.drawString(100, 700, "Currency: USD")
    c.drawString(100, 680, "Line Items:")
    c.drawString(120, 660, "- Printer Paper (Qty: 10, Price: 15.00)")
    c.save()

    # 3. Scanned Image Invoice (JPG)
    img = Image.new('RGB', (800, 600), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    # Use default font since we might not have truetype fonts installed
    d.text((50, 50), "INVOICE #7788", fill=(0,0,0))
    d.text((50, 80), "Date: 2024-04-01", fill=(0,0,0))
    d.text((50, 110), "Vendor: OldSchool Paperworks", fill=(0,0,0))
    d.text((50, 140), "Customer: Modern Digital", fill=(0,0,0))
    d.text((50, 170), "Total: 450.00", fill=(0,0,0))
    d.text((50, 200), "Tax: 45.00", fill=(0,0,0))
    d.text((50, 230), "Currency: USD", fill=(0,0,0))
    d.text((50, 260), "Line Items: 1x Filing Cabinet @ 450.00", fill=(0,0,0))
    img.save(os.path.join(out_dir, "doc3_scanned.jpg"))
    
    # 4. Bank Statement (PDF)
    c = canvas.Canvas(os.path.join(out_dir, "doc4_bank.pdf"))
    c.drawString(100, 800, "BANK STATEMENT - March 2024")
    c.drawString(100, 780, "Customer: Jane Doe")
    c.drawString(100, 760, "Starting Balance: $5000.00")
    c.drawString(100, 740, "Ending Balance: $4800.00")
    c.save()

    # 5. Malformed/Unseen Document (Intentionally confusing text)
    c = canvas.Canvas(os.path.join(out_dir, "doc5_malformed.pdf"))
    c.drawString(100, 800, "CONFIDENTIAL INTERNAL MEMO")
    c.drawString(100, 780, "To: All Staff")
    c.drawString(100, 760, "Subject: Free pizza in the breakroom!")
    c.drawString(100, 740, "Just a reminder that there is total_amount of 5 pizzas.")
    c.drawString(100, 720, "Tax is zero. Currency: PIZZA.")
    c.drawString(100, 700, "Due Date: NOW")
    c.save()

    print("Created 5 mock documents in input_docs/")

if __name__ == "__main__":
    create_mocks()
