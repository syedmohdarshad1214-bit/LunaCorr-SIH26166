"""Render the LunaCorr 120-second demo runbook as a printable two-page PDF."""
from html import escape
from pathlib import Path
import re

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/demo/LunaCorr_120_second_demo_runbook.md"
OUTPUT = ROOT / "output/pdf/LunaCorr_2_Minute_Prototype_Demo_Script.pdf"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

pdfmetrics.registerFont(TTFont("ArialLocal", "/System/Library/Fonts/Supplemental/Arial.ttf"))
pdfmetrics.registerFont(TTFont("ArialLocal-Bold", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"))
pdfmetrics.registerFontFamily("ArialLocal", normal="ArialLocal", bold="ArialLocal-Bold")

INK = colors.HexColor("#222629")
MUTED = colors.HexColor("#565D60")
GOLD = colors.HexColor("#A1844A")
GOLD_PALE = colors.HexColor("#F2ECDF")
RUST = colors.HexColor("#A9665B")
LINE = colors.HexColor("#D9D5CB")
PAPER = colors.HexColor("#FBFAF6")

styles = {
    "eyebrow": ParagraphStyle("eyebrow", fontName="ArialLocal-Bold", fontSize=8.2, leading=11, textColor=GOLD, spaceAfter=7),
    "title": ParagraphStyle("title", fontName="ArialLocal-Bold", fontSize=23, leading=27, textColor=INK, spaceAfter=8),
    "deck": ParagraphStyle("deck", fontName="ArialLocal", fontSize=9.1, leading=13.1, textColor=MUTED, spaceAfter=14),
    "section": ParagraphStyle("section", fontName="ArialLocal-Bold", fontSize=11, leading=14, textColor=INK, spaceBefore=13, spaceAfter=7),
    "body": ParagraphStyle("body", fontName="ArialLocal", fontSize=8.7, leading=12.5, textColor=INK, spaceAfter=7),
    "small": ParagraphStyle("small", fontName="ArialLocal", fontSize=8, leading=11.2, textColor=MUTED, spaceAfter=5),
    "table": ParagraphStyle("table", fontName="ArialLocal", fontSize=7.8, leading=10.8, textColor=INK),
    "tablehead": ParagraphStyle("tablehead", fontName="ArialLocal-Bold", fontSize=7.6, leading=10, textColor=INK),
    "cue": ParagraphStyle("cue", fontName="ArialLocal-Bold", fontSize=8.6, leading=12.2, textColor=INK),
}


def rich(value):
    value = escape(value.strip())
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`(.+?)`", r"<font name='ArialLocal-Bold'>\1</font>", value)
    value = value.replace("“", "").replace("”", "")
    return value


def para(value, style="body"):
    return Paragraph(rich(value), styles[style])


def timeline(rows):
    cells = [[para("TIME", "tablehead"), para("SHOW / CLICK", "tablehead"), para("SAY", "tablehead")]]
    for time, action, spoken in rows:
        cells.append([para(time, "cue"), para(action, "table"), para(spoken, "table")])
    table = Table(cells, colWidths=[79, 202, 214], hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD_PALE),
        ("LINEBELOW", (0, 0), (-1, 0), 1, GOLD),
        ("LINEBELOW", (0, 1), (-1, -1), .5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def callout(title, text, accent=GOLD):
    box = Table([[para(title, "cue")], [para(text, "body")]], colWidths=[495], hAlign="LEFT")
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD_PALE),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
    ]))
    return box


def frame(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, *A4, fill=1, stroke=0)
    canvas.setFillColor(INK)
    canvas.rect(0, A4[1]-10, A4[0], 10, fill=1, stroke=0)
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(1)
    canvas.line(50, 41, A4[0]-50, 41)
    canvas.setFillColor(MUTED)
    canvas.setFont("ArialLocal", 7.2)
    canvas.drawString(50, 28, "LunaCorr | 120-second judge demo | real-data claim boundaries")
    canvas.drawRightString(A4[0]-50, 28, f"{doc.page} / 2")
    canvas.restoreState()


def main():
    lines = SOURCE.read_text().splitlines()
    rows = []
    for line in lines:
        if line.startswith("| **"):
            parts = [x.strip() for x in line.strip().strip("|").split("|")]
            if len(parts) == 3:
                rows.append(tuple(parts))
    if len(rows) != 9:
        raise ValueError(f"Expected nine timed beats; found {len(rows)}")

    story = [
        para("LUNACORR / PRESENTATION RUNBOOK", "eyebrow"),
        para("Two minutes. Two decisions. One standard of proof.", "title"),
        para("A screen-recording script built around real OHRC and TMC-2 audits. The visible IIRS catalogue footprint remains an unverified pixel-registration candidate.", "deck"),
        callout("Opening line", "A glowing overlap on the Moon can be wrong. Point to the three sensor options, then make the judges challenge the evidence."),
        para("0:00–1:14 / Candidate to registered local region", "section"),
        timeline(rows[:5]),
        PageBreak(),
        para("LUNACORR / LIVE DEMONSTRATION", "eyebrow"),
        para("Show the system saying no", "title"),
        para("Finish the live prototype, then hold the rejected verdict on screen. This is the contrast the judges should remember.", "deck"),
        timeline(rows[5:]),
        para("If a judge asks about IIRS", "section"),
        callout("Use this exact boundary", "IIRS records infrared spectra at roughly 80 m per pixel across about 256 bands. Its footprint candidates appear on the globe, but no TMC-2-to-IIRS science-pixel registration is certified in this demo. Fine OHRC craters cannot be recovered by enlarging IIRS pixels. The next leg must pass geometry-bounded structural matching and independent checks; until then, LunaCorr abstains.", RUST),
        para("Recording checks", "section"),
        para("Record at 1080p or higher with clear narration. Show the registered and rejected result for at least three seconds each. Scroll inside the white report to inspect its pages; scroll the dark panel margin to reach SIFT/AKAZE. If time runs long, omit Terrain swipe but preserve both decisions and held-out numbers.", "small"),
        para("Claim boundary: REALPAIR005 is relative local OHRC-to-TMC-2 registration on the native 5 m TMC ortho grid. REALPAIR001 is rejected with zero accepted science control points. Catalogue triple-overlap rings do not prove OHRC-TMC-2-IIRS registration.", "small"),
    ]
    doc = SimpleDocTemplate(str(OUTPUT), pagesize=A4, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=55,
                            title="LunaCorr 2-minute prototype demo script", author="LunaCorr")
    doc.build(story, onFirstPage=frame, onLaterPages=frame)
    print(OUTPUT)


if __name__ == "__main__":
    main()
