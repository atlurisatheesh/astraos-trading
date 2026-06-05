from __future__ import annotations

import io
import hashlib
import os
import time
import textwrap
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "generated"
IMG_DIR = OUT_DIR / "real_images"
OUT_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)

PDF_PATH = OUT_DIR / "Satheesh_Organic_Fertilizer_Master_Manual_V1_Real_Images.pdf"


GREEN = colors.HexColor("#1B4332")
LIGHT_GREEN = colors.HexColor("#52B788")
PALE_GREEN = colors.HexColor("#EAF7EF")
GOLD = colors.HexColor("#F9C74F")
DARK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5C6B73")
RED = colors.HexColor("#9B2226")
ORANGE = colors.HexColor("#CA6702")
BLUE = colors.HexColor("#1D4E89")


@dataclass
class Photo:
    key: str
    title: str
    filename: str
    credit: str
    license: str
    url: str


PHOTOS = [
    Photo(
        "raw_mango",
        "Raw mangoes for fermented fruit juice",
        "Raw_Mango.jpg",
        "Sambit 1982, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:Raw_Mango.jpg",
    ),
    Photo(
        "jackfruit",
        "Jackfruit pulp/waste material for composting",
        "Jackfruit_Pulp.jpg",
        "Gharouni, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:Jackfruit_Pulp.jpg",
    ),
    Photo(
        "kitchen_scraps",
        "Vegetable/kitchen scraps for compost and bokashi",
        "Nothing_will_be_wasted!_Kitchen_scraps_for_compost!.jpg",
        "Anna.Massini, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:Nothing_will_be_wasted!_Kitchen_scraps_for_compost!.jpg",
    ),
    Photo(
        "cow_dung",
        "Cow dung compost/manure input",
        "Cow_dung_compost.jpg",
        "Sindugab, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:Cow_dung_compost.jpg",
    ),
    Photo(
        "bokashi_bucket",
        "DIY bokashi bucket",
        "DIY_bokashi_bucket.jpg",
        "Zenyrgarden, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:DIY_bokashi_bucket.jpg",
    ),
    Photo(
        "bokashi_content",
        "Inside a bokashi bucket",
        "Bokashi_composting_bucket_content.jpg",
        "Zenyrgarden, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:Bokashi_composting_bucket_content.jpg",
    ),
    Photo(
        "bokashi_white",
        "White bloom/mycelium in bokashi bucket",
        "White_bloom_bokashi_bucket.jpg",
        "Zenyrgarden, Wikimedia Commons",
        "CC BY-SA 4.0",
        "https://commons.wikimedia.org/wiki/File:White_bloom_bokashi_bucket.jpg",
    ),
    Photo(
        "compost_pile",
        "Compost pile of yard waste",
        "Compost_pile_of_yard_waste.jpg",
        "Joe Hoover, Wikimedia Commons/Flickr",
        "CC BY 2.0",
        "https://commons.wikimedia.org/wiki/File:Compost_pile_of_yard_waste.jpg",
    ),
    Photo(
        "biochar",
        "Biochar pile",
        "Biochar_pile.jpg",
        "N/A, Wikimedia Commons",
        "Wikimedia Commons listed license",
        "https://commons.wikimedia.org/wiki/File:Biochar_pile.jpg",
    ),
]


def commons_redirect_url(filename: str) -> str:
    return "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + urllib.parse.quote(filename)


def commons_thumb_url(filename: str, width: int = 1024) -> str:
    normalized = filename.replace(" ", "_")
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    quoted = urllib.parse.quote(normalized)
    return f"https://upload.wikimedia.org/wikipedia/commons/thumb/{digest[0]}/{digest[:2]}/{quoted}/{width}px-{quoted}"


def download_photos() -> dict[str, Path]:
    result = {}
    for photo in PHOTOS:
        out = IMG_DIR / photo.filename.replace("!", "").replace(" ", "_")
        result[photo.key] = out
        if out.exists() and out.stat().st_size > 20_000:
            continue
        try:
            data = None
            urls = [
                commons_redirect_url(photo.filename),
                commons_thumb_url(photo.filename, 1024),
                commons_thumb_url(photo.filename, 800),
            ]
            for attempt, url in enumerate(urls):
                req = urllib.request.Request(url, headers={"User-Agent": "SatheeshFarmManual/1.0 educational"})
                try:
                    with urllib.request.urlopen(req, timeout=35) as resp:
                        data = resp.read()
                    break
                except Exception:
                    if attempt == len(urls) - 1:
                        raise
                    time.sleep(2 + attempt * 2)
            if data is None:
                raise RuntimeError("empty download")
            Image.open(io.BytesIO(data)).verify()
            out.write_bytes(data)
            time.sleep(1.5)
        except Exception as exc:
            print(f"WARNING: failed to download {photo.filename}: {exc}")
    return result


class NumberedCanvas:
    def __init__(self, canvas, doc):
        self.canvas = canvas
        self.doc = doc


def on_page(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(GREEN)
    canvas.rect(0, height - 1.0 * cm, width, 1.0 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawString(1.35 * cm, height - 0.65 * cm, "Satheesh Organic Fertilizer Master Manual")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 1.35 * cm, height - 0.65 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(LIGHT_GREEN)
    canvas.setLineWidth(0.8)
    canvas.line(1.35 * cm, 1.25 * cm, width - 1.35 * cm, 1.25 * cm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(width / 2, 0.82 * cm, "Practical natural farming guide for Chittoor terrace systems")
    canvas.restoreState()


class DiagramBox(Flowable):
    def __init__(self, title, kind, width=16.8 * cm, height=8.5 * cm):
        super().__init__()
        self.title = title
        self.kind = kind
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return min(self.width, availWidth), self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(colors.HexColor("#F7FBF8"))
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(LIGHT_GREEN)
        c.setLineWidth(1.2)
        c.roundRect(0, 0, w, h, 8, fill=0, stroke=1)
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(0.35 * cm, h - 0.55 * cm, self.title)
        if self.kind == "terrace_stack":
            labels = [
                ("Grow bags / bins / drums", "#52B788"),
                ("Raised stand or plastic pallet: 2-4 inch air gap", "#95D5B2"),
                ("Drain tray + outlet pipe to terrace drain", "#B7E4C7"),
                ("Geotextile protection sheet", "#D8F3DC"),
                ("Elastomeric waterproof membrane", "#F9C74F"),
                ("Existing RCC terrace slab", "#CAD2C5"),
            ]
            y = h - 1.5 * cm
            for label, col in labels:
                c.setFillColor(colors.HexColor(col))
                c.roundRect(1.0 * cm, y - 0.55 * cm, w - 2.0 * cm, 0.48 * cm, 4, fill=1, stroke=0)
                c.setFillColor(DARK)
                c.setFont("Helvetica", 8.8)
                c.drawCentredString(w / 2, y - 0.39 * cm, label)
                y -= 0.78 * cm
            c.setFillColor(RED)
            c.setFont("Helvetica-Bold", 9)
            c.drawString(1.0 * cm, 0.55 * cm, "Rule: no wet compost, grow bag, or water tank directly on tile/slab.")
        elif self.kind == "fpj_flow":
            steps = ["Collect", "Wash lightly", "Chop", "Layer jaggery", "Ferment", "Filter", "Store"]
            x0, y = 0.7 * cm, h / 2
            gap = (w - 1.4 * cm) / len(steps)
            for i, step in enumerate(steps):
                x = x0 + i * gap
                c.setFillColor(LIGHT_GREEN if i % 2 == 0 else GOLD)
                c.circle(x + gap / 2 - 0.2 * cm, y, 0.48 * cm, fill=1, stroke=0)
                c.setFillColor(DARK)
                c.setFont("Helvetica-Bold", 7.5)
                c.drawCentredString(x + gap / 2 - 0.2 * cm, y - 0.06 * cm, str(i + 1))
                c.setFont("Helvetica", 7.5)
                c.drawCentredString(x + gap / 2 - 0.2 * cm, y - 0.78 * cm, step)
                if i < len(steps) - 1:
                    c.setStrokeColor(GREEN)
                    c.line(x + gap - 0.55 * cm, y, x + gap + 0.05 * cm, y)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 8.4)
            c.drawCentredString(w / 2, 1.0 * cm, "Mango FPJ/FFJ is a concentrate: apply only after dilution.")
        elif self.kind == "bokashi_bucket":
            c.setStrokeColor(GREEN)
            c.setLineWidth(2)
            c.roundRect(5.2 * cm, 1.1 * cm, 6.4 * cm, 5.8 * cm, 10, fill=0, stroke=1)
            c.setFillColor(GOLD)
            c.rect(5.5 * cm, 5.6 * cm, 5.8 * cm, 0.55 * cm, fill=1, stroke=0)
            c.setFillColor(LIGHT_GREEN)
            c.rect(5.5 * cm, 4.55 * cm, 5.8 * cm, 0.75 * cm, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#B08968"))
            c.rect(5.5 * cm, 3.45 * cm, 5.8 * cm, 0.75 * cm, fill=1, stroke=0)
            c.setFillColor(LIGHT_GREEN)
            c.rect(5.5 * cm, 2.35 * cm, 5.8 * cm, 0.75 * cm, fill=1, stroke=0)
            c.setFillColor(BLUE)
            c.rect(8.0 * cm, 1.15 * cm, 0.8 * cm, 0.35 * cm, fill=1, stroke=0)
            labels = [
                ("Airtight lid", 5.85),
                ("Food waste layer", 4.85),
                ("Bokashi bran", 3.75),
                ("Food waste layer", 2.65),
                ("Drain leachate every 2-3 days", 1.35),
            ]
            c.setFont("Helvetica", 8.2)
            c.setFillColor(DARK)
            for label, yy in labels:
                c.drawString(12.0 * cm, yy * cm, label)
        elif self.kind == "compost_layer":
            layers = [
                ("Dry sticks for air channels", "#8D6E63"),
                ("Dry leaves / cocopeat / straw", "#C2A878"),
                ("Fruit + vegetable waste", "#52B788"),
                ("Cow dung slurry / Jeevamrutham", "#6D4C41"),
                ("Thin soil / old compost layer", "#A3B18A"),
            ]
            y = 1.05 * cm
            for label, col in layers:
                c.setFillColor(colors.HexColor(col))
                c.rect(1.2 * cm, y, w - 2.4 * cm, 0.82 * cm, fill=1, stroke=0)
                c.setFillColor(colors.white if col in ["#6D4C41", "#8D6E63"] else DARK)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(w / 2, y + 0.28 * cm, label)
                y += 0.9 * cm
            c.setFillColor(RED)
            c.setFont("Helvetica-Bold", 8.5)
            c.drawString(1.2 * cm, h - 1.1 * cm, "Repeat layers until bin is 80% full. Keep moisture like a squeezed cloth.")
        elif self.kind == "biochar_pit":
            c.setFillColor(colors.HexColor("#6B705C"))
            c.ellipse(2 * cm, 1.0 * cm, w - 2 * cm, 2.2 * cm, fill=1, stroke=0)
            c.setFillColor(colors.black)
            c.ellipse(3.0 * cm, 1.25 * cm, w - 3.0 * cm, 2.0 * cm, fill=1, stroke=0)
            c.setFillColor(ORANGE)
            for x in [5, 7, 9, 11]:
                c.circle(x * cm, 4.4 * cm, 0.22 * cm, fill=1, stroke=0)
                c.line(x * cm, 2.3 * cm, x * cm, 4.2 * cm)
            c.setFillColor(DARK)
            c.setFont("Helvetica", 8.5)
            notes = [
                "1. Burn dry biomass with limited oxygen.",
                "2. Stop before it turns into white ash.",
                "3. Quench fully with water.",
                "4. Crush and charge in Jeevamrutham for 7 days.",
            ]
            for i, note in enumerate(notes):
                c.drawString(0.8 * cm, (h - 1.4 * cm) - i * 0.52 * cm, note)
        elif self.kind == "storage":
            items = [
                ("Fresh", "Jeevamrutham", "3-7 days", "#52B788"),
                ("Medium", "FPJ / FFJ / Bokashi liquid", "3-12 months", "#F9C74F"),
                ("Long", "Compost / dry powders", "1-2 years", "#95D5B2"),
                ("Permanent", "Biochar", "Years", "#343A40"),
            ]
            x = 0.8 * cm
            for label, name, life, col in items:
                c.setFillColor(colors.HexColor(col))
                c.roundRect(x, 2.1 * cm, 3.7 * cm, 3.5 * cm, 8, fill=1, stroke=0)
                c.setFillColor(colors.white if col == "#343A40" else DARK)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(x + 1.85 * cm, 4.75 * cm, label)
                c.setFont("Helvetica", 7.5)
                c.drawCentredString(x + 1.85 * cm, 3.7 * cm, name)
                c.setFont("Helvetica-Bold", 8)
                c.drawCentredString(x + 1.85 * cm, 2.75 * cm, life)
                x += 4.0 * cm


def styles():
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=29,
            textColor=GREEN,
            alignment=TA_CENTER,
            spaceAfter=10,
        ),
        "Sub": ParagraphStyle(
            "Sub",
            parent=base["Normal"],
            fontSize=11,
            leading=15,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "H1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=GREEN,
            spaceBefore=10,
            spaceAfter=7,
        ),
        "H2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#2D6A4F"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "H3": ParagraphStyle(
            "H3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11.2,
            leading=14,
            textColor=ORANGE,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=13.2,
            textColor=DARK,
            spaceAfter=5.2,
        ),
        "Small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=MUTED,
        ),
        "Caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=7.4,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
            spaceAfter=8,
        ),
        "Callout": ParagraphStyle(
            "Callout",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12.5,
            textColor=GREEN,
            backColor=PALE_GREEN,
            borderColor=LIGHT_GREEN,
            borderPadding=7,
            spaceBefore=5,
            spaceAfter=8,
        ),
        "Warn": ParagraphStyle(
            "Warn",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12.5,
            textColor=RED,
            backColor=colors.HexColor("#FFF3E0"),
            borderColor=GOLD,
            borderPadding=7,
            spaceBefore=5,
            spaceAfter=8,
        ),
    }


S = styles()


def p(text, style="Body"):
    text = text.replace("₹", "Rs. ")
    return Paragraph(text, S[style])


def bullets(items):
    return ListFlowable(
        [ListItem(p(i), leftIndent=10) for i in items],
        bulletType="bullet",
        start="circle",
        leftIndent=18,
        bulletFontSize=6,
        spaceAfter=5,
    )


def table(data, widths=None, header=True, font=7.8):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCD5AE")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBF8")]),
    ]
    if header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font),
            ]
        )
    t.setStyle(TableStyle(style))
    return t


def image_block(photo_key: str, paths: dict[str, Path], width=7.5 * cm):
    photo = next(x for x in PHOTOS if x.key == photo_key)
    img_path = paths.get(photo_key)
    if not img_path or not img_path.exists():
        return p(f"[Image unavailable: {photo.title}]", "Warn")
    try:
        im = Image.open(img_path)
        iw, ih = im.size
        ratio = ih / iw
        h = min(width * ratio, 8.7 * cm)
        return Table(
            [[RLImage(str(img_path), width=width, height=h)], [p(f"{photo.title}. Photo: {photo.credit}, {photo.license}.", "Caption")]],
            colWidths=[width],
            style=TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            ),
        )
    except Exception:
        return p(f"[Image could not be rendered: {photo.title}]", "Warn")


def two_col_image_text(photo_key: str, paths: dict[str, Path], title: str, body: list[str]):
    left = image_block(photo_key, paths, width=7.2 * cm)
    right = [p(f"<b>{title}</b>", "H3")] + [p(x) for x in body]
    t = Table([[left, right]], colWidths=[7.6 * cm, 8.9 * cm])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def section_intro(title: str, subtitle: str):
    return [PageBreak(), p(title, "H1"), p(subtitle, "Callout")]


def recipe_section(name, purpose, ingredients, equipment, steps, timeline, use_table, storage, problems):
    story = []
    story += [p(name, "H1"), p(purpose, "Callout")]
    story += [p("Ingredients", "H2"), table([["Input", "Beginner quantity", "Why it is used"]] + ingredients, [4.1 * cm, 4.2 * cm, 8.2 * cm])]
    story += [p("Equipment", "H2"), bullets(equipment)]
    story += [p("Step-by-step preparation", "H2")]
    for idx, step in enumerate(steps, 1):
        story.append(p(f"<b>Step {idx}.</b> {step}"))
    story += [p("Fermentation / processing timeline", "H2"), table([["Day", "What you should see", "What you should do"]] + timeline, [2.2 * cm, 7.0 * cm, 7.3 * cm])]
    story += [p("How to use safely", "H2"), table([["Crop situation", "Dilution", "Frequency", "Best time"]] + use_table, [4.2 * cm, 3.0 * cm, 4.1 * cm, 5.2 * cm])]
    story += [p("Storage method and shelf life", "H2"), table([["Storage point", "Correct practice"]] + storage, [5.2 * cm, 11.3 * cm])]
    story += [p("Common problems and fixes", "H2"), table([["Symptom", "Reason", "Fix"]] + problems, [4.3 * cm, 5.5 * cm, 6.7 * cm])]
    return story


def build_story(paths: dict[str, Path]):
    story = []
    story.append(Spacer(1, 1.0 * cm))
    story.append(p("Satheesh Organic Fertilizer Master Manual", "Title"))
    story.append(p("Seasonal Waste to Year-Round Fertility: Mango FPJ, Jackfruit Compost, Bokashi, Biochar, Jeevamrutham and Terrace-Safe Storage", "Sub"))
    story.append(p("Prepared for Satheesh, Sanganapalle, Chittoor District, Andhra Pradesh", "Sub"))
    story.append(DiagramBox("The circular farm idea", "storage", height=7.0 * cm))
    story.append(p("This PDF is a practical beginner-to-advanced manual. It is written for a farmer starting from zero knowledge, with Chittoor heat, terrace leakage risk, seasonal mango/jackfruit waste, organic-only philosophy, and a future smart terrace farm in mind.", "Callout"))
    story.append(p("Important note about images: this edition uses openly licensed real photographs from Wikimedia Commons for ingredient and process reference. Engineering layouts are locally drawn diagrams. Your actual terrace photo was not available as a local file in this workspace, so it is not embedded in this build.", "Warn"))
    story.append(PageBreak())

    story.append(p("How to Use This Manual", "H1"))
    story.append(p("Do not try every fertilizer on every plant in the first week. Build a fertilizer bank: fresh inputs for weekly microbial activity, fermented concentrates for seasonal storage, compost for slow nutrition, and biochar for long-term soil strength.", "Callout"))
    story.append(table([
        ["Season / source", "What to produce", "Main crop use", "Storage goal"],
        ["Mango season", "Raw mango FPJ / FFJ", "Flowering and fruiting crops", "6-12 months"],
        ["Jackfruit season", "Jackfruit compost base", "Grow bag recharge and microbial soil building", "6-24 months after curing"],
        ["Daily vegetable waste", "Bokashi and compost", "Continuous fertility loop", "Continuous"],
        ["Summer dry biomass", "Biochar", "Water holding and microbial housing", "Permanent once dry"],
        ["Cow dung availability", "Jeevamrutham", "Weekly microbial activation", "Best fresh: 3-7 days"],
    ], [3.2 * cm, 4.0 * cm, 6.0 * cm, 3.3 * cm]))
    story.append(p("Farmer lesson: When a crop fails, beginners ask what chemical to spray. Experienced natural farmers ask: Was the root zone alive? Was the water correct? Did heat stop flowering? Was the input fully fermented? The answer is usually in the process, not in the bottle.", "Callout"))

    story.append(PageBreak())
    story.append(p("Part 1 - Terrace Safety Comes Before Fertilizer", "H1"))
    story.append(p("Because your terrace already has leakage risk, every fertilizer operation must be designed like a rooftop engineering system. Wet compost drums, leachate, NFT water, and grow bag drainage must never sit directly on the slab.", "Warn"))
    story.append(DiagramBox("Professional terrace protection stack", "terrace_stack"))
    story.append(p("Minimum terrace-safe rules", "H2"))
    story.append(bullets([
        "Keep all compost bins, bokashi buckets, FPJ drums, reservoirs and grow bags on raised stands or pallets.",
        "Place a tray or secondary containment under every liquid fertilizer drum.",
        "Never allow leachate to run across tile joints; collect and dilute it.",
        "Keep one dedicated washing area with a drain filter so solids do not block the terrace outlet.",
        "Do not store more wet biomass than the terrace can safely carry. Several small bins are safer than one heavy drum.",
        "During monsoon, cover compost and fermentation drums so rainwater does not dilute or spoil them.",
    ]))
    story.append(p("Practical weight thinking", "H2"))
    story.append(table([
        ["Item", "Approx wet weight", "Terrace rule"],
        ["20L FPJ drum", "20-25 kg", "Keep on stand with tray"],
        ["60L compost drum", "45-70 kg", "Keep near wall/beam zone, not center of slab"],
        ["500L water tank", "500+ kg", "Needs proper stand and structural placement"],
        ["Grow bag 15x15 inch", "12-20 kg wet", "Spread across shelves, never cluster all in one slab spot"],
    ], [4.5 * cm, 4.0 * cm, 8.0 * cm]))

    story.append(PageBreak())
    story.append(p("Part 2 - Real Ingredient Identification", "H1"))
    story.append(two_col_image_text("raw_mango", paths, "Raw mango: seasonal potassium and enzyme source", [
        "Use fallen, cracked, unsold or low-price raw mangoes. Avoid fruits with black rot, pesticide smell, or chemical wash.",
        "For your area where raw mango can fall to Rs. 2/kg or remain unsold, this becomes one of the cheapest fruiting-stage inputs."
    ]))
    story.append(two_col_image_text("jackfruit", paths, "Jackfruit waste: heavy wet biomass for compost", [
        "Jackfruit pulp, rind and fibrous waste are not ideal as direct soil input because they rot, smell and attract insects.",
        "They become excellent compost when mixed with dry leaves/cocopeat and cow dung slurry."
    ]))
    story.append(two_col_image_text("kitchen_scraps", paths, "Vegetable waste: daily nutrient loop", [
        "Vegetable peels, spoiled greens, stems and fruit skins should be chopped small and processed through bokashi or aerobic compost.",
        "Do not place raw kitchen waste directly into grow bags. It heats, rots and damages roots."
    ]))
    story.append(two_col_image_text("cow_dung", paths, "Cow dung: microbial engine, not just manure", [
        "Fresh cow dung is powerful but must be handled safely. Use it mainly in Jeevamrutham, compost activation or aged manure systems.",
        "For leafy vegetables eaten raw, avoid fresh manure near harvest; use matured compost and safe waiting periods."
    ]))

    story.append(PageBreak())
    story += recipe_section(
        "Part 3 - Raw Mango FPJ / FFJ Master Recipe",
        "Goal: Convert cheap seasonal raw mango into a stored liquid concentrate for flowering, fruit setting, fruit strength, microbial stimulation and stress recovery.",
        [
            ["Raw mango pieces", "5 kg", "Potassium, organic acids, enzymes and plant sugars"],
            ["Jaggery or brown sugar", "5 kg for long storage, or 2.5 kg for short use", "Draws juice by osmosis and stabilizes fermentation"],
            ["Old FPJ or Jeevamrutham", "100-200 ml optional", "Starter microbes; optional if fruit skin is healthy"],
            ["Clean dry cloth", "1 piece", "Breathable cover during active fermentation"],
            ["Food-grade bucket/drum", "15-20L", "Fermentation container; keep 30% headspace"],
        ],
        [
            "Food-grade plastic bucket, clay pot or glass jar; avoid rusted metal.",
            "Wooden spatula or clean plastic ladle.",
            "Cotton cloth, rubber band, label, marker and storage bottles.",
            "Fine cloth filter for final straining.",
        ],
        [
            "Select raw mangoes. Remove mud, plastic and black-rotted fruit. Lightly wash if dusty, then dry the surface for 20-30 minutes.",
            "Chop into 1-2 inch pieces. Smaller pieces release juice faster, but do not grind into paste; paste spoils faster.",
            "Weigh mango and jaggery. For one-year storage use 1:1 by weight. If jaggery is costly and you will use within 2-3 months, 2:1 mango:jaggery can work but is less stable.",
            "Put one layer mango, one layer jaggery. Press gently. Repeat until the container is 70% full.",
            "Add starter only if available. Do not add water. Water reduces storage stability.",
            "Cover with cloth for the first 5-7 days. Keep in shade, never in sun.",
            "Stir once daily with a clean dry stick for the first 3 days. After bubbling reduces, stop disturbing.",
            "After 7-15 days, filter through cloth. Squeeze gently. Do not force rotten solids through the filter.",
            "Bottle the liquid in dark bottles. Keep 10-15% headspace. Open once after 2 days to release gas if pressure builds.",
            "Put the leftover solids into compost, never into NFT pipes.",
        ],
        [
            ["Day 1", "Mango and jaggery layers visible; syrup starts forming", "Keep covered with cloth"],
            ["Day 2-3", "Sweet-sour smell, bubbling, liquid increases", "Stir once daily with clean stick"],
            ["Day 4-7", "Fruit softens; smell should be fermented, not rotten", "Stop frequent stirring; check insects"],
            ["Day 7-15", "Liquid extraction peaks; solids collapse", "Filter and bottle"],
            ["Month 1+", "Stable brown liquid; mild alcohol/sour fruit smell", "Store cool and dark; use diluted"],
        ],
        [
            ["Tomato/chilli/brinjal fruiting", "1:100 soil drench", "Every 10-15 days", "Morning before heat"],
            ["Leaf spray for stress recovery", "1:500", "Every 15 days", "Evening only"],
            ["NFT leafy crops", "Avoid direct use unless laboratory filtered", "Only experimental", "Never if cloudy or smelly"],
            ["Seedlings", "1:1000", "Once after establishment", "Early morning"],
        ],
        [
            ["Container", "Dark glass/plastic bottle or HDPE can. Avoid metal."],
            ["Shelf life", "6-12 months when made with 1:1 jaggery, no water, filtered and stored cool."],
            ["Good smell", "Sweet-sour, fruity, mild alcohol."],
            ["Bad smell", "Rotten egg, sewage, strong ammonia. Discard into compost after dilution; do not spray."],
            ["Seasonal plan", "Make enough during mango glut. Use mainly from flowering to harvest season."],
        ],
        [
            ["Fruit flies", "Cover loose or fruit exposed", "Use double cloth cover; keep rim clean; move to shaded protected area"],
            ["Black mold", "Too much air/contamination", "Remove top layer if small; discard if smell is rotten"],
            ["No liquid", "Too little jaggery or fruit too dry", "Add more jaggery; do not add water"],
            ["Bottle swelling", "Fermentation still active", "Open carefully to release gas; keep cool"],
        ],
    )
    story.insert(len(story)-27, DiagramBox("Mango FPJ process flow", "fpj_flow", height=5.8 * cm))
    story.append(PageBreak())
    story.append(p("Real Mango FPJ Operating Notes", "H1"))
    story.append(image_block("raw_mango", paths, width=10.5 * cm))
    story.append(p("The most important difference between a good FPJ and a bad rotten fruit liquid is water control. FPJ is preserved by sugar extraction and fermentation. If you add water early, you make a weak liquid that spoils faster.", "Callout"))
    story.append(p("For Satheesh's terrace, the safest way is to keep FPJ as a concentrated input for grow bags only. For NFT, raw organic liquids can clog pipes and create biofilm. If you experiment with NFT, use only a few millilitres, filter through cloth plus coffee filter, and monitor root smell daily.", "Warn"))

    story.append(PageBreak())
    story += recipe_section(
        "Part 4 - Jackfruit Waste Compost Master Process",
        "Goal: Convert wet jackfruit waste into stable compost without smell, flies or terrace leakage.",
        [
            ["Jackfruit waste", "10 kg", "Wet sugar-rich biomass and potassium"],
            ["Dry leaves / cocopeat / straw", "15 kg", "Carbon, odor control and moisture balance"],
            ["Cow dung slurry", "2 kg dung in 10L water", "Microbial activation"],
            ["Wood ash", "250-500 g only", "Potassium and odor control; too much raises pH"],
            ["Old compost / forest soil", "2-3 handfuls", "Microbial diversity"],
        ],
        [
            "Two or three 60L drums with side holes, or one raised compost bin.",
            "Drain tray under bin; never leak liquid directly onto terrace.",
            "Chopping tool, gloves, compost fork/stick and breathable cover.",
            "Optional compost thermometer for serious management.",
        ],
        [
            "Chop jackfruit waste into small pieces. The fibrous core decomposes slowly; smaller pieces are better.",
            "Make a dry base layer 4-6 inches thick using sticks, dry leaves or cocopeat.",
            "Add a thin wet layer of jackfruit waste, not more than 3 inches thick.",
            "Sprinkle dry leaves/cocopeat over the wet layer until it is fully covered.",
            "Add cow dung slurry lightly. The pile should feel like a squeezed cloth, not dripping.",
            "Dust a very small amount of wood ash. Do not make the whole pile grey with ash.",
            "Repeat layers. Finish with dry leaves on top to block flies.",
            "Turn after 5 days, then every 5-7 days for the first month.",
            "If smell comes, add dry carbon immediately and turn for air.",
            "Cure for 45-90 days before using in grow bags.",
        ],
        [
            ["Day 1", "Layered pile, mild fruit smell", "Cover with dry carbon"],
            ["Day 3-5", "Heat starts, pile may shrink", "Check moisture and turn once"],
            ["Day 10-20", "Fruit pieces break down, smell should become earthy", "Turn every 5-7 days"],
            ["Day 30-45", "Compost darkening, fibers still visible", "Stop adding fresh waste; begin curing"],
            ["Day 60-90", "Cool, dark, crumbly, earthy smell", "Sieve and store"],
        ],
        [
            ["Grow bag recharge", "1 part compost : 4 parts old mix", "Between crop cycles", "Morning mixing"],
            ["Tomato/chilli top dress", "1-2 handfuls per bag", "Monthly", "Before watering"],
            ["Seedling mix", "Use only mature sieved compost", "At nursery setup", "Avoid fresh compost"],
            ["NFT", "Do not add solids", "Not suitable", "Use only filtered liquid experiments"],
        ],
        [
            ["Storage", "Dry shade, breathable sacks or covered bin."],
            ["Shelf life", "1-2 years if kept dry, cool and protected from rain."],
            ["Moisture", "Finished compost should be slightly moist, not wet."],
            ["Terrace safety", "Store on pallet, not directly on slab."],
        ],
        [
            ["Bad smell", "Too wet, no air", "Add dry leaves/cocopeat; turn immediately"],
            ["Maggots", "Exposed fruit waste", "Cover with dry layer; close bin; increase carbon"],
            ["No heating", "Too dry or too much carbon", "Add cow dung slurry and turn"],
            ["White fungus", "Usually normal fungal decomposition", "Safe if smell is earthy"],
        ],
    )
    story.insert(len(story)-27, DiagramBox("Jackfruit compost layering", "compost_layer", height=6.8 * cm))
    story.append(PageBreak())
    story.append(image_block("jackfruit", paths, width=9.8 * cm))
    story.append(p("Real farmer warning: jackfruit waste is very wet and sugary. If you put it directly into a bin without enough dry leaves, it becomes sticky, hot, sour and insect-attracting. The fix is not medicine; the fix is carbon and air.", "Callout"))

    story.append(PageBreak())
    story += recipe_section(
        "Part 5 - Vegetable Waste Bokashi for Terrace Farming",
        "Goal: Process daily kitchen and vegetable waste in a sealed low-smell system suitable for terraces and apartment-style spaces.",
        [
            ["Vegetable/fruit waste", "1-2 kg per batch", "Daily nutrient source"],
            ["Bokashi bran", "1 handful per layer", "Lactic acid bacteria and yeasts"],
            ["Dry leaf powder / cocopeat", "As needed", "Controls moisture"],
            ["Jaggery water", "Only if bran is weak", "Microbial food"],
            ["Airtight bucket with tap", "15-25L", "Anaerobic fermentation"],
        ],
        [
            "Airtight bucket or DIY double-bucket system with leachate drain.",
            "Plate/press to compact waste.",
            "Bokashi bran container and small scoop.",
            "Drain bottle for bokashi liquid.",
        ],
        [
            "Chop waste small. Large pieces ferment slowly and create air pockets.",
            "Add a 2-3 inch layer of waste.",
            "Sprinkle bokashi bran evenly. More bran is needed for wet or cooked waste.",
            "Press down firmly to remove air. This is critical.",
            "Close lid immediately. Open only when adding new waste.",
            "Drain liquid every 2-3 days. Dilute before use.",
            "When full, seal for 14 days. Do not keep opening.",
            "After fermentation, bury in soil, add to compost, or mix into a curing tub with old compost.",
            "Wait another 2-4 weeks before using near tender roots.",
        ],
        [
            ["Day 1-7", "Pickle/sour smell; waste still visible", "Keep sealed; drain liquid"],
            ["Day 7-14", "White bloom may appear; volume compresses", "Continue draining"],
            ["Day 14-21", "Fermented pre-compost ready", "Move to soil/compost curing"],
            ["After curing", "Material softens and smell becomes earthy", "Use in compost or grow bag recharge"],
        ],
        [
            ["Bokashi liquid", "1:100", "Within 24-48 hours of draining", "Morning soil drench only"],
            ["Pre-compost", "Mix into compost/soil, not direct root contact", "After 2-4 week curing", "Between crop cycles"],
            ["Leafy greens", "Avoid direct use close to harvest", "Use matured compost only", "Food safety first"],
            ["Fruit crops", "Small amounts after curing", "Monthly", "Before watering"],
        ],
        [
            ["Bucket stage", "14-21 days sealed fermentation."],
            ["Liquid", "Use quickly; do not store for months."],
            ["Pre-compost", "Cure with soil/compost 2-4 weeks before root contact."],
            ["Smell test", "Good: pickle/sour. Bad: sewage/rotten flesh."],
        ],
        [
            ["Foul smell", "Too wet or air entered", "Add more bran/dry carbon; press harder; drain liquid"],
            ["Green/black mold", "Air contamination", "Discard bad layer into hot compost; improve sealing"],
            ["No liquid", "Waste too dry", "Not a problem; continue fermentation"],
            ["Plants burn after use", "Pre-compost too acidic/fresh", "Cure longer before applying"],
        ],
    )
    story.insert(len(story)-27, DiagramBox("Bokashi bucket cross-section", "bokashi_bucket", height=7.4 * cm))
    story.append(PageBreak())
    story.append(two_col_image_text("bokashi_bucket", paths, "Real bokashi bucket reference", [
        "A bucket with a tight lid and drain is ideal. The system works because oxygen is limited.",
        "For terrace use, keep it under shade and place it in a tray so leachate never reaches the floor."
    ]))
    story.append(two_col_image_text("bokashi_content", paths, "Inside bokashi content", [
        "Food remains visible during fermentation. Bokashi is not finished compost yet.",
        "After the sealed stage, it must be buried or cured in compost/soil."
    ]))
    story.append(two_col_image_text("bokashi_white", paths, "White bloom is usually good", [
        "A white fungal bloom can be normal in bokashi. It indicates fermentation, not failure.",
        "Green/black mold with foul smell is different and indicates oxygen contamination."
    ]))

    story.append(PageBreak())
    story += recipe_section(
        "Part 6 - Jeevamrutham Beginner-to-Farmer Method",
        "Goal: Prepare a weekly living microbial input that activates soil biology and supports organic nutrient cycling.",
        [
            ["Water", "10L", "Medium for microbial multiplication"],
            ["Fresh desi cow dung", "1 kg", "Microbial source and nutrients"],
            ["Cow urine", "1L optional", "Nitrogen and microbial stimulation"],
            ["Jaggery", "200 g", "Microbial energy"],
            ["Pulse flour / besan", "200 g", "Protein/nitrogen for microbes"],
            ["Forest soil / bund soil", "1 handful", "Local microbial diversity"],
        ],
        [
            "Plastic or clay drum; do not use pesticide-contaminated container.",
            "Wooden stirring stick.",
            "Cloth cover; do not seal airtight.",
            "Filter cloth if using in drip or NFT experiments.",
        ],
        [
            "Fill drum with water. If using chlorinated tap water, keep it open overnight first.",
            "Mix cow dung thoroughly in a separate bucket so lumps break down.",
            "Add dung slurry, jaggery, pulse flour, cow urine and soil to the drum.",
            "Stir clockwise and anticlockwise for 5-10 minutes.",
            "Cover with cloth and keep in shade.",
            "Stir morning and evening for 2-3 days.",
            "Use fresh. Do not treat it like a long-storage fertilizer.",
            "For grow bags, apply around the edge of the bag, not directly on the stem.",
            "For NFT, only use heavily diluted and very well filtered liquid; watch for biofilm.",
        ],
        [
            ["Day 1", "Dung smell but not rotten", "Stir well"],
            ["Day 2", "Mild fermentation, bubbles may appear", "Stir twice"],
            ["Day 3", "Ready for soil drench", "Use or refresh"],
            ["Day 5-7", "Microbial strength declines slowly", "Use remaining in compost"],
        ],
        [
            ["Grow bags", "1:5 to 1:10", "Weekly", "Morning after light watering"],
            ["Seedlings", "1:20", "Once every 10-15 days", "Early morning"],
            ["Compost activation", "Undiluted or 1:2", "When layering compost", "Any cool time"],
            ["Foliar spray", "1:20 and filtered", "Every 15 days", "Evening"],
        ],
        [
            ["Best use", "Fresh within 3 days."],
            ["Maximum practical storage", "3-7 days in shade with stirring."],
            ["Do not seal", "Gas buildup and anaerobic smell can develop."],
            ["Old batch", "Pour into compost; do not spray on leaves."],
        ],
        [
            ["Strong bad smell", "Anaerobic rot", "Add to compost; make fresh batch"],
            ["Maggots", "Poor cover", "Use tighter cloth; keep rim clean"],
            ["Leaf burn", "Too strong", "Dilute more; spray only evening"],
            ["Clogged drip", "Not filtered", "Filter through cloth; flush lines"],
        ],
    )
    story.append(PageBreak())
    story.append(image_block("cow_dung", paths, width=11.5 * cm))
    story.append(p("Food safety note: fresh manure can carry pathogens. For crops eaten raw, use mature compost and avoid fresh manure contact near harvest. Composting and time reduce risk, but good hygiene is non-negotiable.", "Warn"))

    story.append(PageBreak())
    story += recipe_section(
        "Part 7 - Biochar: Permanent Soil Battery",
        "Goal: Convert dry biomass into a long-term carbon material that holds water, nutrients and microbes in grow bags.",
        [
            ["Dry wood / coconut shell / dry sticks", "As available", "Carbon feedstock"],
            ["Water", "Enough to quench", "Stops burning before ash"],
            ["Jeevamrutham or compost tea", "Enough to soak", "Charges biochar with nutrients and microbes"],
            ["Old compost", "Optional", "Adds biology during charging"],
            ["Crushing tool", "1", "Makes root-zone sized particles"],
        ],
        [
            "Safe outdoor pit or metal drum kiln; do not make smoke near neighbors.",
            "Water hose/bucket for emergency.",
            "Metal rod, gloves, mask and eye protection.",
            "Covered bucket for charging biochar.",
        ],
        [
            "Use only clean dry biomass. Never use painted wood, plastic, rubber, pesticide containers or treated boards.",
            "Start a controlled burn. The goal is low-oxygen charring, not full ash production.",
            "When material becomes black charcoal but before it turns white/grey ash, quench completely with water.",
            "Dry partially, then crush to rice-grain to peanut size.",
            "Charge before use: soak in Jeevamrutham, compost tea or cow dung slurry for 7 days.",
            "Mix charged biochar into grow bag medium at 5-10% by volume.",
            "For existing bags, top dress only a handful and water with Jeevamrutham.",
        ],
        [
            ["Burn day", "Black char forms", "Quench before ash"],
            ["Day 1-7", "Biochar soaking in microbial liquid", "Stir daily if possible"],
            ["After day 7", "Charged biochar smells earthy", "Mix into soil/grow bags"],
            ["Long term", "Biochar remains for years", "Recharge with compost/Jeevamrutham seasonally"],
        ],
        [
            ["New grow bag mix", "5-10% of volume", "Once during mixing", "Before planting"],
            ["Old grow bag recharge", "1-2 handfuls per bag", "Between crops", "With compost"],
            ["Seedlings", "Very fine and mature only, 2-3%", "At nursery mix", "Avoid excess"],
            ["NFT", "Not for channels", "No direct use", "Can be in external biofilter only"],
        ],
        [
            ["Shelf life", "Permanent if dry."],
            ["Storage", "Dry sack or drum; protected from rain."],
            ["Must charge?", "Yes. Raw biochar can temporarily pull nutrients away from plants."],
            ["Best use", "Grow bag soil structure, water retention and microbial housing."],
        ],
        [
            ["Plants yellow after biochar", "Used raw/un-charged", "Apply Jeevamrutham and compost; charge next batch"],
            ["Too much ash", "Burned too long", "Use ash separately in tiny amounts; make fresh biochar"],
            ["Smoke complaints", "Poor burning method", "Use small batch, dry feedstock, safer kiln"],
            ["Dust irritation", "Crushing dry char", "Wet lightly and wear mask"],
        ],
    )
    story.insert(len(story)-27, DiagramBox("Biochar pit method", "biochar_pit", height=6.8 * cm))
    story.append(PageBreak())
    story.append(image_block("biochar", paths, width=11.5 * cm))

    story.append(PageBreak())
    story.append(p("Part 8 - Ordinary Aerobic Compost from Vegetable Waste", "H1"))
    story.append(image_block("compost_pile", paths, width=11.5 * cm))
    story.append(p("Aerobic compost is the backbone of your grow bag fertility. Bokashi is good for sealed terrace waste processing, FPJ is good as liquid concentrate, but mature compost is what rebuilds soil body.", "Callout"))
    story.append(p("The 60:40 rule", "H2"))
    story.append(p("For terrace composting, use about 60% brown carbon and 40% green wet waste by volume. Brown material includes dry leaves, cocopeat, cardboard pieces, straw and sawdust. Green material includes vegetable waste, fruit waste, fresh leaves and cow dung. This ratio prevents smell and speeds decomposition."))
    story.append(table([
        ["Material", "Type", "How to use"],
        ["Dry leaves", "Brown", "Main odor-control and carbon material"],
        ["Cocopeat", "Brown/neutral", "Moisture buffer for wet jackfruit/mango residues"],
        ["Vegetable peels", "Green", "Chop small; cover with dry layer"],
        ["Fruit waste", "Green wet", "Use in thin layers only"],
        ["Cow dung slurry", "Green/microbial", "Sprinkle lightly to activate"],
        ["Wood ash", "Mineral", "Tiny amount only; excess raises pH"],
    ], [4.2 * cm, 3.5 * cm, 8.8 * cm]))
    story.append(p("Turn schedule", "H2"))
    story.append(table([
        ["Age of pile", "Action", "Reason"],
        ["Day 3-5", "First turn", "Prevent anaerobic pockets"],
        ["Day 10", "Second turn", "Mix hot and cold zones"],
        ["Day 15-30", "Turn weekly", "Maintain oxygen and even decomposition"],
        ["Day 30-60", "Cure undisturbed if stable", "Let microbes finish humus formation"],
    ], [3.4 * cm, 5.0 * cm, 8.1 * cm]))

    story.append(PageBreak())
    story.append(p("Part 9 - Fertilizer Storage Bank", "H1"))
    story.append(DiagramBox("Storage life ladder", "storage", height=7.0 * cm))
    story.append(table([
        ["Input", "Expected storage", "Container", "Good sign", "Bad sign"],
        ["Mango FPJ/FFJ", "6-12 months", "Dark airtight bottle", "Sweet-sour fruit smell", "Rotten egg, black mold"],
        ["Jeevamrutham", "3-7 days", "Open shaded drum", "Mild dung ferment", "Sewage smell"],
        ["Bokashi liquid", "Use within 1-2 days", "Small bottle", "Sour pickle smell", "Foul/ammonia smell"],
        ["Bokashi pre-compost", "2-4 weeks curing", "Sealed then soil/compost", "Pickled smell", "Black mold + rot"],
        ["Mature compost", "1-2 years", "Breathable sack/bin", "Earth smell", "Wet sour smell"],
        ["Biochar", "Years", "Dry sack/drum", "Dry black char", "Contaminated with chemicals"],
        ["Wood ash", "1-3 years", "Dry sealed bin", "Dry grey powder", "Wet hard lumps"],
    ], [3.3 * cm, 3.0 * cm, 3.5 * cm, 3.4 * cm, 3.3 * cm], font=7.1))
    story.append(p("Storage rules that prevent 90% of failures", "H2"))
    story.append(bullets([
        "Label every batch: date, ingredient, ratio, expected use.",
        "Keep liquid concentrates cool and dark.",
        "Keep dry powders completely dry.",
        "Never mix all fertilizers into one drum. Separate storage prevents total loss.",
        "Use smell as a diagnostic tool: sweet-sour/earthy is usually good; sewage/rotten egg is failure.",
        "For terrace safety, every liquid container needs secondary containment.",
    ]))

    story.append(PageBreak())
    story.append(p("Part 10 - Crop Application Schedule for Satheesh's Terrace", "H1"))
    story.append(table([
        ["Crop group", "Base nutrition", "Weekly input", "Fruiting input", "Warning"],
        ["Tomato", "Compost + biochar grow bag mix", "Jeevamrutham 500ml diluted", "Mango FPJ 1:100 every 10-15 days", "Too much nitrogen causes leaves, not fruit"],
        ["Chilli", "Compost + ash trace", "Jeevamrutham 300ml diluted", "Mango FPJ during flowering", "Avoid waterlogging"],
        ["Brinjal", "Rich compost", "Jeevamrutham weekly", "FPJ + neem pest watch", "Fruit borer needs early pruning"],
        ["Bhindi", "Moderate compost", "Light Jeevamrutham", "Little FPJ if flowering weak", "Do not overwater"],
        ["Cucumber", "Moist compost mix", "Jeevamrutham weekly", "FPJ after first flowers", "Needs moisture, but roots need air"],
        ["NFT leafy", "Filtered reservoir nutrients", "Very cautious organic filtration", "Not needed", "Biofilm/clogging risk"],
    ], [2.6 * cm, 3.6 * cm, 3.4 * cm, 4.2 * cm, 3.0 * cm], font=6.7))
    story.append(p("Beginner rule: one change at a time", "Warn"))
    story.append(p("If a plant is weak, do not apply FPJ, Jeevamrutham, neem, ash and compost tea all on the same day. You will not know what helped or harmed it. Apply one input, observe for 48 hours, then decide."))

    story.append(PageBreak())
    story.append(p("Part 11 - Emergency Troubleshooting Like an Experienced Farmer", "H1"))
    story.append(table([
        ["Problem seen", "Most likely cause", "First response", "Do not do"],
        ["Plant wilts though soil is wet", "Root rot / no oxygen", "Stop watering, improve drainage, smell roots", "Do not add more liquid fertilizer"],
        ["Yellow lower leaves", "Nitrogen shortage or old leaves", "Light Jeevamrutham, compost top dress", "Do not overdose FPJ"],
        ["Leaf edges brown", "Salt/potassium/water stress", "Flush with clean water, check EC/TDS if possible", "Do not add ash immediately"],
        ["White powder on leaves", "Powdery mildew", "Remove worst leaves, spray diluted buttermilk/neem in evening", "Do not spray in hot sun"],
        ["Fruit drop in summer", "Heat stress above 38-40C", "Shade net, morning water, mulch, reduce stress", "Do not assume fertilizer alone fixes heat"],
        ["Compost smells rotten", "Too wet/anaerobic", "Add dry leaves/cocopeat and turn", "Do not seal wet aerobic compost"],
        ["FPJ smells sewage-like", "Rot contamination", "Discard into compost after dilution", "Do not spray crops"],
        ["Bokashi has green mold", "Air entered", "Remove bad layer, add bran, seal better", "Do not use directly near roots"],
    ], [3.4 * cm, 4.0 * cm, 5.0 * cm, 4.1 * cm], font=6.8))

    story.append(PageBreak())
    story.append(p("Part 12 - 30-Day Startup Plan from Zero Knowledge", "H1"))
    story.append(table([
        ["Day", "Task", "Output"],
        ["1", "Clean terrace fertilizer corner; place pallet, tray and shade", "Safe work zone"],
        ["2", "Buy/arrange two buckets, one drum, labels, gloves, cloth", "Basic input lab"],
        ["3", "Start small mango FPJ batch with 1kg mango + 1kg jaggery", "First fermentation"],
        ["4", "Start dry leaf collection and storage sack", "Carbon bank"],
        ["5", "Start bokashi bucket with daily vegetable waste", "Kitchen waste loop"],
        ["7", "Prepare first Jeevamrutham batch", "Weekly microbial input"],
        ["10", "Build compost drum layers using dry leaves + waste", "Compost production"],
        ["15", "Filter mango FPJ if ready; bottle and label", "Stored fruiting input"],
        ["20", "Move bokashi pre-compost to curing tub", "Safe soil-ready material"],
        ["30", "Review smell, insects, leakage, plant response; correct process", "Stable routine"],
    ], [1.8 * cm, 10.2 * cm, 4.5 * cm]))
    story.append(p("Your first goal is not maximum fertilizer quantity. Your first goal is clean smell, no flies, no leakage, correct labels, and plants that respond gently. Quantity comes after process discipline.", "Callout"))

    story.append(PageBreak())
    story.append(p("Part 13 - Extra Natural Inputs You Should Learn After the First Month", "H1"))
    story.append(p("Do not start with ten inputs on day one. Learn FPJ, compost, bokashi, biochar and Jeevamrutham first. After the smell, storage and plant response are stable, add the following simple inputs one by one.", "Callout"))
    story.append(p("Banana Peel Potassium Ferment", "H2"))
    story.append(table([
        ["Item", "Quantity", "Reason"],
        ["Banana peels", "1 kg chopped", "Potassium for flowering and fruiting"],
        ["Jaggery", "500 g to 1 kg", "Fermentation and extraction"],
        ["Water", "Only enough after fermentation for dilution", "Do not add during extraction if storing long"],
    ], [4.2 * cm, 4.0 * cm, 8.3 * cm]))
    story.append(bullets([
        "Chop peels into small pieces and layer with jaggery in a clean jar.",
        "Cover with cloth for 5-7 days, then filter.",
        "Use 1:100 as soil drench for tomato, chilli, brinjal and cucumber during flowering.",
        "Do not spray strong banana ferment on leaves in hot sun.",
        "Shelf life is 3-6 months if made without water and stored cool/dark.",
    ]))
    story.append(p("Eggshell Calcium Vinegar Extract", "H2"))
    story.append(table([
        ["Step", "Action", "Important note"],
        ["1", "Wash eggshells and dry fully", "Moist shells smell bad"],
        ["2", "Roast lightly until brittle", "Do not burn black"],
        ["3", "Crush into powder", "More surface area"],
        ["4", "Add vinegar slowly", "It will bubble; leave headspace"],
        ["5", "After bubbling stops, filter", "Store in bottle"],
        ["6", "Use 1:500 to 1:1000", "Too strong can burn"],
    ], [2.0 * cm, 7.0 * cm, 7.5 * cm]))
    story.append(p("Use this only when calcium deficiency symptoms appear, such as blossom end rot in tomato or capsicum. First correct irregular watering because calcium deficiency is often caused by moisture fluctuation, not absence of calcium.", "Warn"))
    story.append(p("Wood Ash Water", "H2"))
    story.append(bullets([
        "Use only clean wood ash, not plastic/painted wood ash.",
        "Mix 1 teaspoon ash in 1 litre water, stir, settle, and use the clear water.",
        "Use very carefully for acidic soil or potassium support.",
        "Do not overuse in Chittoor terrace bags; too much ash raises pH and locks nutrients.",
    ]))
    story.append(p("Compost Tea - Short Life Input", "H2"))
    story.append(table([
        ["Input", "Quantity"],
        ["Mature compost", "1 kg"],
        ["Water", "10L chlorine-free"],
        ["Jaggery", "1 tablespoon optional"],
        ["Aeration", "Best with aquarium pump for 12-24 hours"],
    ], [7.0 * cm, 9.5 * cm]))
    story.append(p("Compost tea is not a storage fertilizer. Use within 24 hours. If it smells bad, pour into compost instead of spraying. For a beginner, soil drench is safer than foliar spray.", "Warn"))

    story.append(PageBreak())
    story.append(p("Part 14 - How to Build a Terrace-Safe Fertilizer Corner", "H1"))
    story.append(p("This is the small 'fertilizer factory' for your terrace. It must be clean, shaded, raised, easy to wash, and protected from rain. If this corner is badly designed, the farm will smell, leak, attract flies and damage the building.", "Callout"))
    story.append(table([
        ["Area", "Recommended setup", "Why"],
        ["Floor protection", "Plastic pallet + HDPE tray", "Creates air gap and catches leaks"],
        ["Shade", "50% shade net or roof sheet", "Prevents overheating of microbes"],
        ["Liquid drums", "20L drums with secondary tray", "Stops FPJ/Jeevamrutham leaks reaching slab"],
        ["Compost drum", "Side holes + bottom tray", "Airflow without terrace leakage"],
        ["Bokashi bucket", "Airtight bucket on small stand", "Easy leachate draining"],
        ["Dry material storage", "Sacks of dry leaves/cocopeat kept dry", "Needed to fix smell quickly"],
        ["Washing zone", "Small tub, not open floor washing", "Avoids blocked terrace drain"],
    ], [3.2 * cm, 6.4 * cm, 6.9 * cm]))
    story.append(p("ASCII layout for a 4ft x 4ft terrace fertilizer corner", "H2"))
    story.append(p("<font name='Courier'>BACK WALL<br/>+----------------------------+<br/>| Dry leaves | Compost drum  |<br/>| sack       | on tray       |<br/>|------------+---------------|<br/>| FPJ drum   | Bokashi bucket|<br/>| on tray    | with tap      |<br/>+----------------------------+<br/>FRONT: keep walking space and drain access clear</font>"))
    story.append(p("Farmer fix learned from experience: always keep one sack of dry leaves or cocopeat beside the compost. When smell starts, the solution must be immediate. Searching for carbon after smell begins is too late.", "Callout"))

    story.append(PageBreak())
    story.append(p("Part 15 - Batch Size Calculator", "H1"))
    story.append(p("Start small. If the small batch succeeds twice, move to medium. If the medium batch succeeds for one season without smell or leakage, move to large. This is how experienced farmers avoid wasting seasonal material.", "Callout"))
    story.append(table([
        ["Input", "Small beginner batch", "Medium terrace batch", "Large seasonal batch"],
        ["Mango FPJ", "1 kg mango + 1 kg jaggery", "5 kg mango + 5 kg jaggery", "20 kg mango + 20 kg jaggery"],
        ["Jackfruit compost", "2 kg waste + 3 kg dry leaves", "10 kg waste + 15 kg dry leaves", "50 kg waste + 75 kg dry leaves"],
        ["Bokashi", "5L bucket", "20L bucket", "2 x 20L buckets rotation"],
        ["Jeevamrutham", "5L", "10L", "20L only if used quickly"],
        ["Biochar", "2 kg charged", "10 kg charged", "50 kg charged for field scale"],
    ], [4.0 * cm, 4.2 * cm, 4.2 * cm, 4.1 * cm], font=7.0))
    story.append(p("How much to store for one terrace season?", "H2"))
    story.append(table([
        ["Material", "Reasonable storage target for 20x12 terrace"],
        ["Mango FPJ", "5-10 litres concentrate is enough for many months if diluted correctly"],
        ["Mature compost", "80-150 kg dry cured compost for grow bag recharge"],
        ["Biochar", "20-40 kg charged biochar for soil mixing over time"],
        ["Dry leaves/cocopeat", "Always keep 2-3 sacks as emergency carbon"],
        ["Jeevamrutham", "Do not store; prepare 10L weekly"],
    ], [5.0 * cm, 11.5 * cm]))

    story.append(PageBreak())
    story.append(p("Part 16 - Farmer Observation Sheets", "H1"))
    story.append(p("Writing notes is not school work. It is farming intelligence. Later, this becomes your AgriShield AI training data: input used, weather, plant response, disease signs and yield.", "Callout"))
    story.append(table([
        ["Date", "Batch/Input", "Smell", "Plant/crop used", "Dilution", "Result after 48 hours"],
        ["", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["", "", "", "", "", ""],
        ["", "", "", "", "", ""],
    ], [2.1 * cm, 3.5 * cm, 2.2 * cm, 3.2 * cm, 2.2 * cm, 3.3 * cm], font=7.2))
    story.append(Spacer(1, 0.4 * cm))
    story.append(table([
        ["Batch label", "Ingredients", "Start date", "Filter/turn date", "Good signs", "Problem signs"],
        ["Mango FPJ - Batch 1", "", "", "", "", ""],
        ["Compost - Drum 1", "", "", "", "", ""],
        ["Bokashi - Bucket 1", "", "", "", "", ""],
        ["Biochar charge - Batch 1", "", "", "", "", ""],
    ], [3.0 * cm, 3.2 * cm, 2.2 * cm, 2.7 * cm, 2.8 * cm, 2.6 * cm], font=6.9))

    story.append(PageBreak())
    story.append(p("Part 17 - Deep Troubleshooting: Smell, Color, Texture and Insects", "H1"))
    story.append(table([
        ["Observation", "Usually means", "Safe action"],
        ["Sweet-sour smell in FPJ", "Good fermentation", "Continue; filter at correct time"],
        ["Alcohol fruit smell", "Normal mature FPJ", "Store cool/dark"],
        ["Rotten egg smell", "Anaerobic failure", "Do not use on crops; dilute into compost"],
        ["White fungal threads in compost", "Good fungal decomposition if earthy smell", "Continue curing"],
        ["Green mold on bokashi", "Air contamination", "Remove bad layer; improve seal"],
        ["Maggots in compost", "Exposed wet waste", "Cover with dry leaves; turn; close bin"],
        ["Compost too hot and dry", "Microbes losing moisture", "Sprinkle water/Jeevamrutham lightly"],
        ["Compost cold after 10 days", "Too dry or too much carbon", "Add green material/cow dung slurry"],
        ["Sticky slimy compost", "Too wet and compacted", "Add dry carbon; make air holes"],
        ["FPJ has no liquid", "Too little sugar or dry fruit", "Add jaggery and wait"],
    ], [4.0 * cm, 5.8 * cm, 6.7 * cm], font=7.0))
    story.append(p("The old farmer rule", "H2"))
    story.append(p("Your nose tells you before your eyes. Good farming biology smells like soil, pickle, mild fruit ferment, forest floor or sweet-sour liquid. Bad biology smells like sewage, rotten egg, dead animal or ammonia. Once you learn smell, you will prevent many failures before they touch the plants.", "Callout"))

    story.append(PageBreak())
    story.append(p("Part 18 - Annual Seasonal Production Plan for Chittoor", "H1"))
    story.append(table([
        ["Month", "Main available material", "What to prepare", "Storage/use decision"],
        ["Jan", "Cool weather, dry leaves", "Compost curing, seedling mix", "Prepare for spring planting"],
        ["Feb", "Vegetable waste", "Bokashi + compost", "Build daily routine"],
        ["Mar", "Heat begins", "Biochar charging, mulch storage", "Prepare summer protection"],
        ["Apr", "Mango starts", "Small mango FPJ trials", "Test before large batch"],
        ["May", "Mango glut, high heat", "Large mango FPJ/FFJ", "Store 6-12 months"],
        ["Jun", "Monsoon starts", "Compost from fruit waste + leaves", "Watch moisture and smell"],
        ["Jul", "Wet biomass", "Jackfruit compost, bokashi", "Use extra dry carbon"],
        ["Aug", "Monsoon waste", "Compost curing", "Protect from rainwater"],
        ["Sep", "Post-monsoon growth", "Jeevamrutham weekly", "High crop response"],
        ["Oct", "Peak terrace season", "Use stored FPJ carefully", "Flowering/fruiting support"],
        ["Nov", "Cool season", "Compost tea trials", "Good for leafy crops"],
        ["Dec", "Dry leaves", "Biochar + compost storage", "Prepare next year's carbon bank"],
    ], [1.5 * cm, 4.0 * cm, 5.3 * cm, 5.7 * cm], font=6.7))

    story.append(PageBreak())
    story.append(p("Part 19 - Safety Rules for Family, Terrace and Food Crops", "H1"))
    story.append(p("Organic does not automatically mean safe. Natural inputs are powerful biological materials. Handle them cleanly, dilute them correctly, and keep them away from drinking water and children.", "Warn"))
    story.append(bullets([
        "Wear gloves when handling dung, compost and rotten plant material.",
        "Wash hands and tools after fertilizer work.",
        "Keep all buckets labeled. Never reuse fertilizer bottles for drinking water.",
        "Do not spray any fermented input on leafy greens close to harvest.",
        "Avoid fresh manure contact with edible leaves and roots.",
        "Keep children away from biochar burning, fermentation drums and compost leachate.",
        "Do not burn biochar on the terrace if smoke, fire safety, or neighbor complaints are possible. Make biochar in a safe open farm area instead.",
        "If a liquid smells dangerous, do not 'test' it on valuable plants. Put it into compost after heavy dilution.",
    ]))
    story.append(p("Terrace fire warning for biochar", "H2"))
    story.append(p("Biochar production should ideally be done on open ground, not on a building terrace. The terrace manual includes biochar because it is excellent for soil, but the burning process must be safe, legal and away from waterproof membranes, plastic pipes, shade nets and electrical wiring.", "Warn"))

    story.append(PageBreak())
    story.append(p("Part 20 - Detailed Daily, Weekly and Monthly SOP", "H1"))
    story.append(p("Daily - 10 minutes", "H2"))
    story.append(bullets([
        "Check if any fermentation container has leaked.",
        "Smell FPJ/bokashi area without opening all containers unnecessarily.",
        "Drain bokashi liquid if present; dilute immediately or store only until evening.",
        "Check compost moisture by hand: it should feel like a squeezed cloth.",
        "Look under grow bags and shelves for standing water.",
    ]))
    story.append(p("Weekly - 45 minutes", "H2"))
    story.append(bullets([
        "Prepare fresh Jeevamrutham.",
        "Turn active compost if it is in the first month.",
        "Clean terrace drain mesh.",
        "Check labels and batch dates.",
        "Apply diluted inputs to a small test group first if using a new batch.",
    ]))
    story.append(p("Monthly - 2 hours", "H2"))
    story.append(bullets([
        "Sieve mature compost and store in sacks.",
        "Recharge old grow bags with compost + charged biochar.",
        "Inspect terrace waterproofing, corners and parapet joints.",
        "Review which input improved plants and which created problems.",
        "Plan next seasonal batch based on available waste: mango, jackfruit, dry leaves or crop residues.",
    ]))

    story.append(PageBreak())
    story.append(p("Part 21 - Image Credits and Research Notes", "H1"))
    credit_rows = [["Image", "Credit", "License", "Source"]]
    for photo in PHOTOS:
        credit_rows.append([photo.title, photo.credit, photo.license, photo.url])
    story.append(table(credit_rows, [4.2 * cm, 4.0 * cm, 2.6 * cm, 5.7 * cm], font=5.8))
    story.append(p("Research notes", "H2"))
    story.append(bullets([
        "Fermented plant/fruit juice methods are based on Korean Natural Farming principles: plant/fruit material is extracted with sugar/jaggery and used only after dilution.",
        "Bokashi is an anaerobic fermentation process; pre-compost is acidic and must be buried or cured before normal plant use.",
        "Manure and dung-based inputs can contain pathogens; composting, curing and safe handling are important, especially for leafy crops eaten raw.",
        "Biochar should be charged with compost/Jeevamrutham before use so it does not temporarily tie up nutrients.",
        "Terrace systems need secondary containment and drainage because water damage can destroy the building before farming succeeds.",
    ]))
    story.append(p("This manual is practical guidance, not a laboratory certification document. For selling produce as certified organic, follow the relevant Indian organic certification and food safety requirements.", "Warn"))

    story.append(PageBreak())
    story.append(p("Final Farmer Advice", "H1"))
    story.append(p("A real farmer does not only grow crops. A real farmer manages water, heat, microbes, smell, roots, time, waste, insects, and market trust. Your strongest advantage is that you are learning to convert local low-value materials into a controlled fertility system.", "Callout"))
    story.append(p("Start small, observe daily, write labels, keep batches separate, and never let enthusiasm damage the terrace. Once the process becomes stable, you can scale the same system into the NFT/grow bag farm, then into the 1.5-acre field, and later into AgriShield AI as a documented natural farming operating system."))
    return story


def build_pdf():
    paths = download_photos()
    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=1.45 * cm,
        rightMargin=1.45 * cm,
        topMargin=1.45 * cm,
        bottomMargin=1.65 * cm,
        title="Satheesh Organic Fertilizer Master Manual",
        author="OpenAI Codex for Satheesh",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=on_page)])
    story = build_story(paths)
    doc.build(story)
    print(PDF_PATH)


if __name__ == "__main__":
    build_pdf()
