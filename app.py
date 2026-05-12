import os
import json
import uuid
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
from groq import Groq
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
import io
 
load_dotenv()
 
app = Flask(__name__)
 
# In-memory history store (resets on server restart)
history = []
 
 
def summarize_note(clinical_note: str) -> str:
    api_key = os.getenv("GROQ_API_KEY")
 
    if not api_key:
        return "No GROQ_API_KEY found. Please check your .env file."
 
    try:
        client = Groq(api_key=api_key)
 
        prompt = f"""You are a medical note summarizer.
 
Summarize the following clinical note into these sections:
- Chief Complaint
- History of Present Illness
- Key Findings
- Assessment
- Plan
 
Clinical Note:
{clinical_note}"""
 
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
 
        return response.choices[0].message.content
 
    except Exception as e:
        print("GROQ ERROR:", e)
        return f"Error contacting Groq API: {str(e)}"
 
 
def generate_pdf(note_text: str, summary: str, timestamp: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
 
    styles = getSampleStyleSheet()
    story = []
 
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=colors.HexColor("#1a1714"),
        spaceAfter=4,
        fontName="Helvetica-Bold",
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b6560"),
        spaceAfter=16,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#c84b2f"),
        fontName="Helvetica-Bold",
        spaceBefore=12,
        spaceAfter=4,
        letterSpacing=1,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#1a1714"),
        leading=16,
        spaceAfter=6,
    )
    note_style = ParagraphStyle(
        "NoteBody",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#4a4540"),
        leading=14,
        fontName="Courier",
    )
 
    story.append(Paragraph("MediSumai", title_style))
    story.append(Paragraph(f"Clinical Note Summary · {timestamp}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dedad3")))
    story.append(Spacer(1, 12))
    story.append(Paragraph("AI SUMMARY", section_style))
    story.append(Spacer(1, 4))
 
    lines = summary.split("\n")
    current_section = None
    section_body = []
 
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if section_body and current_section:
                story.append(Paragraph(current_section.upper(), section_style))
                story.append(Paragraph(" ".join(section_body), body_style))
                section_body = []
                current_section = None
            continue
 
        if stripped.startswith("**") and stripped.endswith("**"):
            if section_body and current_section:
                story.append(Paragraph(current_section.upper(), section_style))
                story.append(Paragraph(" ".join(section_body), body_style))
                section_body = []
            current_section = stripped.replace("**", "").replace(":", "").strip()
        elif stripped.startswith("- ") and ":" in stripped and len(stripped) < 60:
            if section_body and current_section:
                story.append(Paragraph(current_section.upper(), section_style))
                story.append(Paragraph(" ".join(section_body), body_style))
                section_body = []
            current_section = stripped.replace("- ", "").replace(":", "").strip()
        else:
            section_body.append(stripped)
 
    if section_body:
        if current_section:
            story.append(Paragraph(current_section.upper(), section_style))
        story.append(Paragraph(" ".join(section_body), body_style))
 
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dedad3")))
    story.append(Spacer(1, 12))
    story.append(Paragraph("ORIGINAL NOTE", section_style))
    story.append(Spacer(1, 4))
 
    for para in note_text.split("\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), note_style))
 
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "This summary is AI-generated and not a substitute for clinical judgment.",
        ParagraphStyle("Warning", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#c84b2f"), fontName="Helvetica-Oblique")
    ))
 
    doc.build(story)
    buffer.seek(0)
    return buffer.read()
 
 
@app.route("/", methods=["GET", "POST"])
def index():
    summaries = []
    notes_input = ""
 
    if request.method == "POST":
        raw = request.form.get("notes", "").strip()
        notes_input = raw
 
        notes = [n.strip() for n in raw.split("---") if n.strip()]
        if not notes:
            notes = [raw] if raw else []
 
        for note in notes:
            summary = summarize_note(note)
            entry = {
                "id": str(uuid.uuid4()),
                "note": note,
                "summary": summary,
                "timestamp": datetime.now().strftime("%b %d, %Y · %I:%M %p"),
            }
            summaries.append(entry)
            history.insert(0, entry)
 
    return render_template(
        "index.html",
        summaries=summaries,
        notes_input=notes_input,
        history=history[:20],
    )
 
 
@app.route("/export-pdf/<entry_id>")
def export_pdf(entry_id):
    entry = next((h for h in history if h["id"] == entry_id), None)
    if not entry:
        return "Not found", 404
 
    pdf_bytes = generate_pdf(entry["note"], entry["summary"], entry["timestamp"])
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"medisumai-summary-{entry_id[:8]}.pdf",
    )
 
 
@app.route("/clear-history", methods=["POST"])
def clear_history():
    history.clear()
    return jsonify({"status": "ok"})
 
 
if __name__ == "__main__":
    app.run(debug=True, port=5001)