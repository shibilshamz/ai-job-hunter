"""
cv_generator.py
ReportLab CV PDF generator for the AI Job Hunter pipeline.
Takes tailored summary + reordered skills from scorer.py and generates
a properly formatted PDF: Shibil_CV_CompanyName.pdf

Usage:
    from cv_generator import generate_cv

    path = generate_cv(
        company_name="TechCorp Dubai",
        tailored_summary="...",
        tailored_skills=["skill1", "skill2", ...]
    )
"""

import os
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

# ── Output directory ──────────────────────────────────────────────────────────
CV_OUTPUT_DIR = os.environ.get("CV_OUTPUT_DIR", "/root/job-hunter/cvs")
os.makedirs(CV_OUTPUT_DIR, exist_ok=True)

# ── Colours ───────────────────────────────────────────────────────────────────
DARK    = colors.HexColor("#1a1a2e")   # Near-black (name, section headers)
ACCENT  = colors.HexColor("#2563eb")   # Blue (links, divider lines)
MID     = colors.HexColor("#374151")   # Dark grey (body text)
LIGHT   = colors.HexColor("#6b7280")   # Grey (dates, subtitles)
WHITE   = colors.white

# ── Page margins ──────────────────────────────────────────────────────────────
MARGIN_TOP    = 14 * mm
MARGIN_BOTTOM = 14 * mm
MARGIN_LEFT   = 18 * mm
MARGIN_RIGHT  = 18 * mm

# ── Fixed CV data (never changes) ────────────────────────────────────────────
CONTACT = {
    "name":     "Shibil Shamsudheen",
    "title":    "AI Automation Builder · Agent Developer",
    "tagline":  "Chemical engineer turned AI agent builder — I build autonomous systems that run while I sleep, from 24/7 trading agents to n8n automation pipelines.",
    "location": "Dubai, UAE · Company Visa (Sterling Perfumes) — available to transfer",
    "phone":    "+971 54 322 0599",
    "email":    "shibilshamz123@gmail.com",
    "portfolio":"shibilshamz.github.io",
    "linkedin": "linkedin.com/in/shibil-shamsudheen",
    "github":   "github.com/shibilshamz",
}

PROJECTS = [
    {
        "title":   "Stock Trading Agent v2",
        "period":  "2025 – Present",
        "links":   "Live Dashboard · GitHub",
        "bullets": [
            "Autonomous NSE intraday paper trading agent in Python — scans top 20 Nifty 50 stocks every 15 min using yfinance and pandas-ta; processes ~96 trade signals/day across 20 symbols",
            "3-layer signal system (ORB, VWAP, Momentum) validated by Groq LLaMA 3.1 — every trade signal confirmed by AI before execution",
            "Deployed on Hostinger Ubuntu VPS managed by Supervisor — 6+ months continuous uptime, zero manual restarts; all signals and daily P&L pushed live to Telegram",
            "Built a custom Node.js MCP server with 7 tools for natural-language agent control via Claude Desktop",
            "Hermes Agent (OpenRouter / LLaMA 3.3-70B) configured as Telegram-based remote control interface",
        ],
    },
    {
        "title":   "AI Job Hunter Agent",
        "period":  "May 2026",
        "links":   "GitHub",
        "bullets": [
            "7-node n8n workflow deployed on Hostinger VPS — scrapes UAE job boards daily and delivers curated AI-filtered digests via Gmail; zero manual intervention since deployment",
            "Pipeline monitors 5+ platforms simultaneously, filters by role relevance using LLM classification, and delivers a ranked shortlist every morning",
            "End-to-end automation: source scraping → deduplication → AI scoring → formatted email delivery — fully autonomous",
        ],
    },
    {
        "title":   "StyleCode App",
        "period":  "2026 – Present",
        "links":   "stylecode-app.vercel.app",
        "bullets": [
            "Men's fashion advisor web app built solo in React, TypeScript, and Anthropic Claude API — deployed on Vercel and live with UAE-based users",
            "AI styling recommendations across 3 body-type profiles and 4 seasonal colour palettes; affiliate-monetised via Amazon UAE and Noon",
            "Mobile version in development: React Native + Expo + Supabase + Gemini API",
        ],
    },
]

EXPERIENCE = [
    {
        "role":    "Lab Assistant – Perfumery Department",
        "period":  "Sep 2024 – Present",
        "company": "Sterling Perfumes Industries LLC · Dubai, UAE",
        "bullets": [
            "Managed 10,000+ litres of bulk RTF batches monthly at 99% on-time delivery rate across a multi-product fragrance portfolio",
            "Operated SAP ERP for raw material inventory management — stock tracking, near-expiry flagging, uninterrupted supply",
            "Optimised 5 fine fragrance formulations through systematic reformulation, achieving 12% raw material cost reduction with zero scent performance compromise",
            "Authored batch sheets that reduced production team errors and queries by 15%, streamlining R&D-to-production handoffs",
            "Executed 25+ fragrance sample compounding cycles per month; daily QC checks (density, stability, olfactory) — zero critical documentation errors",
        ],
    },
    {
        "role":    "Chemist & QC – Perfumery Department",
        "period":  "Jun 2023 – Jul 2024",
        "company": "Faan Al Ibdaa Perfumes & Cosmetics · Sharjah, UAE",
        "bullets": [
            "Collaborated with 2–4 clients monthly to define requirements and deliver customised fine fragrance samples through the full development cycle",
            "Developed novel perfume formulations and optimised legacy products within 1% target cost deviation",
            "Conducted QC testing on 100% of finished batches; prepared all regulatory documentation (COA, IC, MSDS) for domestic and international distribution",
        ],
    },
]

SKILLS_CATEGORIES = [
    ("AI & Agents",    "Groq API · LLaMA 3.1 · Claude API · Gemini API · MCP Protocol · Telegram Bot API"),
    ("Languages",      "Python 3.12 · Node.js · React / TypeScript · React Native"),
    ("Automation",     "n8n · UiPath RPA (in progress) · GitHub Actions · Workflow Design"),
    ("Infrastructure", "Ubuntu VPS · systemd · Supervisor · Vercel · Supabase"),
    ("Data",           "pandas · pandas-ta · yfinance"),
    ("Enterprise",     "SAP ERP · QC/QA · GLP / EH&S · Fine Fragrance Compounding"),
    ("Soft Skills",    "Systems Thinking · Technical Documentation · Self-directed Learning"),
]

EDUCATION = {
    "degree":  "Bachelor of Technology – Chemical Engineering",
    "period":  "2017 – 2021",
    "school":  "Lovely Professional University · Punjab, India",
}

CERTIFICATIONS = [
    "UiPath RPA Developer Associate — in progress, exam targeted Q3 2026 (v2024.10 Academy curriculum)",
    "UAE Driving License (valid)",
    "Certified – Elementary First Aid & Industrial Safety",
    "Chemical Engineering Computations using MS Excel – Webinar Certificate",
]

LANGUAGES = "English (Fluent) · Malayalam (Native) · Hindi (Proficient)"

FOOTER = "Open to AI Implementation, Automation, and AI Ops roles — Dubai (hybrid/office) or global (remote)"


# ── Style builder ─────────────────────────────────────────────────────────────
def _styles():
    return {
        "name": ParagraphStyle(
            "name", fontSize=22, textColor=DARK, fontName="Helvetica-Bold",
            spaceAfter=1, leading=26,
        ),
        "title_tag": ParagraphStyle(
            "title_tag", fontSize=10, textColor=ACCENT, fontName="Helvetica-Bold",
            spaceAfter=2, leading=13,
        ),
        "tagline": ParagraphStyle(
            "tagline", fontSize=8.5, textColor=MID, fontName="Helvetica-Oblique",
            spaceAfter=4, leading=12,
        ),
        "contact": ParagraphStyle(
            "contact", fontSize=7.8, textColor=MID, fontName="Helvetica",
            spaceAfter=1, leading=11,
        ),
        "section": ParagraphStyle(
            "section", fontSize=9.5, textColor=DARK, fontName="Helvetica-Bold",
            spaceBefore=7, spaceAfter=2, leading=12,
            textTransform="uppercase", letterSpacing=1.2,
        ),
        "proj_title": ParagraphStyle(
            "proj_title", fontSize=9.5, textColor=DARK, fontName="Helvetica-Bold",
            spaceAfter=0, leading=13,
        ),
        "proj_meta": ParagraphStyle(
            "proj_meta", fontSize=8, textColor=LIGHT, fontName="Helvetica-Oblique",
            spaceAfter=2, leading=11,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontSize=8.2, textColor=MID, fontName="Helvetica",
            spaceAfter=1.5, leading=11.5, leftIndent=10, bulletIndent=0,
        ),
        "skill_cat": ParagraphStyle(
            "skill_cat", fontSize=8.2, textColor=DARK, fontName="Helvetica-Bold",
            leading=11,
        ),
        "skill_val": ParagraphStyle(
            "skill_val", fontSize=8.2, textColor=MID, fontName="Helvetica",
            leading=11,
        ),
        "body": ParagraphStyle(
            "body", fontSize=8.2, textColor=MID, fontName="Helvetica",
            spaceAfter=2, leading=11.5,
        ),
        "footer": ParagraphStyle(
            "footer", fontSize=7.5, textColor=ACCENT, fontName="Helvetica-Oblique",
            alignment=TA_CENTER, leading=10,
        ),
    }


def _hr(color=ACCENT, thickness=0.6):
    return HRFlowable(
        width="100%", thickness=thickness, color=color, spaceAfter=4, spaceBefore=2
    )


def _section(title, S):
    return [Paragraph(title, S["section"]), _hr()]


def _bullet(text, S):
    return Paragraph(f"• {text}", S["bullet"])


# ── Main generator ────────────────────────────────────────────────────────────
def generate_cv(
    company_name: str,
    tailored_summary: str,
    tailored_skills: list[str],
) -> str:
    """
    Generate a tailored CV PDF.

    Args:
        company_name:    Used in filename and subtle personalisation
        tailored_summary: Rewritten summary from scorer.py
        tailored_skills:  Reordered skills list from scorer.py

    Returns:
        str: Full path to generated PDF
    """
    # Sanitise company name for filename
    safe_name = re.sub(r'[^\w\s-]', '', company_name).strip().replace(' ', '_')
    filename = f"Shibil_CV_{safe_name}.pdf"
    output_path = os.path.join(CV_OUTPUT_DIR, filename)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
    )

    S = _styles()
    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph(CONTACT["name"], S["name"]))
    story.append(Paragraph(CONTACT["title"], S["title_tag"]))
    story.append(Paragraph(CONTACT["tagline"], S["tagline"]))

    contact_line1 = f"{CONTACT['location']} · {CONTACT['phone']} · {CONTACT['email']}"
    contact_line2 = f"{CONTACT['portfolio']} · {CONTACT['linkedin']} · {CONTACT['github']}"
    story.append(Paragraph(contact_line1, S["contact"]))
    story.append(Paragraph(contact_line2, S["contact"]))
    story.append(_hr(color=DARK, thickness=1.2))
    story.append(Spacer(1, 2))

    # ── Professional Summary (TAILORED) ───────────────────────────────────────
    story += _section("Professional Summary", S)
    story.append(Paragraph(tailored_summary, S["body"]))
    story.append(Spacer(1, 3))

    # ── Projects ──────────────────────────────────────────────────────────────
    story += _section("Projects", S)
    for proj in PROJECTS:
        # Title + date on same row
        title_date = Table(
            [[Paragraph(proj["title"], S["proj_title"]),
              Paragraph(proj["period"], S["proj_meta"])]],
            colWidths=["75%", "25%"],
        )
        title_date.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN",  (1, 0), (1, 0),  "RIGHT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(title_date)
        story.append(Paragraph(proj["links"], S["proj_meta"]))
        for b in proj["bullets"]:
            story.append(_bullet(b, S))
        story.append(Spacer(1, 4))

    # ── Work Experience ───────────────────────────────────────────────────────
    story += _section("Work Experience", S)
    for exp in EXPERIENCE:
        title_date = Table(
            [[Paragraph(exp["role"], S["proj_title"]),
              Paragraph(exp["period"], S["proj_meta"])]],
            colWidths=["75%", "25%"],
        )
        title_date.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ("ALIGN",  (1, 0), (1, 0),  "RIGHT"),
            ("LEFTPADDING",  (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",   (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
        ]))
        story.append(title_date)
        story.append(Paragraph(exp["company"], S["proj_meta"]))
        for b in exp["bullets"]:
            story.append(_bullet(b, S))
        story.append(Spacer(1, 4))

    # ── Skills (TAILORED — reordered) ────────────────────────────────────────
    story += _section("Skills", S)

    # Top skills from scorer (reordered for this job) shown as highlight row
    top_skills_text = " · ".join(tailored_skills[:6])
    story.append(Paragraph(
        f'<font color="#2563eb"><b>Top match for this role:</b></font> {top_skills_text}',
        S["body"]
    ))
    story.append(Spacer(1, 3))

    # Full categorised skills table
    skill_rows = []
    for cat, val in SKILLS_CATEGORIES:
        skill_rows.append([
            Paragraph(cat, S["skill_cat"]),
            Paragraph(val, S["skill_val"]),
        ])

    skill_table = Table(skill_rows, colWidths=["22%", "78%"])
    skill_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(skill_table)
    story.append(Spacer(1, 3))

    # ── Education ─────────────────────────────────────────────────────────────
    story += _section("Education", S)
    edu_row = Table(
        [[Paragraph(EDUCATION["degree"], S["proj_title"]),
          Paragraph(EDUCATION["period"], S["proj_meta"])]],
        colWidths=["75%", "25%"],
    )
    edu_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN",  (1, 0), (1, 0),  "RIGHT"),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",   (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 0),
    ]))
    story.append(edu_row)
    story.append(Paragraph(EDUCATION["school"], S["proj_meta"]))
    story.append(Spacer(1, 3))

    # ── Certifications ────────────────────────────────────────────────────────
    story += _section("Certifications", S)
    for cert in CERTIFICATIONS:
        story.append(_bullet(cert, S))
    story.append(Spacer(1, 3))

    # ── Languages ─────────────────────────────────────────────────────────────
    story += _section("Languages", S)
    story.append(Paragraph(LANGUAGES, S["body"]))
    story.append(Spacer(1, 6))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(_hr(color=ACCENT, thickness=0.4))
    story.append(Paragraph(FOOTER, S["footer"]))

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.build(story)
    print(f"✅ CV generated: {output_path}")
    return output_path


# ── Smoke test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=== CV Generator Smoke Test ===\n")

    # Simulate what scorer.py returns
    test_summary = (
        "AI Automation Developer with 3+ years of hands-on experience building and deploying "
        "production-grade automated workflows using n8n and Python. I specialise in developing "
        "AI agents powered by LLM APIs (Claude, Groq), integrating REST APIs and third-party "
        "services, and managing infrastructure on Ubuntu VPS. I've built a live 7-node n8n job "
        "pipeline, a 24/7 autonomous trading agent with Telegram notifications, and deployed "
        "multiple automation systems on Linux servers. Seeking to leverage my workflow automation "
        "expertise and AI integration skills to drive automation initiatives in Dubai."
    )

    test_skills = [
        "n8n workflow automation (7-node pipelines, VPS-deployed, multi-service integration)",
        "Python scripting (agents, scrapers, data pipelines, automation)",
        "LLM API integration (Claude API, Groq API, prompt engineering)",
        "REST API integration and third-party service orchestration",
        "Ubuntu/Linux server administration (Hostinger KVM VPS, Supervisor, Cron jobs)",
        "Playwright (web scraping, browser automation)",
        "React / TypeScript / Vite (frontend development)",
        "Google Sheets API (data logging, reporting)",
        "UiPath RPA (Developer Associate — in progress)",
        "GitHub Actions (CI/CD workflows)",
        "Telegram Bot API",
        "ReportLab (PDF generation)",
    ]

    path = generate_cv(
        company_name="TechCorp Dubai",
        tailored_summary=test_summary,
        tailored_skills=test_skills,
    )

    print(f"\nFile saved to: {path}")
    import os
    size = os.path.getsize(path)
    print(f"File size: {size:,} bytes ({size//1024} KB)")
    print("\n✅ CV generation complete. Check /root/job-hunter/cvs/")
