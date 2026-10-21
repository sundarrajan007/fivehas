"""
resume_generator.py
Generates clean, professional, ATS-friendly PDF and formatted resumes
for Smart Career Guidance & Employment Portal.

Adheres strictly to modern ATS formatting standards:
- Single-column layout (no tables or multi-column parsing traps)
- Clear, standard section headers
- Clean typography, consistent spacing, and bullet points
- Grounded 100% in the user's reviewed and approved data
"""

import io
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ReportLab imports
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, ListFlowable, ListItem
except ImportError as e:
    logger.error(f"ReportLab import error in resume_generator: {e}")


def clean_xml_chars(text):
    """Escape XML special characters for ReportLab Paragraphs."""
    if not text:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&apos;")
    return text


def generate_improved_resume_pdf(data):
    """
    Generates an ATS-compliant, executive-style PDF resume from the user's
    reviewed and approved Career Profile details.
    
    data: dictionary containing:
      - full_name
      - email
      - phone
      - location
      - register_number
      - college_name
      - batch_year
      - current_semester
      - skills
      - tech_stack
      - interests
      - experience (summary, projects, work experience)
    
    Returns: BytesIO buffer containing the generated PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom modern typography styles
    title_style = ParagraphStyle(
        'ResumeTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f172a'),
        alignment=0, # Left-aligned for standard ATS reading
        spaceAfter=4
    )

    contact_style = ParagraphStyle(
        'ResumeContact',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceAfter=12
    )

    section_header_style = ParagraphStyle(
        'ResumeSectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor('#1e40af'), # Professional blue
        spaceBefore=10,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'ResumeBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#1e293b'),
        spaceAfter=4
    )

    bold_body_style = ParagraphStyle(
        'ResumeBoldBody',
        parent=body_style,
        fontName='Helvetica-Bold',
        spaceAfter=2
    )

    bullet_style = ParagraphStyle(
        'ResumeBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    story = []

    # 1. HEADER (Candidate Name & Contact Info)
    name = (data.get("full_name") or "Student Candidate").strip()
    story.append(Paragraph(clean_xml_chars(name), title_style))

    contact_parts = []
    if data.get("email"):
        contact_parts.append(f"Email: {clean_xml_chars(data.get('email'))}")
    if data.get("phone"):
        contact_parts.append(f"Phone: {clean_xml_chars(data.get('phone'))}")
    if data.get("location"):
        contact_parts.append(f"Location: {clean_xml_chars(data.get('location'))}")
    if data.get("register_number"):
        contact_parts.append(f"Reg No: {clean_xml_chars(data.get('register_number'))}")

    contact_line = " | ".join(contact_parts) if contact_parts else "Contact details provided upon request"
    story.append(Paragraph(contact_line, contact_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # 2. EDUCATION SECTION
    college = data.get("college_name")
    batch = data.get("batch_year")
    sem = data.get("current_semester")
    if college or batch or sem:
        story.append(Paragraph("EDUCATION", section_header_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))

        edu_headline = f"{clean_xml_chars(college or 'Bachelor of Engineering / Technology')}"
        story.append(Paragraph(edu_headline, bold_body_style))

        edu_meta_parts = []
        if sem:
            edu_meta_parts.append(f"Current Status: Semester {clean_xml_chars(sem)}")
        if batch:
            edu_meta_parts.append(f"Batch / Year of Graduation: {clean_xml_chars(batch)}")
        
        if edu_meta_parts:
            story.append(Paragraph(" | ".join(edu_meta_parts), body_style))
        story.append(Spacer(1, 6))

    # 3. TECHNICAL SKILLS & STACK
    skills = data.get("skills")
    tech_stack = data.get("tech_stack")
    interests = data.get("interests")

    if skills or tech_stack or interests:
        story.append(Paragraph("TECHNICAL SKILLS &amp; COMPETENCIES", section_header_style))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))

        if skills:
            story.append(Paragraph(f"<b>Core Skills:</b> {clean_xml_chars(skills)}", body_style))
        if tech_stack:
            story.append(Paragraph(f"<b>Frameworks &amp; Tools:</b> {clean_xml_chars(tech_stack)}", body_style))
        if interests:
            story.append(Paragraph(f"<b>Specialization / Domains:</b> {clean_xml_chars(interests)}", body_style))
        story.append(Spacer(1, 6))

    # 4. EXPERIENCE, PROJECTS & SUMMARY
    experience_text = (data.get("experience") or "").strip()
    if experience_text:
        # Check if structured sections like SUMMARY:, PROJECTS:, EXPERIENCE: exist
        lines = [l.strip() for l in experience_text.split('\n') if l.strip()]

        current_heading = "EXPERIENCE &amp; KEY PROJECTS"
        has_printed_exp_header = False

        bullet_accumulator = []

        def flush_bullets():
            for b in bullet_accumulator:
                # Add clean bullet symbol
                clean_b = re.sub(r'^[•\-\*\d\.\)\s]+', '', b).strip()
                if clean_b:
                    story.append(Paragraph(f"• {clean_xml_chars(clean_b)}", bullet_style))
            bullet_accumulator.clear()

        for line in lines:
            line_upper = line.upper().rstrip(':')
            if line_upper in ["SUMMARY", "PROFESSIONAL SUMMARY", "CAREER OBJECTIVE"]:
                flush_bullets()
                story.append(Paragraph("PROFESSIONAL SUMMARY", section_header_style))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))
                has_printed_exp_header = False
            elif line_upper in ["EXPERIENCE", "WORK EXPERIENCE", "INTERNSHIPS"]:
                flush_bullets()
                story.append(Paragraph("WORK EXPERIENCE", section_header_style))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))
                has_printed_exp_header = True
            elif line_upper in ["PROJECTS", "ACADEMIC PROJECTS", "KEY PROJECTS"]:
                flush_bullets()
                story.append(Paragraph("PROJECTS", section_header_style))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))
                has_printed_exp_header = True
            elif line_upper in ["CERTIFICATIONS", "CERTIFICATES", "COURSES"]:
                flush_bullets()
                story.append(Paragraph("CERTIFICATIONS", section_header_style))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))
                has_printed_exp_header = True
            else:
                if not has_printed_exp_header and not story:
                    story.append(Paragraph("EXPERIENCE &amp; PROJECTS", section_header_style))
                    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0"), spaceAfter=5))
                    has_printed_exp_header = True

                # Check if it looks like a bullet or project title
                if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                    bullet_accumulator.append(line)
                elif len(line) < 60 and not line.endswith('.'):
                    flush_bullets()
                    story.append(Paragraph(clean_xml_chars(line), bold_body_style))
                else:
                    if bullet_accumulator:
                        flush_bullets()
                    story.append(Paragraph(clean_xml_chars(line), body_style))

        flush_bullets()

    # Footer note indicating ATS compliance
    story.append(Spacer(1, 14))
    footer_text = f"Curated via Smart Career Guidance Portal | Verified Profile Standards | Generated {datetime.now().strftime('%B %Y')}"
    footer_style = ParagraphStyle(
        'ResumeFooter',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#94a3b8'),
        alignment=1
    )
    story.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer
