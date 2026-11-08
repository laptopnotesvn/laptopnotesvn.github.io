#!/usr/bin/env python3
"""Tạo ảnh cho bài viết: featured.webp, hinh-1/2/3.webp và tools/images.json (cần Pillow + mạng).

Chạy:  python tools/make_images.py [--only <slug>] [--force]
- Mặc định bỏ qua file đã có (chạy lại không cần mạng nếu đủ file); --force làm lại.
- featured.webp 1200x750: banner nền sáng, chữ trái, ảnh máy phải (bài không có link SP: banner chữ + hình chip).
- hinh-1 = Features-01 (hoặc ảnh chính SP), hinh-3 = Features-02, hinh-2 = infographic từ <table> của bài.
- Lỗi mạng ở 1 bài chỉ bỏ qua bài đó. Chỉ nhận ảnh từ hungphatlaptop.com / static.hungphatlaptop.com.
build.py (chỉ stdlib) đọc tools/images.json để chèn ảnh + mục lục; script này KHÔNG cần cho build.
"""
import argparse
import html
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
POSTS_DIR = ROOT / "bai-viet"
FONT_DIR = TOOLS / "fonts"
MANIFEST = TOOLS / "images.json"
STYLE_CSS = ROOT / "style.css"

API = "https://hungphatlaptop.com/wp-json/wc/store/v1/products?slug="
UA = "Mozilla/5.0 (compatible; PriceSync/1.0)"
ALLOWED_HOSTS = {"hungphatlaptop.com", "static.hungphatlaptop.com"}
TIMEOUT = 30
MAX_DOWNLOAD = 15 * 1024 * 1024
PAUSE = 0.6

FEAT_W, FEAT_H = 1200, 750
FEAT_LIMIT = 150 * 1024
FIG_LIMIT = 200 * 1024
FIG1_W = 1000
SUB_MAX = 46
CHIP_TEXT = "LAPTOP LẬP TRÌNH"
FILES = ("featured.webp", "hinh-1.webp", "hinh-2.webp", "hinh-3.webp")

# màu lấy từ :root của style.css (do build.py sinh); dự phòng nếu thiếu
DEFAULT_COLORS = {"ink": "#0B1020", "bg": "#F4F5F0", "acc": "#C6F36B", "mut": "#4B5563",
                  "line": "#E2E5DA", "panel": "#10182C", "pline": "#26304A"}


def load_colors():
    cols = dict(DEFAULT_COLORS)
    try:
        css = STYLE_CSS.read_text(encoding="utf-8")
        m = re.search(r":root\{([^}]*)\}", css)
        for k, v in re.findall(r"--([a-z]+):(#[0-9A-Fa-f]{6})", m.group(1) if m else ""):
            cols[k] = v
    except OSError:
        pass
    return cols


COL = load_colors()
_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(str(FONT_DIR / f"BeVietnamPro-{weight}.ttf"), size)
    return _font_cache[key]


# ---------------------------------------------------------------- văn bản
def nfc(s):
    return unicodedata.normalize("NFC", s)


def strip_tags(s):
    return nfc(html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def wrap(text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if not cur or f.getlength(t) <= maxw:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def short_sub(s, limit=SUB_MAX):
    """Rút nhãn phụ còn <= limit ký tự, cắt ở dấu phẩy hoặc ranh giới từ, không cắt giữa chữ."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit + 1]
    i = cut.rfind(",")
    if i >= limit * 0.5:
        return cut[:i].strip()
    j = cut.rfind(" ")
    out = cut[:j].rstrip(" ,;:-")
    return re.sub(r"\s+(và|với|hoặc|của|cho|để|tới|đến|từ|có|là)$", "", out)


def title_parts(title):
    head, _, sub = title.partition(" - ")
    name = head.replace(" cho lập trình", "").strip()
    return nfc(name), nfc(short_sub(sub))


# ---------------------------------------------------------------- bài viết + mạng
def read_article(slug):
    src = (POSTS_DIR / slug / "index.html").read_text(encoding="utf-8")
    m = re.search(r"<title>(.*?)</title>", src, re.S)
    title = html.unescape(m.group(1)).strip() if m else slug
    a0, a1 = src.find("<article>"), src.find("</article>")
    art = src[a0:a1] if 0 <= a0 < a1 else src
    # chỉ bài model (slug kết thúc -lap-trinh) mới lấy ảnh SP; bài kiến thức nhắc SP làm ví dụ thì dùng banner chữ
    m = re.search(r'href="https://hungphatlaptop\.com/([a-z0-9-]+)/"', art) if slug.endswith("-lap-trinh") else None
    return {"slug": slug, "title": title, "art": art, "product": m.group(1) if m else None}


def host_ok(url):
    u = urlparse(url)
    return u.scheme == "https" and u.hostname in ALLOWED_HOSTS


def http_get(url, tries=3):
    if not host_ok(url):
        raise ValueError(f"host không được phép: {url}")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                if not host_ok(r.geturl()):
                    raise ValueError(f"chuyển hướng ra host lạ: {r.geturl()}")
                data = r.read(MAX_DOWNLOAD + 1)
            if len(data) > MAX_DOWNLOAD:
                raise ValueError("ảnh quá lớn")
            return data
        except Exception as e:  # noqa: BLE001 - thử lại rồi báo lên
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def product_images(slug):
    """Trả {'main': url|None, 'feat': {1: url, 2: url, 3: url}, 'name': str}. Item 'variable' mới có đủ gallery."""
    items = json.loads(http_get(API + slug).decode("utf-8"))
    items = [it for it in items if it.get("slug") == slug]
    if not items:
        raise ValueError(f"API không có sản phẩm {slug}")
    it = max(items, key=lambda x: (len(x.get("images") or []), len(x.get("description") or "")))
    imgs = [i.get("src") for i in (it.get("images") or []) if i.get("src")]
    feat = {}
    for m in re.finditer(r"https://(?:static\.)?hungphatlaptop\.com/[^\"' <>]*?Features+-0?(\d)\.(?:jpe?g|png|webp)",
                         it.get("description") or ""):
        feat.setdefault(int(m.group(1)), m.group(0))
    return {"main": next((u for u in imgs if host_ok(u)), None),
            "feat": {k: v for k, v in feat.items() if host_ok(v)}, "name": it.get("name", "")}


def load_img(url):
    im = Image.open(io.BytesIO(http_get(url)))
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, "white")
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


# ---------------------------------------------------------------- ghi webp có giới hạn dung lượng
def save_webp(im, path, limit):
    """Lưu webp, hạ quality (80 -> 50), vẫn quá thì thu nhỏ 10%/lần. Trả (w, h, bytes)."""
    cur = im
    for _ in range(6):
        for q in (80, 74, 68, 62, 56, 50):
            buf = io.BytesIO()
            cur.save(buf, "WEBP", quality=q, method=6)
            if buf.tell() <= limit:
                path.write_bytes(buf.getvalue())
                return cur.width, cur.height, buf.tell()
        cur = cur.resize((int(cur.width * 0.9), int(cur.height * 0.9)), Image.LANCZOS)
    raise ValueError(f"không nén được {path.name} dưới {limit} byte")


# ---------------------------------------------------------------- banner featured
def autocrop_white(im, pad=0):
    diff = ImageChops.difference(im, Image.new("RGB", im.size, "white")).convert("L").point(lambda v: 255 if v > 14 else 0)
    box = diff.getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def draw_chip_text(d, x, y, text, f, fill, spacing=3):
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + spacing
    return x


def chip_width(text, f, spacing=3):
    return sum(f.getlength(c) + spacing for c in text) - spacing


def draw_chip_shape(canvas, box):
    """Hình chip đơn giản cho bài không có ảnh máy: khối tối, lõi lime, chân chip."""
    d = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    s = 150
    body = (cx - s, cy - s, cx + s, cy + s)
    for i in range(-2, 3):  # chân chip
        o = i * 70
        d.rounded_rectangle((cx + o - 12, body[1] - 46, cx + o + 12, body[1] + 10), 6, fill=COL["pline"])
        d.rounded_rectangle((cx + o - 12, body[3] - 10, cx + o + 12, body[3] + 46), 6, fill=COL["pline"])
        d.rounded_rectangle((body[0] - 46, cy + o - 12, body[0] + 10, cy + o + 12), 6, fill=COL["pline"])
        d.rounded_rectangle((body[2] - 10, cy + o - 12, body[2] + 46, cy + o + 12), 6, fill=COL["pline"])
    d.rounded_rectangle(body, 36, fill=COL["panel"])
    inner = 92
    d.rounded_rectangle((cx - inner, cy - inner, cx + inner, cy + inner), 24, fill=COL["acc"])
    f = font("Bold", 64)
    t = "</>"
    w = f.getlength(t)
    d.text((cx - w / 2, cy - 44), t, font=f, fill=COL["ink"])


def make_featured(name, sub, photo, path):
    W, H = FEAT_W, FEAT_H
    im = Image.new("RGB", (W, H), COL["bg"])
    d = ImageDraw.Draw(im)
    # khung trắng bên phải chứa ảnh máy
    px0, py0, px1, py1 = 616, 56, 1144, 694
    d.rounded_rectangle((px0, py0, px1, py1), 40, fill="white", outline=COL["line"], width=2)
    if photo is not None:
        ph = autocrop_white(photo, pad=6)
        box_w, box_h = (px1 - px0) - 64, (py1 - py0) - 120
        sc = min(box_w / ph.width, box_h / ph.height)
        ph = ph.resize((max(1, int(ph.width * sc)), max(1, int(ph.height * sc))), Image.LANCZOS)
        ox = px0 + ((px1 - px0) - ph.width) // 2
        oy = py0 + ((py1 - py0) - ph.height) // 2 - 8
        sh = Image.new("L", (W, H), 0)  # bóng mềm dưới máy
        ImageDraw.Draw(sh).ellipse((ox + ph.width * 0.08, oy + ph.height - 10, ox + ph.width * 0.92, oy + ph.height + 22), fill=70)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        im.paste(Image.new("RGB", (W, H), COL["ink"]), mask=sh.point(lambda v: int(v * 0.35)))
        # ảnh nền trắng đặt lên khung trắng: không lộ viền
        im.paste(ph, (ox, oy))
    else:
        draw_chip_shape(im, (px0, py0, px1, py1))
    d = ImageDraw.Draw(im)

    # cột chữ bên trái
    tx, tw = 64, 616 - 64 - 40
    f_chip = font("Bold", 22)
    chip_h = 46
    cw = chip_width(CHIP_TEXT, f_chip) + 40
    f_sub = font("Medium", 30)
    sub_lines = wrap(sub, f_sub, tw)[:3] if sub else []
    sub_lh = 42
    avail = H - 2 * 84 - chip_h - 28 - (len(sub_lines) * sub_lh + 26 if sub_lines else 0)
    size = 68
    while True:
        f_name = font("Bold", size)
        name_lines = wrap(name, f_name, tw)
        lh = int(size * 1.18)
        fits = all(f_name.getlength(l) <= tw for l in name_lines) and len(name_lines) <= 4 and len(name_lines) * lh <= avail
        if fits or size <= 34:
            break
        size -= 2
    total = chip_h + 28 + len(name_lines) * lh + (26 + len(sub_lines) * sub_lh if sub_lines else 0)
    y = (H - total) // 2
    d.rounded_rectangle((tx, y, tx + cw, y + chip_h), chip_h // 2, fill=COL["acc"])
    draw_chip_text(d, tx + 20, y + 8, CHIP_TEXT, f_chip, COL["ink"])
    y += chip_h + 28
    for l in name_lines:
        d.text((tx, y), l, font=f_name, fill=COL["ink"])
        y += lh
    if sub_lines:
        y += 26
        for l in sub_lines:
            d.text((tx, y), l, font=f_sub, fill=COL["mut"])
            y += sub_lh
    return im


# ---------------------------------------------------------------- infographic bảng cấu hình
def parse_table(art):
    m = re.search(r"<table.*?</table>", art, re.S)
    if not m:
        return None
    t = m.group(0)
    th = [strip_tags(x) for x in re.findall(r"<th[^>]*>(.*?)</th>", t, re.S)]
    tb = re.search(r"<tbody>(.*?)</tbody>", t, re.S)
    rows = []
    for r in re.findall(r"<tr>(.*?)</tr>", tb.group(1) if tb else "", re.S):
        cells = [strip_tags(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if cells:
            rows.append(cells)
    if not th or not rows:
        return None
    n = len(th)
    rows = [(r + [""] * n)[:n] for r in rows]
    return th, rows


def col_widths(cols, f_head, f_body, total, pad):
    """Chia bề rộng cột: vừa nội dung một dòng nếu đủ chỗ, không thì co dần tới từ dài nhất."""
    nat, mn = [], []
    for j, c in enumerate(cols):
        nat.append(max(f.getlength(t) for f, t in c) + 2 * pad)
        mn.append(max(f.getlength(w) for f, t in c for w in t.split() or [""]) + 2 * pad)
    if sum(nat) <= total:
        extra = (total - sum(nat)) / len(nat)
        return [w + extra for w in nat]
    spare = total - sum(mn)
    room = [n - m for n, m in zip(nat, mn)]
    rs = sum(room) or 1
    return [m + spare * r / rs for m, r in zip(mn, room)]


def make_table_image(name, head, rows, path):
    W, M, PAD = 1200, 48, 16
    f_h, f_b, f_t = font("Bold", 24), font("Regular", 24), font("Bold", 40)
    f_foot = font("Regular", 24)
    title = f"Các cấu hình {name} đang bán"
    t_lines = wrap(title, f_t, W - 2 * M)
    tw = W - 2 * M
    cols = [[(f_h, head[j])] + [(f_b, r[j]) for r in rows] for j in range(len(head))]
    cw = col_widths(cols, f_h, f_b, tw, PAD)
    cw = [int(w) for w in cw]
    cw[-1] += tw - sum(cw)
    LH = 33

    def cell_lines(f, t, w):
        return wrap(t, f, w - 2 * PAD)

    head_lines = [cell_lines(f_h, head[j], cw[j]) for j in range(len(head))]
    head_h = max(len(x) for x in head_lines) * LH + 28
    row_lines = [[cell_lines(f_b, r[j], cw[j]) for j in range(len(head))] for r in rows]
    row_h = [max(len(x) for x in rl) * LH + 28 for rl in row_lines]
    top = M + len(t_lines) * 52 + 28
    H = top + head_h + sum(row_h) + 28 + 36 + M - 8
    im = Image.new("RGB", (W, H), COL["bg"])
    d = ImageDraw.Draw(im)
    y = M
    for l in t_lines:
        d.text((M, y), l, font=f_t, fill=COL["ink"])
        y += 52
    y = top
    d.rounded_rectangle((M, y, M + tw, y + head_h + sum(row_h)), 18, fill="white", outline=COL["line"], width=2)
    # hàng tiêu đề (bo góc trên)
    d.rounded_rectangle((M, y, M + tw, y + head_h + 20), 18, fill=COL["ink"])
    d.rectangle((M, y + head_h, M + tw, y + head_h + 20), fill="white")
    x = M
    for j, lines in enumerate(head_lines):
        for k, l in enumerate(lines):
            d.text((x + PAD, y + 14 + k * LH), l, font=f_h, fill="white")
        x += cw[j]
    y += head_h
    for i, rl in enumerate(row_lines):
        if i % 2 == 1:
            d.rectangle((M + 3, y, M + tw - 3, y + row_h[i] - (4 if i == len(rows) - 1 else 0)), fill="#F7F8F4")
        x = M
        for j, lines in enumerate(rl):
            for k, l in enumerate(lines):
                d.text((x + PAD, y + 14 + k * LH), l, font=f_h if j == 0 else f_b, fill=COL["ink"])
            x += cw[j]
        if i < len(rows) - 1:
            d.line((M + 2, y + row_h[i], M + tw - 2, y + row_h[i]), fill=COL["line"], width=2)
        y += row_h[i]
    d.rounded_rectangle((M, y + 28, M + 8, y + 28 + 24), 4, fill=COL["acc"])
    d.text((M + 20, y + 24), "laptopnotesvn.github.io", font=f_foot, fill=COL["mut"])
    return save_webp(im, path, FIG_LIMIT)


def h2_before_table(art):
    t = art.find("<table")
    if t < 0:
        return None
    n = len(re.findall(r"<h2[\s>]", art[:t]))
    return n or None


# ---------------------------------------------------------------- chạy từng bài
def webp_size(path):
    with Image.open(path) as im:
        return im.width, im.height


def process(slug, force, manifest):
    """Trả (đã_tạo, bỏ_qua, ghi_chú). Ném lỗi nếu mạng/ảnh hỏng (bài đó bị bỏ qua)."""
    a = read_article(slug)
    out = POSTS_DIR / slug
    name, sub = title_parts(a["title"])
    table = parse_table(a["art"])
    if force:
        for fn in FILES:
            (out / fn).unlink(missing_ok=True)
    made, skipped, notes = 0, 0, []
    need_net = a["product"] and any(not (out / fn).exists() for fn in ("featured.webp", "hinh-1.webp", "hinh-3.webp"))
    info = None
    if need_net:
        info = product_images(a["product"])
        time.sleep(PAUSE)

    # featured
    if (out / "featured.webp").exists():
        skipped += 1
    else:
        photo = None
        if a["product"]:
            url = info["main"] or info["feat"].get(1)
            if not url:
                raise ValueError("SP không có ảnh chính")
            photo = load_img(url)
        make_name = name if a["product"] else nfc(a["title"].partition(" - ")[0].strip())
        im = make_featured(make_name, sub, photo, out / "featured.webp")
        save_webp(im, out / "featured.webp", FEAT_LIMIT)
        made += 1

    # hinh-1 (Features-01 hoặc ảnh chính) và hinh-3 (Features-02)
    for fn, key, fallback in (("hinh-1.webp", 1, True), ("hinh-3.webp", 2, False)):
        if (out / fn).exists():
            skipped += 1
            continue
        if not a["product"]:
            continue
        url = info["feat"].get(key) or (info["main"] if fallback else None)
        if not url:
            notes.append(f"thiếu Features-0{key}")
            continue
        if fallback and key not in info["feat"]:
            notes.append("hinh-1 dùng ảnh chính (không có Features-01)")
        im = load_img(url)
        if im.width > FIG1_W:
            im = im.resize((FIG1_W, round(im.height * FIG1_W / im.width)), Image.LANCZOS)
        save_webp(im, out / fn, FIG_LIMIT)
        made += 1

    # hinh-2 từ bảng
    if table:
        if (out / "hinh-2.webp").exists():
            skipped += 1
        else:
            make_table_image(name, table[0], table[1], out / "hinh-2.webp")
            made += 1
    else:
        notes.append("không có bảng -> bỏ hinh-2")

    # manifest
    entry = {}
    if (out / "featured.webp").exists():
        w, h = webp_size(out / "featured.webp")
        alt = (f"Ảnh đại diện bài viết về {name} cho lập trình" if a["product"]
               else f"Ảnh đại diện bài viết: {name}")
        entry["featured"] = {"file": "featured.webp", "alt": alt, "w": w, "h": h}
    figs = []
    if (out / "hinh-1.webp").exists():
        w, h = webp_size(out / "hinh-1.webp")
        figs.append({"file": "hinh-1.webp", "alt": f"{name} trong ảnh giới thiệu sản phẩm",
                     "caption": f"{name} trong ảnh giới thiệu sản phẩm.", "after_h2": 1, "w": w, "h": h})
    if (out / "hinh-3.webp").exists():
        w, h = webp_size(out / "hinh-3.webp")
        figs.append({"file": "hinh-3.webp", "alt": f"Góc nhìn khác của {name} trong ảnh giới thiệu",
                     "caption": f"Một ảnh giới thiệu khác của {name}.", "after_h2": 2, "w": w, "h": h})
    if table and (out / "hinh-2.webp").exists():
        w, h = webp_size(out / "hinh-2.webp")
        cols = ", ".join(table[0][1:]) if len(table[0]) > 1 else "thông số"
        figs.append({"file": "hinh-2.webp",
                     "alt": f"Bảng tóm tắt các cấu hình {name} đang bán, gồm {cols}",
                     "caption": f"Các cấu hình {name} đang bán, tóm tắt từ bảng trong bài.",
                     "after_h2": h2_before_table(a["art"]) or 1, "w": w, "h": h})
    figs.sort(key=lambda x: (x["after_h2"], x["file"]))
    entry["figures"] = figs
    manifest[slug] = entry
    return made, skipped, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", help="chỉ làm bài có slug này")
    ap.add_argument("--force", action="store_true", help="làm lại cả file đã có")
    args = ap.parse_args()

    slugs = sorted(p.parent.name for p in POSTS_DIR.glob("*/index.html"))
    if args.only:
        if args.only not in slugs:
            print(f"không có bài {args.only}", file=sys.stderr)
            return 1
        slugs = [args.only]
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        manifest = {}
    ok = made = skipped = 0
    errs = []
    for slug in slugs:
        try:
            m, s, notes = process(slug, args.force, manifest)
            ok += 1
            made += m
            skipped += s
            for n in notes:
                print(f"  ghi chú {slug}: {n}")
        except Exception as e:  # noqa: BLE001 - lỗi 1 bài không dừng cả lượt
            errs.append((slug, f"{type(e).__name__}: {e}"))
            print(f"  LỖI {slug}: {type(e).__name__}: {e}", file=sys.stderr)
    for slug in list(manifest):
        if not (POSTS_DIR / slug).is_dir():
            del manifest[slug]
    text = json.dumps({k: manifest[k] for k in sorted(manifest)}, ensure_ascii=False, indent=2) + "\n"
    old = MANIFEST.read_text(encoding="utf-8") if MANIFEST.exists() else None
    if old != text:
        MANIFEST.write_text(text, encoding="utf-8")
    print(f"make_images: {ok}/{len(slugs)} bài xong, {made} ảnh mới, {skipped} ảnh đã có, {len(errs)} lỗi")
    return 1 if errs and ok == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
