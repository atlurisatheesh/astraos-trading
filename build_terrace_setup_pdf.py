from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
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
IMG_DIR = OUT_DIR / "terrace_setup_images"
OUT_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)

TERRACE_IMAGE = Path(r"C:\Users\atlur\Downloads\terrace.jpeg")
PDF_PATH = OUT_DIR / "Satheesh_Terrace_Setup_From_Scratch_Manual.pdf"

GREEN = colors.HexColor("#1B4332")
LIGHT_GREEN = colors.HexColor("#52B788")
PALE_GREEN = colors.HexColor("#EAF7EF")
GOLD = colors.HexColor("#F9C74F")
DARK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#5C6B73")
RED = colors.HexColor("#9B2226")
BLUE = colors.HexColor("#1D4E89")
GREY = colors.HexColor("#E9ECEF")


def make_terrace_assets() -> dict[str, Path]:
    assets = {}
    if TERRACE_IMAGE.exists():
        img = Image.open(TERRACE_IMAGE).convert("RGB")
        img.thumbnail((1200, 900))
        terrace_out = IMG_DIR / "terrace_original_used.jpg"
        img.save(terrace_out, quality=88)
        assets["terrace"] = terrace_out

        ann = img.copy()
        draw = ImageDraw.Draw(ann, "RGBA")
        w, h = ann.size
        # approximate perspective regions based on supplied photo
        left_poly = [(int(w * 0.12), int(h * 0.31)), (int(w * 0.46), int(h * 0.35)), (int(w * 0.45), int(h * 0.86)), (int(w * 0.09), int(h * 0.83))]
        right_poly = [(int(w * 0.60), int(h * 0.33)), (int(w * 0.87), int(h * 0.30)), (int(w * 0.92), int(h * 0.82)), (int(w * 0.58), int(h * 0.84))]
        center_poly = [(int(w * 0.43), int(h * 0.34)), (int(w * 0.62), int(h * 0.34)), (int(w * 0.58), int(h * 0.85)), (int(w * 0.44), int(h * 0.86))]
        back_poly = [(int(w * 0.35), int(h * 0.26)), (int(w * 0.70), int(h * 0.26)), (int(w * 0.66), int(h * 0.36)), (int(w * 0.39), int(h * 0.36))]
        draw.polygon(left_poly, fill=(82, 183, 136, 90), outline=(27, 67, 50, 255))
        draw.polygon(right_poly, fill=(249, 199, 79, 95), outline=(180, 120, 0, 255))
        draw.polygon(center_poly, fill=(255, 255, 255, 80), outline=(255, 255, 255, 230))
        draw.polygon(back_poly, fill=(29, 78, 137, 95), outline=(29, 78, 137, 255))
        try:
            font_big = ImageFont.truetype("arial.ttf", max(18, w // 38))
            font_small = ImageFont.truetype("arial.ttf", max(14, w // 52))
        except Exception:
            font_big = ImageFont.load_default()
            font_small = ImageFont.load_default()
        labels = [
            ("ZONE A\nGrow bags\n3-tier shelf", int(w * 0.21), int(h * 0.50), (27, 67, 50)),
            ("WALKWAY\nkeep clear", int(w * 0.47), int(h * 0.57), (40, 40, 40)),
            ("ZONE B\nNFT + existing plants", int(w * 0.65), int(h * 0.52), (90, 60, 0)),
            ("ZONE C\nWater + IoT\nfertilizer corner", int(w * 0.44), int(h * 0.28), (20, 55, 100)),
        ]
        for text, x, y, col in labels:
            draw.rounded_rectangle((x - 8, y - 8, x + 210, y + 58), radius=10, fill=(255, 255, 255, 210))
            draw.multiline_text((x, y), text, font=font_big if "ZONE" in text else font_small, fill=col, spacing=3)
        ann_out = IMG_DIR / "terrace_annotated_zones.jpg"
        ann.save(ann_out, quality=90)
        assets["terrace_annotated"] = ann_out

    # Create simple visual diagrams as PNGs
    def diagram_canvas(name: str, title: str, boxes: list[tuple[str, tuple[int, int, int, int], tuple[int, int, int]]], arrows=None):
        W, H = 1400, 850
        img = Image.new("RGB", (W, H), "#F8FBF8")
        d = ImageDraw.Draw(img)
        try:
            ft = ImageFont.truetype("arial.ttf", 42)
            fb = ImageFont.truetype("arial.ttf", 28)
            fs = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            ft = fb = fs = ImageFont.load_default()
        d.rectangle((0, 0, W, 95), fill="#1B4332")
        d.text((40, 25), title, font=ft, fill="white")
        for text, rect, fill in boxes:
            x1, y1, x2, y2 = rect
            d.rounded_rectangle(rect, radius=24, fill=fill, outline="#1B4332", width=4)
            lines = text.split("\n")
            yy = y1 + 22
            for line in lines:
                d.text((x1 + 22, yy), line, font=fb if yy == y1 + 22 else fs, fill="#1F2933")
                yy += 36
        if arrows:
            for (x1, y1, x2, y2, txt) in arrows:
                d.line((x1, y1, x2, y2), fill="#1B4332", width=7)
                ang = math.atan2(y2 - y1, x2 - x1)
                for a in [ang + 2.6, ang - 2.6]:
                    d.line((x2, y2, x2 - 30 * math.cos(a), y2 - 30 * math.sin(a)), fill="#1B4332", width=7)
                if txt:
                    d.text(((x1 + x2) // 2, (y1 + y2) // 2 - 30), txt, font=fs, fill="#9B2226")
        out = IMG_DIR / name
        img.save(out, quality=92)
        assets[name] = out

    diagram_canvas(
        "terrace_top_plan.jpg",
        "Recommended top-view layout for your terrace",
        [
            ("ZONE A: GROW BAGS\nLeft side 3-tier shelf\nTomato, chilli, brinjal,\nbhindi, cucumber", (80, 170, 440, 690), (183, 228, 199)),
            ("CENTER WALKWAY\nMinimum 3 ft clear\nNo pots, no pipes,\nno electric wires on floor", (470, 170, 800, 690), (255, 255, 255)),
            ("ZONE B: NFT + VERTICAL\nRight parapet wall\n4 PVC pipes + mint,\nmethi, coriander, palak", (830, 170, 1280, 690), (249, 199, 79)),
            ("ZONE C: BACK HUB\nWater tank, filter,\nESP32 box, fertilizer corner", (420, 705, 980, 815), (173, 216, 230)),
        ],
    )
    diagram_canvas(
        "waterproof_stack.jpg",
        "Terrace protection stack before farming",
        [
            ("Plants / grow bags / NFT reservoir", (170, 145, 1230, 230), (183, 228, 199)),
            ("Raised stand or plastic pallet: 2-4 inch air gap", (170, 255, 1230, 340), (149, 213, 178)),
            ("Drain tray + overflow pipe to terrace drain", (170, 365, 1230, 450), (216, 243, 220)),
            ("Geotextile or protection sheet", (170, 475, 1230, 560), (234, 247, 239)),
            ("Waterproof membrane / coating", (170, 585, 1230, 670), (249, 199, 79)),
            ("Existing terrace slab and tiles", (170, 695, 1230, 780), (202, 210, 197)),
        ],
    )
    diagram_canvas(
        "nft_wall_build.jpg",
        "NFT wall build sequence",
        [
            ("1. Mark pipe line\n3 ft, 4 ft, 5 ft, 6 ft heights", (60, 160, 380, 335), (234, 247, 239)),
            ("2. Drill 38mm holes\n5 holes per 6 ft pipe", (410, 160, 730, 335), (216, 243, 220)),
            ("3. Add sponge strip\ninside round PVC pipe", (760, 160, 1080, 335), (183, 228, 199)),
            ("4. Fix slope\n3-4 degree drop", (1110, 160, 1360, 335), (249, 199, 79)),
            ("5. Pump to inlets\n13mm tube distributor", (230, 500, 600, 700), (173, 216, 230)),
            ("6. Gravity drain\nback to 20L reservoir", (780, 500, 1180, 700), (255, 255, 255)),
        ],
        arrows=[(380, 245, 410, 245, ""), (730, 245, 760, 245, ""), (1080, 245, 1110, 245, ""), (640, 600, 760, 600, "water returns")],
    )
    diagram_canvas(
        "grow_bag_shelf.jpg",
        "3-tier grow bag shelf arrangement",
        [
            ("Top shelf\nBhindi, beans, herbs\nlighter bags", (110, 145, 1250, 265), (183, 228, 199)),
            ("Middle shelf\nChilli, capsicum,\ncucumber with trellis", (110, 330, 1250, 475), (216, 243, 220)),
            ("Bottom shelf\nTomato, brinjal\nheaviest bags", (110, 545, 1250, 705), (249, 199, 79)),
            ("Floor must stay dry\nUse tray + air gap", (350, 735, 1030, 815), (255, 255, 255)),
        ],
    )
    diagram_canvas(
        "iot_sensor_map.jpg",
        "Sensor and camera placement",
        [
            ("Camera 1\nBack-left high angle\nsees grow bags", (80, 160, 420, 340), (183, 228, 199)),
            ("Camera 2\nBack-right high angle\nsees NFT pipes", (980, 160, 1320, 340), (249, 199, 79)),
            ("ESP32 Box\nBack wall, shaded,\nwaterproof IP65", (500, 160, 900, 340), (173, 216, 230)),
            ("Moisture sensors\n1 each in tomato,\nchilli, bhindi groups", (80, 500, 480, 710), (216, 243, 220)),
            ("pH + TDS + water temp\ninside NFT reservoir", (520, 500, 920, 710), (255, 255, 255)),
            ("DHT22 + LDR\ncenter shade,\nnot direct sun", (960, 500, 1320, 710), (234, 247, 239)),
        ],
    )
    return assets


def page_header(canvas, doc):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(GREEN)
    canvas.rect(0, height - 0.95 * cm, width, 0.95 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 8.3)
    canvas.drawString(1.2 * cm, height - 0.6 * cm, "Satheesh Terrace Farm Setup Manual")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - 1.2 * cm, height - 0.6 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(LIGHT_GREEN)
    canvas.line(1.2 * cm, 1.15 * cm, width - 1.2 * cm, 1.15 * cm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawCentredString(width / 2, 0.72 * cm, "From empty terrace to protected smart organic farm")
    canvas.restoreState()


class ColorBand(Flowable):
    def __init__(self, text, color=PALE_GREEN, text_color=GREEN, height=1.15 * cm):
        super().__init__()
        self.text = text
        self.color = color
        self.text_color = text_color
        self.height = height

    def wrap(self, availWidth, availHeight):
        self.width = availWidth
        return availWidth, self.height

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=0)
        self.canv.setFillColor(self.text_color)
        self.canv.setFont("Helvetica-Bold", 9)
        self.canv.drawString(0.35 * cm, 0.38 * cm, self.text)


def styles():
    base = getSampleStyleSheet()
    return {
        "Title": ParagraphStyle("Title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=GREEN, alignment=TA_CENTER, spaceAfter=8),
        "Sub": ParagraphStyle("Sub", parent=base["Normal"], fontSize=10.5, leading=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=8),
        "H1": ParagraphStyle("H1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15.5, leading=19, textColor=GREEN, spaceBefore=8, spaceAfter=5),
        "H2": ParagraphStyle("H2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12.2, leading=15, textColor=colors.HexColor("#2D6A4F"), spaceBefore=6, spaceAfter=4),
        "H3": ParagraphStyle("H3", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=10.4, leading=13, textColor=BLUE, spaceBefore=5, spaceAfter=2),
        "Body": ParagraphStyle("Body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7, leading=11.2, textColor=DARK, spaceAfter=3.6),
        "Small": ParagraphStyle("Small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2, leading=8.7, textColor=MUTED, spaceAfter=2),
        "Callout": ParagraphStyle("Callout", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11.2, textColor=GREEN, backColor=PALE_GREEN, borderPadding=5, borderColor=LIGHT_GREEN, spaceAfter=5),
        "Warn": ParagraphStyle("Warn", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=8.5, leading=11.2, textColor=RED, backColor=colors.HexColor("#FFF3E0"), borderPadding=5, borderColor=GOLD, spaceAfter=5),
        "Caption": ParagraphStyle("Caption", parent=base["BodyText"], fontName="Helvetica-Oblique", fontSize=7, leading=8.2, textColor=MUTED, alignment=TA_CENTER, spaceAfter=4),
    }


S = styles()


def p(text, style="Body"):
    return Paragraph(text.replace("₹", "Rs. "), S[style])


def bullets(items):
    return ListFlowable([ListItem(p(i), leftIndent=8) for i in items], bulletType="bullet", leftIndent=14, bulletFontSize=5, spaceAfter=3)


def tbl(data, widths=None, font=7.2, header=True):
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    st = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", font),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCD5AE")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FBF8")]),
    ]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), GREEN), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", font)]
    t.setStyle(TableStyle(st))
    return t


def image(path, width=16.5 * cm, caption=None):
    im = Image.open(path)
    iw, ih = im.size
    height = min(width * ih / iw, 12.0 * cm)
    flows = [RLImage(str(path), width=width, height=height)]
    if caption:
        flows.append(p(caption, "Caption"))
    return flows


def section(title, note=None):
    flows = [PageBreak(), p(title, "H1")]
    if note:
        flows.append(p(note, "Callout"))
    return flows


def build_story(assets):
    story = []
    story.append(Spacer(1, 0.5 * cm))
    story.append(p("Satheesh's Terrace Farm Setup Manual", "Title"))
    story.append(p("Step-by-step beginner guide from empty terrace to protected smart organic farm", "Sub"))
    story.append(p("Based on the terrace photo provided: strong parapet walls, open walking space, existing right-side plants, hill-side humidity, and leakage risk.", "Sub"))
    if "terrace" in assets:
        story += image(assets["terrace"], width=14.5 * cm, caption="Your terrace photo used for this setup plan.")
    story.append(ColorBand("Golden rule: protect the terrace first, then build the farm. A farm that leaks is not a farm; it becomes a building problem."))
    story.append(PageBreak())

    story.append(p("1. What I See On Your Terrace", "H1"))
    if "terrace_annotated" in assets:
        story += image(assets["terrace_annotated"], caption="Recommended zones overlaid on your terrace photo.")
    story.append(tbl([
        ["Observation from photo", "What it means for setup"],
        ["Long clear rectangular terrace", "Excellent for left/right zoning with a center walkway."],
        ["Strong parapet walls", "Good for NFT mounting, trellis, cameras, shade-net hooks and pipe support."],
        ["Existing plants on right side", "Right side already behaves like a green wall; expand it into NFT + vertical garden."],
        ["Open hill side and sky", "Good airflow and humidity, useful for mint, leafy greens and creepers."],
        ["Tile floor with leakage concern", "All systems must be raised with trays and drainage; no direct wet load on tiles."],
        ["Overhead metal/pipe structure visible", "Can help support shade net, but check strength before hanging load."],
    ], [5.0 * cm, 11.5 * cm]))
    story.append(p("My verdict: your terrace is suitable, but the design must be clean, raised, and modular. Do not cover the whole floor with pots. Keep the center open so you can inspect, harvest, clean, and repair leaks.", "Callout"))

    story += section("2. Final Layout For Your Terrace", "This layout is chosen to match the actual photo, not a generic terrace drawing.")
    story += image(assets["terrace_top_plan.jpg"], caption="Top-view layout: left grow bags, center walkway, right NFT, back infrastructure hub.")
    story.append(tbl([
        ["Zone", "Position", "Use", "Why this is best"],
        ["Zone A", "Left side from entry", "3-tier grow bag shelf", "Open space, easy access, less disturbance to existing plants."],
        ["Zone B", "Right parapet", "NFT pipes + existing plants + vertical garden", "Already has greenery and wall support; pipes can mount above floor."],
        ["Zone C", "Back/hill side corner", "Water tank, filter, ESP32, fertilizer corner", "Close to parapet, easy to route rainwater and wiring."],
        ["Center", "Middle walkway", "3 ft clear path", "Maintenance, harvesting, emergency repair and leak inspection."],
    ], [2.5 * cm, 3.4 * cm, 4.4 * cm, 6.2 * cm]))

    story += section("3. Build Order From Scratch", "Do not start by buying plants. Start by making the terrace ready. This is how experienced farmers avoid expensive rework.")
    story.append(tbl([
        ["Phase", "Build work", "Result"],
        ["0", "Measure, clean, inspect leaks, decide drain direction", "You know exact working area and weak spots."],
        ["1", "Waterproof protection and raised base system", "Terrace safe from daily water."],
        ["2", "Install left grow-bag shelf and right NFT wall clamps", "Farm structure ready without plants."],
        ["3", "Install water storage, reservoir, gutters and drainage trays", "Water movement controlled."],
        ["4", "Add grow bags, soil mix, trellis and NFT pipes", "Crop zones ready."],
        ["5", "Install sensors, cameras, ESP32 box and electrical safety", "Monitoring ready."],
        ["6", "Plant only 30-40% capacity first, then expand", "Less risk while you learn."],
    ], [1.6 * cm, 9.2 * cm, 5.7 * cm]))
    story.append(p("Old farmer lesson: first season is not for showing off. First season is for learning your terrace's water, heat, wind and pest behavior. After that, expansion becomes easy.", "Callout"))

    story += section("4. Phase 0: Measure And Mark", "Beginner work: one tape, one chalk, one notebook. Do this before buying material.")
    story.append(tbl([
        ["Task", "How to do it", "Why"],
        ["Measure length and width", "Use tape; write exact feet/inches.", "Your shelf, pipe and tank decisions depend on real size."],
        ["Mark 3 ft walkway", "Chalk a center walking lane from entry to back.", "This must remain empty forever."],
        ["Find drain direction", "Pour 1 bucket water and watch flow.", "All tray outlets should point toward drain."],
        ["Leak inspection", "Check floor cracks, parapet corners, tile joints.", "Repair before placing farm weight."],
        ["Sun observation", "Take photos at 8am, 12pm, 4pm.", "Decides crop positions and shade net."],
        ["Wind observation", "Watch which side gets strong wind.", "Trellis and tall plants need support there."],
    ], [3.2 * cm, 7.2 * cm, 6.1 * cm]))

    story += section("5. Phase 1: Terrace Protection", "Because you already have leakage concern, this is the most important chapter.")
    story += image(assets["waterproof_stack.jpg"], caption="Protection stack: farming system sits above the terrace, not directly on the terrace.")
    story.append(bullets([
        "Repair cracks and parapet joints before farm installation.",
        "Add waterproof membrane/top coat if leakage continues after damp-proof paint.",
        "Place geotextile/protection sheet under active farm zones.",
        "Use plastic pallets, PVC stands or GI stands to create 2-4 inch air gap.",
        "Every grow bag shelf must have a drain tray or gutter below.",
        "Every reservoir or fertilizer drum must sit inside a catch tray.",
        "Keep drain outlet open and add leaf mesh so compost/leaves do not block it.",
    ]))
    story.append(p("Do not trust only paint. Paint protects surface, but daily farming creates continuous wetting. Your protection must include drainage and air gap.", "Warn"))

    story += section("6. Phase 2: Build Zone A Grow Bag Shelf", "This side will grow fruiting vegetables. Fruiting crops need root depth, support and stable moisture.")
    story += image(assets["grow_bag_shelf.jpg"], caption="3-tier shelf plan for left side.")
    story.append(tbl([
        ["Part", "Specification", "Beginner note"],
        ["Frame", "1 inch GI square pipe or treated bamboo", "GI is stronger; bamboo cheaper but needs replacement."],
        ["Size", "About 6 ft wide x 10-12 ft long x 6 ft high", "Keep inside terrace wall line."],
        ["Shelves", "3 levels: 2 ft, 4 ft, 6 ft", "Do not overload top shelf with heavy wet bags."],
        ["Bag placement", "Heaviest bags bottom", "Tomato/brinjal below; herbs/beans above."],
        ["Drainage", "Tray/gutter below each shelf", "Water must return to drain, not floor."],
        ["Support", "Tie frame to parapet/wall if windy", "Prevents falling during storms."],
    ], [3.0 * cm, 6.0 * cm, 7.5 * cm]))
    story.append(p("Recommended first crop load", "H2"))
    story.append(tbl([
        ["Crop", "Bags first month", "Bag size", "Why"],
        ["Tomato", "2", "24x24 inch", "Learn staking and watering first."],
        ["Chilli", "3", "15x15 inch", "Good for Chittoor heat."],
        ["Brinjal", "2", "15x15 inch", "Strong terrace crop."],
        ["Bhindi", "4", "12x12 inch", "Beginner-friendly summer crop."],
        ["Cucumber", "1", "15x15 inch + trellis", "Needs moisture and training."],
        ["Herbs", "4-6 small pots", "10x10 inch", "Fast confidence crops."],
    ], [3.0 * cm, 3.0 * cm, 4.0 * cm, 6.5 * cm]))

    story += section("7. Phase 3: Build Zone B NFT Wall", "Right side is best for NFT because the parapet can carry pipe clamps and wiring can run along wall.")
    story += image(assets["nft_wall_build.jpg"], caption="NFT build sequence for right parapet wall.")
    story.append(tbl([
        ["Step", "Action", "Exact practical instruction"],
        ["1", "Cut PVC pipes", "Use 2.5 inch round PVC, 6 ft each, 4 pipes."],
        ["2", "Mark net pot holes", "5 holes per pipe, about 15cm spacing; keep ends clear."],
        ["3", "Drill holes", "Use 38mm hole saw; drill slowly to avoid cracking."],
        ["4", "Add foam strip", "55mm wide kitchen sponge strip along pipe bottom to spread water."],
        ["5", "Mount clamps", "Bottom pipe around 3 ft height; next at 4, 5, 6 ft."],
        ["6", "Set slope", "3-4 degree slope, about 3.5-5 inch drop over 6 ft."],
        ["7", "Connect pump", "300-500 LPH pump from 20L black reservoir."],
        ["8", "Test with plain water", "Run 2 hours before adding plants; fix leaks first."],
    ], [1.4 * cm, 4.0 * cm, 11.1 * cm], font=7.0))
    story.append(p("Important: organic NFT is more difficult than grow bags. Start NFT with plain water test and simple leafy greens. Keep Jeevamrutham highly filtered. Biofilm and clogging are the main enemies.", "Warn"))

    story += section("8. Phase 4: Zone C Water, IoT And Fertilizer Hub", "Back side should become the service area, but do not overload one small point.")
    story.append(tbl([
        ["Item", "Placement", "Safety rule"],
        ["500L tank", "Back/side near strong wall or beam", "Needs strong stand; full tank weighs 500+ kg."],
        ["20L NFT reservoir", "Below NFT pipes on right side", "Must sit in tray, covered from sunlight."],
        ["Filter unit", "Between rainwater/tank and farm lines", "Easy access for cleaning."],
        ["ESP32 box", "Back wall, shaded, waterproof IP65", "Never place on floor."],
        ["Battery/solar controller", "Weatherproof box, ventilated", "Keep away from water spray."],
        ["Fertilizer corner", "Small raised tray area", "No wet drum directly on tiles."],
    ], [3.6 * cm, 6.2 * cm, 6.7 * cm]))
    story.append(p("Water flow plan", "H2"))
    story.append(bullets([
        "Rain gutter collects roof/terrace water into first-flush diverter.",
        "First dirty water is discarded, clean water enters settling/filter unit.",
        "Filtered water goes to 500L tank.",
        "Tank gravity-feeds drip lines for grow bags.",
        "NFT reservoir runs separately with pump and returns water by gravity.",
        "Overflow from any tray must go to terrace drain, not random floor flow.",
    ]))

    story += section("9. Phase 5: Sensor And Camera Setup", "Sensors should first observe. Do not make automation control everything until readings are stable.")
    story += image(assets["iot_sensor_map.jpg"], caption="Sensor and camera placement plan.")
    story.append(tbl([
        ["Device", "Where to place", "Beginner purpose"],
        ["Moisture sensor A", "One tomato/cucumber bag", "High-water group reading."],
        ["Moisture sensor B", "One chilli/brinjal bag", "Medium-water group reading."],
        ["Moisture sensor C", "One bhindi/beans bag", "Low-water group reading."],
        ["pH sensor", "NFT reservoir", "Prevent root nutrient problems."],
        ["TDS sensor", "NFT reservoir", "Watch solution strength."],
        ["DS18B20", "NFT reservoir water", "Heat warning."],
        ["DHT22", "Center shade at 3 ft height", "Air temp/humidity."],
        ["ESP32-CAM 1", "Back-left high angle", "Grow bag disease observation."],
        ["ESP32-CAM 2", "Back-right high angle", "NFT and right wall observation."],
    ], [3.2 * cm, 5.4 * cm, 7.9 * cm], font=6.8))

    story += section("10. Soil Mix And Planting From Zero", "Do not fill bags with random mud. Container soil must drain, breathe and feed microbes.")
    story.append(tbl([
        ["Ingredient", "Ratio", "Purpose"],
        ["Cocopeat", "40%", "Moisture holding and lightness."],
        ["Forest sand / coarse sand", "20%", "Drainage and weight balance."],
        ["Vermicompost / mature compost", "30%", "Nutrition and biology."],
        ["Charged biochar / charcoal", "10%", "Water, nutrients and microbial housing."],
        ["Neem cake", "1 handful per medium bag", "Root pest protection."],
    ], [4.0 * cm, 3.0 * cm, 9.5 * cm]))
    story.append(p("Filling steps", "H2"))
    story.append(bullets([
        "Place bag on shelf/tray, not on floor.",
        "Add a few broken tile pieces or coco chips at bottom only if drainage holes are large.",
        "Mix soil outside the bag first so it is even.",
        "Fill 80-85%, not to the top. Leave watering space.",
        "Water once and wait one day before transplanting.",
        "After planting, mulch the top with dry leaves to reduce heat.",
    ]))

    story += section("11. First 90 Days Planting Plan", "This plan avoids overload. You learn with strong crops first, then add difficult crops.")
    story.append(tbl([
        ["Period", "Do this", "Do not do this"],
        ["Week 1", "Build protection, shelf, NFT frame, water test", "Do not buy all seedlings yet."],
        ["Week 2", "Plant chilli, bhindi, brinjal, herbs in grow bags", "Do not overwater daily by habit."],
        ["Week 3", "Start tomato and cucumber with stakes/trellis", "Do not leave vines unsupported."],
        ["Week 4", "Start NFT with mint/methi first", "Do not add thick organic liquids to NFT."],
        ["Month 2", "Add coriander/palak if temperature allows", "Do not ignore summer shade."],
        ["Month 3", "Expand to full bag count if drainage is clean", "Do not scale if leaks/smell/insects are unresolved."],
    ], [2.5 * cm, 7.4 * cm, 6.6 * cm]))

    story += section("12. Tools And Material List", "Buy in layers. This prevents wasting money.")
    story.append(tbl([
        ["Category", "Items", "Approx cost range"],
        ["Terrace protection", "Trays, pallets/stands, drain mesh, sealant", "Rs. 2,000-6,000"],
        ["Grow bags", "15x15, 24x24, 12x12 bags", "Rs. 1,500-3,000"],
        ["Shelf", "GI/bamboo frame, planks/mesh", "Rs. 1,500-5,000"],
        ["NFT", "PVC pipes, caps, pump, tubes, clamps, net pots", "Rs. 2,000-4,500"],
        ["Water", "Tank, filter, drip pipes, valves", "Rs. 3,000-8,000"],
        ["IoT", "ESP32, sensors, relay, wires, box", "Rs. 4,000-8,000"],
        ["Organic inputs", "Cocopeat, compost, neem cake, jaggery", "Rs. 1,500-4,000"],
        ["Safety", "MCB/RCCB, waterproof boxes, cable ducts", "Rs. 2,000-5,000"],
    ], [3.2 * cm, 9.2 * cm, 4.1 * cm], font=6.8))

    story += section("13. Common Problems I Would Expect On Your Terrace", "This is where experience matters. These problems are normal; the solution is preparation.")
    story.append(tbl([
        ["Problem", "Why it happens", "Prevention"],
        ["Water leaking below", "Standing water, tile joints, no trays", "Raised system + drainage + weekly inspection."],
        ["NFT water too hot", "Reservoir in sun, Chittoor summer", "Shade reservoir, white cover, airflow, water temp sensor."],
        ["Plants dry fast", "Tile heat and wind", "Mulch, morning watering, shade net."],
        ["Fungus in monsoon", "Hill humidity + wet leaves", "Morning watering only, airflow, neem/buttermilk preventive."],
        ["Pests from existing plants", "Old plant line can host insects", "Inspect underside weekly, prune, neem spray."],
        ["Center becomes messy", "Pots slowly occupy walkway", "Walkway is sacred: keep empty always."],
        ["Electrical risk", "Water + loose wires", "Elevated wires, waterproof boxes, MCB/RCCB."],
    ], [3.2 * cm, 5.4 * cm, 7.9 * cm], font=6.8))

    story += section("14. Daily, Weekly, Monthly Routine", "This routine is more important than expensive technology.")
    story.append(tbl([
        ["Frequency", "Checklist"],
        ["Daily morning", "Check water level, pump sound, leaf wilting, soil moisture, NFT flow, any floor water."],
        ["Daily evening", "Look for pests, tie vines, check camera view, close fertilizer containers."],
        ["Weekly", "Clean drain mesh, inspect leaf undersides, apply Jeevamrutham, check shade-net ropes."],
        ["Every 15 days", "Calibrate pH sensor if installed, prune dead leaves, check pipe joints."],
        ["Monthly", "Flush NFT, inspect waterproofing, clean trays, recharge compost, review records."],
        ["Before rain", "Cover fertilizer drums, clear drains, secure trellis, check overflow pipes."],
    ], [3.0 * cm, 13.5 * cm]))

    story += section("15. Beginner Rules That Save The Farm", "If you remember only one page, remember this.")
    story.append(bullets([
        "No grow bag directly on terrace floor.",
        "No water tank without proper stand and weight planning.",
        "No electrical item on floor.",
        "No raw kitchen waste in grow bags.",
        "No spraying in afternoon heat.",
        "No full automation until manual system works.",
        "No overcrowding plants in first 90 days.",
        "No blocked center walkway.",
        "No ignoring first disease sign.",
        "No trusting memory: write dates, batches and plant response.",
    ]))
    story.append(p("The mindset: your terrace is not just a garden. It is a small agricultural engineering system. Water, heat, roots, weight, microbes and electricity must all be controlled.", "Callout"))

    story += section("16. Printable Build Checklist", "Use this as your actual work checklist.")
    story.append(tbl([
        ["Done", "Task"],
        ["☐", "Measure terrace exact length, width and drain direction."],
        ["☐", "Mark center walkway with chalk."],
        ["☐", "Repair cracks and parapet joints."],
        ["☐", "Install raised base/trays under future grow zones."],
        ["☐", "Build left-side grow bag shelf."],
        ["☐", "Mount right-side NFT clamps without pipes first."],
        ["☐", "Install water tank/stand and reservoir tray."],
        ["☐", "Test NFT pipes with plain water for 2 hours."],
        ["☐", "Fill first 10-15 grow bags only."],
        ["☐", "Plant first beginner crops."],
        ["☐", "Install sensors after plants and water system are stable."],
        ["☐", "Start daily farm notebook."],
    ], [2.0 * cm, 14.5 * cm]))

    story += section("17. Final Recommended First Build", "This is my practical build recommendation for your exact terrace.")
    story.append(tbl([
        ["Build item", "Recommended first version"],
        ["Grow bags", "Start with 12-15 bags, not 30. Expand after 45 days."],
        ["NFT", "Install all 4 pipes physically, but run only 2 pipes first."],
        ["Water tank", "Use 200-300L first if structural doubt exists; upgrade to 500L after confirming stand and leakage."],
        ["Shade net", "Install hooks now; use 50% shade net in summer."],
        ["Fertilizer", "Use compost + Jeevamrutham first; add FPJ after flowering."],
        ["Automation", "Start with monitoring alerts only; automation after 1 month of reliable readings."],
        ["Marketing", "Do not sell first harvest. Use it to learn quality, yield and timing."],
    ], [4.5 * cm, 12.0 * cm]))
    story.append(p("My honest advice: your terrace can support the project, but success will come from clean layout, drainage discipline, and gradual plant loading. Build the infrastructure in one phase, but activate crops and automation step by step.", "Callout"))

    return story


def build_pdf():
    assets = make_terrace_assets()
    doc = BaseDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=1.25 * cm,
        rightMargin=1.25 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.45 * cm,
        title="Satheesh Terrace Setup From Scratch Manual",
        author="OpenAI Codex for Satheesh",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page_header)])
    doc.build(build_story(assets))
    print(PDF_PATH)


if __name__ == "__main__":
    build_pdf()
