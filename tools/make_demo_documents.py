"""Creates FICTIONAL demo documents (digital PDFs, scanner-style images and
phone-photo-style images) plus manifest.json for the demo-data loader.
Run:  python tools/make_demo_documents.py
Needs: reportlab, pymupdf, pillow, numpy (developer tool, not needed by the app)."""
import json
import os

import fitz  # pymupdf
import numpy as np
from PIL import Image, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = os.path.join(os.path.dirname(__file__), "..", "demo_documents")
EXTRAS = os.path.join(OUT, "extras")
rng = np.random.default_rng(42)
ss = getSampleStyleSheet()
small = ParagraphStyle("small", parent=ss["Normal"], fontSize=8, textColor=colors.grey)
body = ParagraphStyle("body", parent=ss["Normal"], fontSize=10, leading=14)
DISCLAIMER = "FICTIONAL DEMO DOCUMENT - generated for software testing. Not a real patient, laboratory or doctor."

# ---------------------------------------------------------------- content
# (test, result, unit, reference range text, flag)  flag: "", "H", "L", "CRITICAL H", ...
REPORTS = {
    "ananya_cbc_iron_report": dict(
        patient=("Ananya Krishnan", "31 Y / Female", "DEMO-P01"), title="Complete Blood Count and Iron Studies",
        sections=[("HAEMATOLOGY", [
            ("Haemoglobin", "9.8", "g/dL", "12.0 - 15.5", "L"),
            ("RBC count", "3.9", "million/uL", "3.8 - 5.2", ""),
            ("Haematocrit (PCV)", "31", "%", "36 - 46", "L"),
            ("MCV", "72", "fL", "80 - 100", "L"),
            ("MCH", "24", "pg", "27 - 33", "L"),
            ("MCHC", "31.5", "g/dL", "32 - 36", "L"),
            ("WBC count", "7.2", "thousand/uL", "4.0 - 11.0", ""),
            ("Platelet count", "310", "thousand/uL", "150 - 400", ""),
        ]), ("IRON STUDIES", [
            ("Serum ferritin", "8", "ng/mL", "13 - 150", "L"),
            ("Serum iron", "42", "ug/dL", "60 - 170", "L"),
        ])]),
    "rahul_diabetes_panel": dict(
        patient=("Rahul Menon", "48 Y / Male", "DEMO-P02"), title="Diabetes and Lipid Panel",
        sections=[("GLUCOSE", [
            ("Fasting plasma glucose", "168", "mg/dL", "70 - 99", "H"),
            ("Post-prandial glucose (2 h)", "245", "mg/dL", "less than 140", "H"),
            ("HbA1c", "8.9", "%", "less than 5.7", "H"),
        ]), ("LIPID PROFILE", [
            ("Total cholesterol", "232", "mg/dL", "less than 200", "H"),
            ("LDL cholesterol", "152", "mg/dL", "less than 100", "H"),
            ("HDL cholesterol", "38", "mg/dL", "more than 40", "L"),
            ("Triglycerides", "210", "mg/dL", "less than 150", "H"),
        ]), ("KIDNEY", [
            ("Serum creatinine", "1.0", "mg/dL", "0.7 - 1.3", ""),
        ])]),
    "fatima_lipid_thyroid_report": dict(
        patient=("Fatima Sheikh", "60 Y / Female", "DEMO-P03"), title="Lipid Profile and Thyroid Function",
        sections=[("LIPID PROFILE", [
            ("Total cholesterol", "268", "mg/dL", "less than 200", "H"),
            ("LDL cholesterol", "172", "mg/dL", "less than 100", "H"),
            ("HDL cholesterol", "44", "mg/dL", "more than 50", "L"),
            ("Triglycerides", "240", "mg/dL", "less than 150", "H"),
        ]), ("THYROID FUNCTION", [
            ("TSH", "9.8", "mIU/L", "0.4 - 4.0", "H"),
            ("Free T4", "0.7", "ng/dL", "0.8 - 1.8", "L"),
        ])]),
    "karthik_health_checkup": dict(
        patient=("Karthik Subramanian", "36 Y / Male", "DEMO-P04"), title="Routine Health Check-up",
        sections=[("HAEMATOLOGY", [
            ("Haemoglobin", "14.8", "g/dL", "13.0 - 17.0", ""),
            ("WBC count", "6.4", "thousand/uL", "4.0 - 11.0", ""),
            ("Platelet count", "255", "thousand/uL", "150 - 400", ""),
        ]), ("BIOCHEMISTRY", [
            ("Fasting plasma glucose", "88", "mg/dL", "70 - 99", ""),
            ("Total cholesterol", "178", "mg/dL", "less than 200", ""),
            ("Serum creatinine", "0.9", "mg/dL", "0.7 - 1.3", ""),
            ("SGPT (ALT)", "28", "U/L", "7 - 56", ""),
        ])]),
    "meena_kidney_panel_critical": dict(
        patient=("Meena Rajan", "75 Y / Female", "DEMO-P05"), title="Kidney Function and Electrolytes",
        sections=[("KIDNEY FUNCTION", [
            ("Serum creatinine", "3.4", "mg/dL", "0.6 - 1.1", "H"),
            ("Blood urea", "98", "mg/dL", "15 - 40", "H"),
            ("eGFR", "14", "mL/min/1.73m2", "more than 90", "L"),
        ]), ("ELECTROLYTES", [
            ("Serum potassium", "6.4", "mmol/L", "3.5 - 5.0", "CRITICAL H"),
            ("Serum sodium", "132", "mmol/L", "135 - 145", "L"),
        ]), ("HAEMATOLOGY", [
            ("Haemoglobin", "9.1", "g/dL", "12.0 - 15.5", "L"),
        ])]),
}

PRESCRIPTIONS = {
    "rahul_prescription": dict(
        patient=("Rahul Menon", "48 Y / Male", "DEMO-P02"), doctor=("Dr. Arjun Nair", "MBBS, MD (Medicine)", "DEMO-REG-20417"),
        rows=[("Metformin", "500 mg", "1 tablet", "Oral", "Twice daily after food", "30 days"),
              ("Amlodipine", "5 mg", "1 tablet", "Oral", "Once daily, morning", "30 days"),
              ("Atorvastatin", "20 mg", "1 tablet", "Oral", "Once daily at night", "30 days")],
        advice="Low sugar and low salt diet. 30 minutes of walking daily. Review with fasting glucose in 4 weeks."),
    "fatima_prescription": dict(
        patient=("Fatima Sheikh", "60 Y / Female", "DEMO-P03"), doctor=("Dr. Meera Iyer", "MBBS, MD (General Medicine)", "DEMO-REG-18822"),
        rows=[("Levothyroxine", "50 mcg", "1 tablet", "Oral", "Once daily, empty stomach", "60 days"),
              ("Atorvastatin", "20 mg", "1 tablet", "Oral", "Once daily at night", "60 days")],
        advice="Take levothyroxine 30 minutes before breakfast. Repeat TSH and lipid profile after 6 weeks."),
    "meena_prescription": dict(
        patient=("Meena Rajan", "75 Y / Female", "DEMO-P05"), doctor=("Dr. Arjun Nair", "MBBS, MD (Medicine)", "DEMO-REG-20417"),
        rows=[("Sodium bicarbonate", "500 mg", "1 tablet", "Oral", "Twice daily", "14 days"),
              ("Furosemide", "40 mg", "1 tablet", "Oral", "Once daily, morning", "14 days")],
        advice="Restrict potassium-rich foods. Urgent nephrology review. Repeat kidney panel in 3 days."),
}


# ---------------------------------------------------------------- PDFs
def lab_pdf(name, spec):
    path = os.path.join(OUT, f"{name}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    p_name, p_age, p_ref = spec["patient"]
    flow = [Paragraph("<b>HEALTHBRIDGE DEMO DIAGNOSTICS</b>", ParagraphStyle("h", fontSize=16, leading=22, textColor=colors.HexColor("#0f766e"))),
            Paragraph("Demo Lab Services Pvt. Ltd. - Chennai, India - Lab ID DEMO-LAB-001", small), Spacer(1, 4 * mm)]
    info = Table([[f"Patient: {p_name}", f"Age / Sex: {p_age}"], [f"Patient ref: {p_ref}", "Sample: Venous blood"],
                  ["Collected: 24-Oct-2026 08:15", "Reported: 24-Oct-2026 14:40"]], colWidths=[85 * mm, 85 * mm])
    info.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                              ("BOX", (0, 0), (-1, -1), 0.6, colors.grey), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9"))]))
    flow += [info, Spacer(1, 5 * mm), Paragraph(f"<b>{spec['title']}</b>", ParagraphStyle("t", fontSize=12))]
    for section, rows in spec["sections"]:
        data = [["TEST", "RESULT", "UNIT", "REFERENCE RANGE", "FLAG"]]
        for test, res, unit, ref, flag in rows:
            data.append([test, res, unit, ref, flag])
        t = Table(data, colWidths=[58 * mm, 20 * mm, 30 * mm, 36 * mm, 28 * mm])
        style = [("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                 ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                 ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        for i, row in enumerate(rows, start=1):
            if row[4]:
                color = colors.HexColor("#b91c1c") if "CRITICAL" in row[4] else colors.HexColor("#c2410c")
                style += [("TEXTCOLOR", (1, i), (1, i), color), ("TEXTCOLOR", (4, i), (4, i), color),
                          ("FONTNAME", (1, i), (1, i), "Helvetica-Bold"), ("FONTNAME", (4, i), (4, i), "Helvetica-Bold")]
        t.setStyle(TableStyle(style))
        flow += [Spacer(1, 4 * mm), Paragraph(f"<b>{section}</b>", ParagraphStyle("s", fontSize=10, textColor=colors.HexColor("#0f766e"))), t]
    flow += [Spacer(1, 8 * mm), Paragraph("H = high, L = low. Values outside the reference range need clinical interpretation by a doctor.", small),
             Spacer(1, 2 * mm), Paragraph(DISCLAIMER, ParagraphStyle("d", parent=small, textColor=colors.HexColor("#b91c1c")))]
    doc.build(flow)
    return path


def rx_pdf(name, spec):
    path = os.path.join(OUT, f"{name}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=14 * mm, bottomMargin=14 * mm)
    d_name, d_qual, d_reg = spec["doctor"]
    p_name, p_age, p_ref = spec["patient"]
    flow = [Paragraph(f"<b>{d_name}</b>", ParagraphStyle("h", fontSize=16, leading=22, textColor=colors.HexColor("#1d4ed8"))),
            Paragraph(f"{d_qual} - Reg. No. {d_reg}", body), Paragraph("HealthBridge Demo Clinic, Anna Nagar, Chennai - Ph: 044-0000-0000", small),
            Spacer(1, 4 * mm)]
    info = Table([[f"Patient: {p_name}", f"Age / Sex: {p_age}", "Date: 26-Oct-2026"]], colWidths=[70 * mm, 55 * mm, 45 * mm])
    info.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9.5), ("LINEABOVE", (0, 0), (-1, 0), 0.8, colors.grey),
                              ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.grey), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    data = [["No.", "MEDICINE", "STRENGTH", "DOSE", "ROUTE", "FREQUENCY", "DURATION"]]
    for i, (med, strength, dose, route, freq, dur) in enumerate(spec["rows"], 1):
        data.append([str(i), med, strength, dose, route, freq, dur])
    t = Table(data, colWidths=[10 * mm, 38 * mm, 22 * mm, 22 * mm, 16 * mm, 42 * mm, 20 * mm])
    t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                           ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    flow += [info, Spacer(1, 4 * mm), Paragraph("<font size=22 color='#1d4ed8'><b>Rx</b></font>", body), Spacer(1, 2 * mm), t, Spacer(1, 6 * mm),
             Paragraph(f"<b>Advice:</b> {spec['advice']}", body), Spacer(1, 18 * mm), Paragraph("_______________________<br/>Signature (demo)", body),
             Spacer(1, 8 * mm), Paragraph(DISCLAIMER, ParagraphStyle("d", parent=small, textColor=colors.HexColor("#b91c1c")))]
    doc.build(flow)
    return path


# ---------------------------------------------------------------- image effects
def render(pdf_path, dpi):
    page = fitz.open(pdf_path)[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def scanner_look(img, angle=1.1):
    """Flatbed-scanner style: slight skew, grey tint, noise, soft edges, JPEG artefacts."""
    g = img.convert("L").rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=250).filter(ImageFilter.GaussianBlur(0.7))
    a = np.asarray(g, dtype=np.float32)
    a = a * 0.93 + 8 + rng.normal(0, 5.0, a.shape)
    h, w = a.shape
    a -= np.linspace(0, 14, w)[None, :]  # darker toward one side
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGB")


def phone_photo_look(img):
    """Photo of a page on a desk: perspective tilt, uneven light, shadow, colour cast, blur."""
    w, h = img.size
    pad = int(w * 0.12)
    desk = Image.new("RGB", (w + 2 * pad, h + 2 * pad), (92, 70, 52))
    desk.paste(img, (pad, pad))
    W, H = desk.size
    src = [(0, 0), (W, 0), (W, H), (0, H)]
    dst = [(W * 0.03, H * 0.015), (W * 0.97, H * 0.0), (W * 1.0, H * 0.985), (W * 0.0, H * 1.0)]
    A = []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
    coeffs = np.linalg.solve(np.array(A, dtype=np.float64), np.array([c for p in src for c in p], dtype=np.float64))
    out = desk.transform((W, H), Image.PERSPECTIVE, coeffs.tolist(), Image.BICUBIC).rotate(-2.2, resample=Image.BICUBIC, fillcolor=(92, 70, 52))
    a = np.asarray(out, dtype=np.float32)
    yy, xx = np.mgrid[0:H, 0:W]
    light = 1.06 - 0.22 * (xx / W) - 0.10 * (yy / H)  # light falls off to one corner
    shadow = 1 - 0.30 * np.exp(-(((xx - W * 0.82) / (W * 0.20)) ** 2 + ((yy - H * 0.20) / (H * 0.30)) ** 2))
    a = a * (light * shadow)[..., None] * np.array([1.03, 1.0, 0.93])[None, None, :] + rng.normal(0, 3.5, a.shape)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))


def main():
    os.makedirs(EXTRAS, exist_ok=True)
    manifest = []
    P = {"ananya_cbc_iron_report": "ananya.krishnan", "rahul_diabetes_panel": "rahul.menon", "fatima_lipid_thyroid_report": "fatima.sheikh",
         "karthik_health_checkup": "karthik.subramanian", "meena_kidney_panel_critical": "meena.rajan",
         "rahul_prescription": "rahul.menon", "fatima_prescription": "fatima.sheikh", "meena_prescription": "meena.rajan"}
    pdfs = {}
    for name, spec in REPORTS.items():
        pdfs[name] = lab_pdf(name, spec)
        manifest.append(dict(file=f"{name}.pdf", patient=P[name], doc_type="lab_report", by="patient", kind="digital PDF"))
    for name, spec in PRESCRIPTIONS.items():
        pdfs[name] = rx_pdf(name, spec)
    manifest.append(dict(file="rahul_prescription.pdf", patient="rahul.menon", doc_type="prescription", by="doctor:arjun.nair", kind="digital PDF"))

    def save_jpg(img, fname, q):
        img.save(os.path.join(OUT, fname), "JPEG", quality=q)

    save_jpg(scanner_look(render(pdfs["ananya_cbc_iron_report"], 150)), "ananya_cbc_iron_report_scan.jpg", 72)
    manifest.append(dict(file="ananya_cbc_iron_report_scan.jpg", patient="ananya.krishnan", doc_type="lab_report", by="patient", kind="scanner image"))
    save_jpg(scanner_look(render(pdfs["fatima_lipid_thyroid_report"], 150), 0.8), "fatima_lipid_thyroid_report_scan.jpg", 70)
    manifest.append(dict(file="fatima_lipid_thyroid_report_scan.jpg", patient="fatima.sheikh", doc_type="lab_report", by="patient", kind="scanner image"))
    save_jpg(scanner_look(render(pdfs["meena_kidney_panel_critical"], 150), -0.9), "meena_kidney_panel_critical_scan.jpg", 70)
    manifest.append(dict(file="meena_kidney_panel_critical_scan.jpg", patient="meena.rajan", doc_type="lab_report", by="patient", kind="scanner image"))
    save_jpg(phone_photo_look(render(pdfs["rahul_prescription"], 120)), "rahul_prescription_photo.jpg", 84)
    manifest.append(dict(file="rahul_prescription_photo.jpg", patient="rahul.menon", doc_type="prescription", by="patient", kind="phone photo"))
    save_jpg(scanner_look(render(pdfs["fatima_prescription"], 150), 0.6), "fatima_prescription_scan.jpg", 72)
    manifest.append(dict(file="fatima_prescription_scan.jpg", patient="fatima.sheikh", doc_type="prescription", by="patient", kind="scanner image"))
    save_jpg(phone_photo_look(render(pdfs["meena_prescription"], 120)), "meena_prescription_photo.jpg", 84)
    manifest.append(dict(file="meena_prescription_photo.jpg", patient="meena.rajan", doc_type="prescription", by="patient", kind="phone photo", draft_source=True))
    # remove intermediate PDFs that are not meant to be uploaded
    for n in ("fatima_prescription", "meena_prescription"):
        os.remove(os.path.join(OUT, f"{n}.pdf"))

    # ----- extras: files for testing validation and OCR uncertainty (NOT loaded into the database)
    blurry = scanner_look(render(pdfs["rahul_diabetes_panel"], 70), 2.5).filter(ImageFilter.GaussianBlur(1.6))
    blurry.save(os.path.join(EXTRAS, "blurry_low_quality_report.jpg"), "JPEG", quality=40)
    open(os.path.join(EXTRAS, "fake_report.pdf"), "w").write("This is plain text pretending to be a PDF. It must be rejected.")
    open(os.path.join(EXTRAS, "notes.txt"), "w").write("A text file. Only PDF, JPG, PNG and WEBP are accepted.")
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    print("created", len(manifest), "documents in", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
