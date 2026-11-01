import csv
import io
from html import escape

from fpdf import FPDF


def to_csv(headers, rows) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8-sig")


def to_html(title: str, headers, rows) -> bytes:
    head = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    body = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(c))}</td>" for c in row)
        body.append(f"<tr>{cells}</tr>")
    html = f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{ font-family: sans-serif; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #444; padding: 6px 10px; }}
th {{ background: #eee; }}
</style></head>
<body><h1>{escape(title)}</h1>
<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>
</body></html>"""
    return html.encode("utf-8")


class _TablePDF(FPDF):
    def header(self):
        pass


def to_pdf(title: str, headers, rows) -> bytes:
    pdf = _TablePDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title.encode("latin-1", "replace").decode("latin-1"), ln=1)
    pdf.set_font("Helvetica", size=8)
    col_width = 277 / max(len(headers), 1)
    pdf.set_fill_color(40, 40, 40)
    pdf.set_text_color(255, 255, 255)
    for header in headers:
        pdf.cell(col_width, 8, str(header).encode("latin-1", "replace").decode("latin-1"), border=1, fill=True)
    pdf.ln()
    pdf.set_text_color(0, 0, 0)
    fill = False
    for row in rows:
        pdf.set_fill_color(240, 240, 240)
        for cell in row:
            pdf.cell(
                col_width,
                7,
                str(cell).encode("latin-1", "replace").decode("latin-1"),
                border=1,
                fill=fill,
            )
        pdf.ln()
        fill = not fill
    return bytes(pdf.output())
