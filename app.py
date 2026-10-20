from flask import Flask, render_template, request, send_file, jsonify
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from PIL import Image, ImageOps
from io import BytesIO
from pathlib import Path
import os
import re

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / "assets" / "master_template.png"
W, H = 595.5, 842.25

LIMITS = {
    "group_name": 12,
    "visit_place": 14,
    "insight": 36,
    "member_comment": 24,
}

# Precise table geometry measured from the supplied master template.
VISIT_ROWS = [
    {"idx": 1, "center_y": 453.88, "photo_box": (384.0, 405.2, 164.0, 96.5)},
    {"idx": 2, "center_y": 350.46, "photo_box": (384.0, 301.8, 164.0, 96.5)},
    {"idx": 3, "center_y": 247.16, "photo_box": (384.0, 198.5, 164.0, 96.5)},
]

COMMENT_SLOTS = [
    (1, 52.0, 108.0, 235.0),
    (2, 52.0, 87.0, 235.0),
    (3, 52.0, 66.0, 235.0),
    (4, 307.0, 108.0, 235.0),
    (5, 307.0, 87.0, 235.0),
    (6, 307.0, 66.0, 235.0),
]


def register_fonts():
    regular_candidates = []
    bold_candidates = []

    if os.name == "nt":
        fonts_dir = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts"
        regular_candidates += [fonts_dir / "malgun.ttf", fonts_dir / "NanumGothic.ttf"]
        bold_candidates += [fonts_dir / "malgunbd.ttf", fonts_dir / "NanumGothicBold.ttf"]

    regular_candidates += [
        BASE / "runtime_fonts" / "NanumGothic-Regular.ttf",
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
    ]
    bold_candidates += [
        BASE / "runtime_fonts" / "NanumGothic-Bold.ttf",
        Path("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    ]

    regular = next((p for p in regular_candidates if p.exists()), None)
    bold = next((p for p in bold_candidates if p.exists()), None)
    if not regular or not bold:
        raise RuntimeError("Korean TrueType fonts are missing. Rebuild the service.")

    pdfmetrics.registerFont(TTFont("Korean", str(regular)))
    pdfmetrics.registerFont(TTFont("KoreanBold", str(bold)))


register_fonts()


def clean(value, limit=800):
    return re.sub(r"[\r\t]+", " ", (value or "").strip())[:limit]


def fit_size(text, font, max_width, size, minimum=5.8):
    while size > minimum and pdfmetrics.stringWidth(text, font, size) > max_width:
        size -= 0.2
    return size


def vertical_baseline(font, size, center_y, optical=0.0):
    ascent, descent = pdfmetrics.getAscentDescent(font, size)
    return center_y - (ascent + descent) / 2 + optical


def draw_center(c, text, center_x, center_y, max_width, size=9.0, font="Korean", white=False, optical=0.8):
    text = clean(text)
    if not text:
        return
    size = fit_size(text, font, max_width, size)
    c.setFillColor(HexColor("#FFFFFF") if white else HexColor("#333333"))
    c.setFont(font, size)
    c.drawCentredString(center_x, vertical_baseline(font, size, center_y, optical), text)


def wrap_text(text, font, size, max_width):
    text = clean(text)
    lines = []
    cur = ""
    for ch in text:
        if ch == "\n":
            if cur:
                lines.append(cur)
                cur = ""
            continue
        candidate = cur + ch
        if pdfmetrics.stringWidth(candidate, font, size) <= max_width:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def draw_two_insights(c, item1, item2, x, center_y, max_width, max_height):
    items = [clean(item1, LIMITS["insight"]), clean(item2, LIMITS["insight"])]
    size = 8.0
    minimum = 6.0

    while size >= minimum:
        leading = size * 1.30
        gap = size * 1.05
        rendered = []
        total_h = 0
        bullet = "• "
        bullet_w = pdfmetrics.stringWidth(bullet, "Korean", size)
        for item in items:
            lines = wrap_text(item, "Korean", size, max_width - bullet_w)
            rendered.append(lines)
            total_h += len(lines) * leading
        total_h += gap
        if total_h <= max_height:
            break
        size -= 0.2

    if size < minimum:
        size = minimum
        leading = size * 1.30
        gap = size * 0.85
        bullet = "• "
        bullet_w = pdfmetrics.stringWidth(bullet, "Korean", size)
        rendered = [wrap_text(item, "Korean", size, max_width - bullet_w)[:2] for item in items]
        total_h = sum(len(lines) * leading for lines in rendered) + gap

    y = center_y + total_h / 2 - size * 0.35
    c.setFillColor(HexColor("#333333"))
    c.setFont("Korean", size)

    for n, lines in enumerate(rendered):
        if not lines:
            continue
        c.drawString(x, y, bullet + lines[0])
        for extra in lines[1:]:
            y -= leading
            c.drawString(x + bullet_w, y, extra)
        if n == 0:
            y -= leading + gap


def prepare_photo(file_storage):
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None
    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img).convert("RGB")
        max_px = 1600
        scale = min(1.0, max_px / max(img.size))
        if scale < 1.0:
            img = img.resize(
                (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                Image.Resampling.LANCZOS,
            )
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        buf.seek(0)
        return {"buffer": buf, "width": img.width, "height": img.height}
    except Exception:
        return None


def draw_photo_contain(c, photo, box_x, box_y, box_w, box_h):
    if not photo:
        return

    # A small inset keeps the original template border visible while preserving the full image.
    inset = 3.0
    inner_x = box_x + inset
    inner_y = box_y + inset
    inner_w = box_w - inset * 2
    inner_h = box_h - inset * 2

    iw, ih = photo["width"], photo["height"]
    scale = min(inner_w / iw, inner_h / ih)
    draw_w = iw * scale
    draw_h = ih * scale
    dx = inner_x + (inner_w - draw_w) / 2
    dy = inner_y + (inner_h - draw_h) / 2

    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(inner_x, inner_y, inner_w, inner_h, fill=1, stroke=0)
    c.drawImage(
        ImageReader(photo["buffer"]),
        dx, dy, draw_w, draw_h,
        preserveAspectRatio=True,
        mask="auto",
    )


def draw_member_comment(c, name, comment, x, center_y, width):
    name = clean(name, 12)
    comment = clean(comment, LIMITS["member_comment"])
    if not name and not comment:
        return

    prefix = f"• {name}: " if name else "• "
    size = 7.2
    minimum = 5.8
    max_width = width
    while size > minimum and pdfmetrics.stringWidth(prefix + comment, "Korean", size) > max_width:
        size -= 0.2

    c.setFillColor(HexColor("#333333"))
    c.setFont("Korean", size)
    baseline = vertical_baseline("Korean", size, center_y, 0.7)
    c.drawString(x, baseline, prefix + comment)


def build_pdf(data, files):
    out = BytesIO()
    c = canvas.Canvas(out, pagesize=(W, H))
    c.drawImage(ImageReader(str(TEMPLATE)), 0, 0, W, H, mask="auto")

    # Header group number: same baseline as the fixed '조' glyph in the master template.
    draw_center(c, data.get("group_no"), 282.0, 763.0, 60, 38, "KoreanBold", True, optical=0.0)

    # 01. Group information
    draw_center(c, data.get("group_name"), 146.5, 634.0, 112, 9.5, "KoreanBold")
    draw_center(c, data.get("members"), 421.5, 634.0, 286, 8.8, "KoreanBold")

    # 02. Visit summary
    for row in VISIT_ROWS:
        i = row["idx"]
        yc = row["center_y"]

        draw_center(
            c, data.get(f"visit_{i}_place"),
            117.0, yc, 118.0, 9.4, "KoreanBold", False, optical=1.0
        )

        draw_two_insights(
            c,
            data.get(f"visit_{i}_insight_1"),
            data.get(f"visit_{i}_insight_2"),
            190.0, yc, 181.0, 82.0,
        )

        px, py, pw, ph = row["photo_box"]
        photo = prepare_photo(files.get(f"visit_{i}_photo"))
        if photo:
            draw_photo_contain(c, photo, px, py, pw, ph)

    # 03. Up to six member comments in two columns. Empty slots stay blank.
    for idx, x, y, width in COMMENT_SLOTS:
        draw_member_comment(
            c,
            data.get(f"member_{idx}_name"),
            data.get(f"member_{idx}_comment"),
            x, y, width,
        )

    c.save()
    out.seek(0)
    return out


def validate(data, files):
    no = clean(data.get("group_no"))
    if not no.isdigit() or int(no) < 1:
        return "조 번호는 1 이상의 숫자로 입력해주세요."

    if not clean(data.get("group_name")):
        return "조 이름을 입력해주세요."
    if len(clean(data.get("group_name"), 100)) > LIMITS["group_name"]:
        return f"조 이름은 최대 {LIMITS['group_name']}자까지 입력할 수 있습니다."
    if not clean(data.get("members")):
        return "조원 이름을 입력해주세요."

    for i in range(1, 4):
        place = clean(data.get(f"visit_{i}_place"), 100)
        insight1 = clean(data.get(f"visit_{i}_insight_1"), 100)
        insight2 = clean(data.get(f"visit_{i}_insight_2"), 100)
        photo = files.get(f"visit_{i}_photo")

        if not place:
            return f"방문지 {i}의 장소명을 입력해주세요."
        if len(place) > LIMITS["visit_place"]:
            return f"방문지는 최대 {LIMITS['visit_place']}자까지 입력할 수 있습니다."
        if not insight1 or not insight2:
            return f"방문지 {i}의 인사이트를 2가지 모두 작성해주세요."
        if len(insight1) > LIMITS["insight"] or len(insight2) > LIMITS["insight"]:
            return f"인사이트는 항목당 최대 {LIMITS['insight']}자까지 입력할 수 있습니다."
        if not photo or not getattr(photo, "filename", ""):
            return f"방문지 {i}의 활동 사진을 첨부해주세요."

    # If a member-comment slot is used, both name and comment must be present.
    for i in range(1, 7):
        name = clean(data.get(f"member_{i}_name"), 30)
        comment = clean(data.get(f"member_{i}_comment"), 100)
        if bool(name) != bool(comment):
            return f"조원 {i}의 이름과 소감을 함께 입력해주세요."
        if len(comment) > LIMITS["member_comment"]:
            return f"조원 소감은 최대 {LIMITS['member_comment']}자까지 입력할 수 있습니다."

    return None


@app.get("/")
def index():
    return render_template("index.html", limits=LIMITS)


@app.post("/generate")
def generate():
    data = request.form.to_dict()
    error = validate(data, request.files)
    if error:
        return jsonify({"error": error}), 400

    no = clean(data.get("group_no"))
    group_name = clean(data.get("group_name"), LIMITS["group_name"])
    safe = re.sub(r'[\\/:*?"<>|]', "", group_name).strip() or "조"

    return send_file(
        build_pdf(data, request.files),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"탐방결과보고서_{no}조_{safe}.pdf",
    )


@app.errorhandler(413)
def too_large(_):
    return jsonify({"error": "사진 파일 용량이 너무 큽니다. 사진 용량을 줄인 뒤 다시 시도해주세요."}), 413


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
