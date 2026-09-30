"""Build judge-readable PDFs from the frozen REALPAIR001 and REALPAIR005 audits."""
from pathlib import Path
import json
import shutil
import subprocess

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
SCIENCE = ROOT / "data/derived/REALPAIR005_science_v1"
REJECTED = ROOT / "data/derived/REALPAIR001_adjusted_registration_v5"
OUT = ROOT / "output/pdf"
OUT.mkdir(parents=True, exist_ok=True)

INK = colors.HexColor("#23282B")
MUTED = colors.HexColor("#596266")
GOLD = colors.HexColor("#A47F38")
GOLD_PALE = colors.HexColor("#F3EDDF")
RUST = colors.HexColor("#A45249")
RUST_PALE = colors.HexColor("#F5E9E6")
LINE = colors.HexColor("#D9D7D1")
PAPER = colors.HexColor("#FBFAF7")

styles = {
    "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=8, leading=11, textColor=GOLD, spaceAfter=8, tracking=1.1),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=INK, spaceAfter=9),
    "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9.1, leading=13, textColor=MUTED, spaceAfter=14),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=INK, spaceBefore=15, spaceAfter=8),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.7, leading=13.2, textColor=INK, spaceAfter=8),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, leading=10.5, textColor=MUTED, spaceAfter=7),
    "table": ParagraphStyle("table", fontName="Helvetica", fontSize=7.1, leading=10, textColor=INK),
    "tablehead": ParagraphStyle("tablehead", fontName="Helvetica-Bold", fontSize=7.2, leading=10, textColor=INK),
    "mono": ParagraphStyle("mono", fontName="Courier", fontSize=6.6, leading=9.5, textColor=INK),
    "caption": ParagraphStyle("caption", fontName="Helvetica", fontSize=7.3, leading=10, textColor=MUTED, alignment=TA_CENTER, spaceAfter=10),
}


def P(text, kind="body"):
    return Paragraph(text, styles[kind])


def table(headers, rows, widths, accent=GOLD):
    cells = [[P(str(x), "tablehead") for x in headers]]
    cells += [[P(str(x), "table") for x in row] for row in rows]
    result = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), GOLD_PALE if accent == GOLD else RUST_PALE),
        ("LINEBELOW", (0, 0), (-1, 0), 1, accent),
        ("LINEBELOW", (0, 1), (-1, -1), .45, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return result


def verdict(label, detail, accent=GOLD):
    bg = GOLD_PALE if accent == GOLD else RUST_PALE
    inner = Table([[P(label, "h2"), P(detail, "small")]], colWidths=[169, 326])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return inner


def img(path, max_w, max_h):
    w, h = ImageReader(str(path)).getSize()
    scale = min(max_w / w, max_h / h)
    return Image(str(path), width=w * scale, height=h * scale)


def frame(canvas, doc, label, accent):
    canvas.saveState()
    canvas.setFillColor(PAPER)
    canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    canvas.setFillColor(INK)
    canvas.rect(0, A4[1] - 12, A4[0], 12, fill=1, stroke=0)
    canvas.setStrokeColor(accent)
    canvas.setLineWidth(1)
    canvas.line(50, 39, A4[0] - 50, 39)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(50, 27, f"LunaCorr | {label} | real Chandrayaan-2 data")
    canvas.drawRightString(A4[0] - 50, 27, f"{doc.page}")
    canvas.restoreState()


def make_doc(path, story, label, accent):
    doc = SimpleDocTemplate(
        str(path), pagesize=A4, rightMargin=50, leftMargin=50,
        topMargin=48, bottomMargin=55, title=f"LunaCorr {label}",
        author="LunaCorr scientific audit",
    )
    doc.build(story, onFirstPage=lambda c, d: frame(c, d, label, accent),
              onLaterPages=lambda c, d: frame(c, d, label, accent))


def registered():
    decision = json.loads((SCIENCE / "aligned_middle_decision.json").read_text())
    sift = json.loads((SCIENCE / "science_roi_aligned_middle_test/SIFT/metrics.json").read_text())
    akaze = json.loads((SCIENCE / "science_roi_aligned_middle_test/AKAZE/metrics.json").read_text())
    story = [
        P("SCIENTIFIC EVIDENCE / REALPAIR005", "eyebrow"),
        P("A local overlap that passes the test", "title"),
        P("OHRC to TMC-2 | Frozen middle-region audit | Relative image registration", "subtitle"),
        verdict("REGISTERED - LOCAL", "The tested middle ROI passes camera/terrain, SIFT, AKAZE, coverage and reverse checks. The full OHRC strip and absolute 5 m lunar position remain ABSTAIN."),
        P("1 / What was tested", "h2"),
        P("Real OHRC science pixels were projected through their camera model and a TMC-2 DTM onto the native 5 m TMC-2 ortho grid. The audited OHRC native range is samples 1,000-11,000 and lines 42,000-58,000. The XML footprint intersection is 80.356 km²; that polygon alone is not proof of registration."),
        table(["Instrument", "Exact product ID", "Role"], [
            ["OHRC", decision["products"]["ohrc"], "Fine-scale optical source"],
            ["TMC-2", decision["products"]["tmc_ortho"], "5 m ortho target"],
            ["TMC-2 DTM", decision["products"]["tmc_dtm"], "Terrain projection"],
        ], [68, 326, 101]),
        P("2 / Frozen image evidence", "h2"),
        P("Each method used a fixed reciprocal/ratio search, candidate window and affine RANSAC gate. Held-out spatial bins were excluded from fitting. Errors are in <b>native 5 m TMC-2 pixels</b>, not OHRC pixels or absolute lunar ground error."),
        table(["Method", "Train", "Held-out", "RMSE / P90", "Spread"], [
            ["SIFT", f'{sift["training_inliers"]}/{sift["training_candidates"]}', f'{sift["heldout_inliers"]}/{sift["heldout_candidates"]} ({sift["heldout_inlier_ratio"]*100:.1f}%)', f'{sift["rmse_tmc_5m_px"]:.2f} / {sift["p90_residual_tmc_5m_px"]:.2f} px', f'{sift["occupied_cells_3x6"]}/18; {sift["hull_fraction"]*100:.1f}% hull'],
            ["AKAZE", f'{akaze["training_inliers"]}/{akaze["training_candidates"]}', f'{akaze["heldout_inliers"]}/{akaze["heldout_candidates"]} ({akaze["heldout_inlier_ratio"]*100:.1f}%)', f'{akaze["rmse_tmc_5m_px"]:.2f} / {akaze["p90_residual_tmc_5m_px"]:.2f} px', f'{akaze["occupied_cells_3x6"]}/18; {akaze["hull_fraction"]*100:.1f}% hull'],
        ], [63, 61, 123, 112, 136]),
        P("Fixed minimum: 6 training inliers at 40%, 3 held-out at 40%, 6/18 occupied cells, 15% hull and 3 TMC-pixel median reverse closure. Separately fitted reverse medians: SIFT 1.26 px; AKAZE 2.20 px. The 878 and 410 accepted match counts overlap and cannot be added as distinct ground-control points.", "small"),
        PageBreak(),
        P("EVIDENCE PLATE / REALPAIR005", "eyebrow"),
        P("Terrain agreement at the tested scale", "title"),
        P("The saved figures below come from the frozen science-pixel audit. Image alignment and match support are shown separately so a visual overlay cannot substitute for the fixed tests.", "subtitle"),
    ]
    figures = Table([[
        img(SCIENCE / "aligned_middle_evidence/local_affine_overlay.png", 230, 300),
        img(SCIENCE / "aligned_middle_evidence/sift_heldout_correspondences.png", 250, 300),
    ]], colWidths=[245, 250], hAlign="LEFT")
    figures.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    story += [
        figures,
        P("Left: saved local affine overlay. Right: held-out SIFT correspondences. Both are science-data figures, not a full-strip accuracy map.", "caption"),
        P("3 / Independent checks and evidence boundary", "h2"),
        P("The DTM navigation was compared with LOLA terrain, and OHRC was screened independently against LOLA hillshade at 120 m cells. Alternative TMC locations 20 km north and 10 km south failed the same matcher settings. These support the local association without establishing surveyed 5 m absolute coordinates."),
        P("<b>Scope of the decision:</b> relative local OHRC-to-TMC-2 correspondence only. Prior full-strip affine transfer failed outside this middle ROI. The local affine can absorb camera/terrain residuals. No IIRS science-pixel registration is claimed here."),
        P("4 / Reproducibility", "h2"),
        P("Audit ID: <b>REALPAIR005_OHRC_TMC_ALIGNED_MIDDLE_VERIFICATION_V1</b>. Fixed gates are in aligned_candidate_config_v1.json. SIFT and AKAZE each retain config.json, matches.csv, inliers.csv, reverse_matches.csv, transform.json and metrics.json. The scoped decision is aligned_middle_decision.json; aligned_middle_sha256_v2.txt binds derived artifacts. The original science labels and product hashes are listed in the full scientific verification document.", "small"),
        P("Source: data/derived/REALPAIR005_science_v1/ALIGNED_MIDDLE_SCIENTIFIC_VERIFICATION.md", "mono"),
    ]
    make_doc(OUT / "LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf", story, "REALPAIR005 registered local report", GOLD)


def rejected():
    proof = json.loads((REJECTED / "audit_summary.json").read_text())
    story = [
        P("SCIENTIFIC EVIDENCE / REALPAIR001", "eyebrow"),
        P("A plausible overlap that fails the test", "title"),
        P("OHRC to TMC-2 | Adjusted-camera audit | Real science data", "subtitle"),
        verdict("REJECTED - CONSISTENCY", "The footprints overlap, but image-derived displacement and independent terrain geometry disagree. Accepted science control points: zero.", RUST),
        P("1 / What was tested", "h2"),
        P("The original OHRC science image and TMC-2 ortho were evaluated with an adjusted OHRC camera, real TMC DTM and independent ASP terrain alignment. This is the earlier candidate, separate from the later REALPAIR005 local registration."),
        table(["Instrument", "Exact product ID", "Role"], [
            ["OHRC", "ch2_ohr_nrp_20200827T0030107497_d_img_d18", "Optical source"],
            ["TMC-2", "ch2_tmc_ndn_20231101T0125121377_d_oth_d18", "5 m ortho target"],
            ["TMC-2 DTM", "ch2_tmc_ndn_20231101T0125121377_d_dtm_d18", "Terrain reference"],
        ], [68, 326, 101], RUST),
        P("2 / Why it is rejected", "h2"),
        table(["Gate", "Measured result", "Decision"], [
            ["Camera / DTM", "ISIS-CSM maximum round trip 0.014 OHRC px; stereo adjustment 10,690 points", "Internal geometry passes"],
            ["SIFT support", f'{proof["sift"]["training"]} training; {proof["sift"]["heldout"]} held-out; {proof["sift"]["coverage_cells"]} cells', "Fails held-out and spread"],
            ["AKAZE support", f'{proof["akaze"]["training"]} training; {proof["akaze"]["heldout"]} held-out', "Point ratio passes"],
            ["AKAZE coverage", f'{proof["akaze"]["coverage_cells"]} cells; {proof["akaze"]["hull_fraction"]*100:.1f}% hull versus 15% gate', "Fails spatial coverage"],
            ["Independent geometry", f'{proof["descriptor_displacement"]["akaze_median_m"]/1000:.2f} km image shift versus {proof["pc_align"]["translation_magnitude_m"]/1000:.2f} km ASP terrain estimate', "Conflict"],
        ], [103, 280, 112], RUST),
        P("The ~6.97 km image shift remains a hypothesis. It was not applied as a camera correction or accepted as a control network. SIFT and AKAZE can agree on repeated crater texture while still selecting the wrong physical region.", "small"),
        PageBreak(),
        P("EVIDENCE PLATE / REALPAIR001", "eyebrow"),
        P("A shared map frame is not a match", "title"),
        P("The images below are real science-data context from the earlier camera audit. They show where the camera projected OHRC and the TMC ortho lie on the same 5 m map grid; they do not certify pixel correspondence.", "subtitle"),
        img(ROOT / "data/derived/REALPAIR001_camera_audit_v2/science_comparison.png", 470, 405),
        P("Earlier projection comparison only. The final v5 rejection uses an adjusted camera and frozen matcher/terrain metrics, reported above.", "caption"),
        P("3 / Evidence boundary", "h2"),
        P("Stereo bundle adjustment and camera-model equivalence validate internal OHRC geometry, not its absolute tie to TMC-2. Illumination and shadows make this pair difficult, but the audit does not identify them as the sole cause. The independent ASP alignment of 10,690 OHRC terrain points to the TMC DTM estimated 649.64 m translation and 97.88 m output RMSE; those are terrain-alignment results, not accepted image control points."),
        P("4 / Reproducibility", "h2"),
        P("Audit ID: <b>REALPAIR001_adjusted_registration_v5</b>. audit_summary.json records the decision. The SIFT and AKAZE experiment folders contain frozen config, matches, inliers, reverse matches, transform, metrics and manifest files. pc_align/ retains independent terrain results; checksums.sha256 binds the critical artifacts. The next valid action is a new illumination-compatible pair or independent lunar control with untouched validation data.", "small"),
        P("Source: data/derived/REALPAIR001_adjusted_registration_v5/SCIENTIFIC_REPORT.md", "mono"),
    ]
    make_doc(OUT / "LunaCorr_REALPAIR001_Rejected_Consistency_Scientific_Report.pdf", story, "REALPAIR001 rejected consistency report", RUST)


if __name__ == "__main__":
    registered()
    rejected()
    published = ROOT / "frontend/assets/reports"
    published.mkdir(parents=True, exist_ok=True)
    for report in (
        "LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf",
        "LunaCorr_REALPAIR001_Rejected_Consistency_Scientific_Report.pdf",
    ):
        shutil.copy2(OUT / report, published / report)
    for source, prefix in (
        ("LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf", "registered-page"),
        ("LunaCorr_REALPAIR001_Rejected_Consistency_Scientific_Report.pdf", "rejected-page"),
    ):
        subprocess.run(
            ["pdftoppm", "-f", "1", "-l", "2", "-scale-to", "1400", "-png",
             str(OUT / source), str(published / prefix)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    print(OUT / "LunaCorr_REALPAIR005_Registered_Local_Scientific_Report.pdf")
    print(OUT / "LunaCorr_REALPAIR001_Rejected_Consistency_Scientific_Report.pdf")
