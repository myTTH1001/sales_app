from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def create_invoice_pdf(invoice_id, items, total):
    file_name = f"invoice_{invoice_id}.pdf"
    c = canvas.Canvas(file_name, pagesize=A4)

    c.setFont("Helvetica", 14)
    c.drawString(50, 800, f"HÓA ĐƠN #{invoice_id}")

    y = 760
    for item in items:
        c.drawString(50, y, f"{item['name']} x{item['qty']} = {item['price']}đ")
        y -= 20

    c.drawString(50, y-20, f"TỔNG TIỀN: {total}đ")
    c.save()

    return file_name