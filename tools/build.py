#!/usr/bin/env python3
"""Dựng index.html + style.css + khung bài viết cho trang vệ tinh Laptop Lập Trình.

Giá/kho/ảnh lấy từ WooCommerce Store API của hungphatlaptop.com (stdlib thuần).
Xem tools/README.md. Mã thoát: 0 = ok, 1 = lỗi dữ liệu/tệp, 2 = quá nửa sản phẩm lỗi.
"""
import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
PRODUCTS_JSON = TOOLS / "products.json"
STATE_JSON = TOOLS / "state.json"
INDEX_HTML = ROOT / "index.html"
STYLE_CSS = ROOT / "style.css"
SITEMAP = ROOT / "sitemap.xml"
POSTS_DIR = ROOT / "bai-viet"

SITE_URL = "https://laptopnotesvn.github.io/"
API = "https://hungphatlaptop.com/wp-json/wc/store/v1/products?slug="
UA = "Mozilla/5.0 (compatible; PriceSync/1.0)"
TIMEOUT = 20
PAUSE = 1.0
MIN_PRICE = 1_000_000  # dưới mức này coi là dữ liệu hỏng (laptop không thể rẻ vậy)
MAX_PRICE = 300_000_000  # trên mức này coi là dữ liệu hỏng
IMG_HOST = "https://static.hungphatlaptop.com/"  # chỉ nhận ảnh từ host này
VN = timezone(timedelta(hours=7))

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&amp;family=JetBrains+Mono:wght@500&amp;family=Space+Grotesk:wght@500;600;700&amp;display=swap" rel="stylesheet">'
)

# ---------------------------------------------------------------- icon SVG
def _svg(inner, size, sw="2.2"):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{inner}</svg>')

def ic_upright(s=16): return _svg('<path d="M7 17 17 7"></path><path d="M8 7h9v9"></path>', s)
def ic_right(s=16): return _svg('<path d="M5 12h14"></path><path d="m13 6 6 6-6 6"></path>', s)
def ic_down(s=18): return _svg('<path d="M12 5v14"></path><path d="m6 13 6 6 6-6"></path>', s, "2.4")
def ic_refresh(s=15): return _svg('<path d="M21 12a9 9 0 1 1-3-6.7"></path><path d="M21 4v5h-5"></path>', s, "2")
def ic_code(s=20): return _svg('<polyline points="8 6 2 12 8 18"></polyline><polyline points="16 6 22 12 16 18"></polyline>', s, "2.4")
def ic_check(s=14): return _svg('<polyline points="20 6 9 17 4 12"></polyline>', s, "2.6")

def esc(s):
    return html.escape(str(s), quote=True)

def price_ok(d):
    return bool(d) and isinstance(d.get("price"), int) and MIN_PRICE <= d["price"] <= MAX_PRICE

def fmt_vnd(n):
    return f"{int(n):,}".replace(",", ".") + "₫"

# ---------------------------------------------------------------- bài viết (quét bai-viet/*/index.html)
# Mô tả thẻ bài trên trang chủ của bài cũ (bài mới lấy từ meta description).
LEGACY_CARD_DESC = {
    "lap-trinh-vien-can-bao-nhieu-ram": "Đọc trước khi chọn máy: RAM bao nhiêu là đủ cho kiểu việc của bạn.",
}
_DATE_RE = re.compile(r"Đăng ngày (\d{2})/(\d{2})/(\d{4})")

def scan_posts():
    """Trả danh sách bài, mới nhất trước (cùng ngày thì theo slug). Mỗi bài: dict slug/path/title/desc/iso/src."""
    posts = []
    if not POSTS_DIR.is_dir():
        return posts
    for f in sorted(POSTS_DIR.glob("*/index.html")):
        src = f.read_text(encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", src, re.S)
        title = html.unescape(m.group(1)).strip() if m else f.parent.name
        m = re.search(r'<meta name="description" content="([^"]*)"', src)
        desc = html.unescape(m.group(1)).strip() if m else ""
        m = _DATE_RE.search(src)
        iso = f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""
        slug = f.parent.name
        if slug in LEGACY_CARD_DESC:
            desc = LEGACY_CARD_DESC[slug]
        elif len(desc) > 150:
            desc = desc[:150].rsplit(" ", 1)[0].rstrip(",.;: -") + "..."
        posts.append({"slug": slug, "path": f, "title": title, "desc": desc, "iso": iso, "src": src})
    posts.sort(key=lambda x: (x["iso"], x["slug"]), reverse=True)
    return posts

def post_card(p, kicker):
    href = f'bai-viet/{p["slug"]}/'
    return f'''<a class="post-card" href="{href}">
<div class="post-card-in">
<h2 class="mono kicker">{kicker}</h2>
<span class="hd post-t">{esc(p["title"])}</span>
<span class="post-d">{esc(p["desc"])}</span>
</div>
<span class="post-go">Đọc bài{ic_right(18)}</span>
</a>'''

def posts_section(posts):
    cta = f'''<div class="cta-box">
<div class="cta-in">
<span class="mono cta-k">HƯNG PHÁT LAPTOP · TP.HCM</span>
<h2 class="hd h2">Cần xem đủ cấu hình và giá mới nhất?</h2>
<p>Mọi mẫu trên trang đều dẫn về web Hưng Phát Laptop, nơi có thông số chi tiết, các bản cấu hình và giá đang bán.</p>
</div>
<div class="cta-row">
<a class="btn btn-lg btn-dark" href="https://hungphatlaptop.com/">Vào hungphatlaptop.com{ic_upright(18)}</a>
</div>
</div>'''
    first = post_card(posts[0], "Bài viết mới") if posts else ""
    rows = [f'<div class="duo">\n{first}\n{cta}\n</div>' if posts else f'<div class="duo">\n{cta}\n</div>']
    rest = posts[1:]
    for i in range(0, len(rest), 2):
        rows.append('<div class="duo">\n' + "\n".join(post_card(p, "Bài viết") for p in rest[i:i + 2]) + "\n</div>")
    return '<section id="bai-viet" class="wrap post-sec">\n' + "\n".join(rows) + "\n</section>"

# ---------------------------------------------------------------- dữ liệu
def load_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def now_vn():
    return datetime.now(VN)

def fetch_product(slug):
    """Trả (dict dữ liệu | None, thông báo lỗi)."""
    url = API + urllib.parse.quote(slug)
    last_err = "không rõ"
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                items = json.loads(r.read().decode("utf-8"))
            return parse_item(items, slug)
        except Exception as e:  # mạng, JSON, HTTP...
            last_err = f"{type(e).__name__}: {e}"
            if attempt == 0:
                time.sleep(2)
    return None, last_err

def parse_item(items, slug):
    if not isinstance(items, list):
        return None, "API không trả danh sách"
    cands = [x for x in items if isinstance(x, dict) and x.get("slug") == slug]
    if not cands:
        return None, "API không có sản phẩm khớp slug"
    # slug có thể trả cả sản phẩm cha (variable) lẫn biến thể: ưu tiên sản phẩm cha (giá thấp nhất)
    cands.sort(key=lambda x: 0 if (x.get("type") != "variation" and not x.get("parent")) else 1)
    it = cands[0]
    pr = it.get("prices") or {}
    try:
        minor = int(pr.get("currency_minor_unit", 0))
        price = int(pr["price"]) // (10 ** minor)
        regular = int(pr.get("regular_price") or pr["price"]) // (10 ** minor)
    except Exception:
        return None, "thiếu/sai prices.price"
    if price <= 0 or price < MIN_PRICE or price > MAX_PRICE:
        return None, f"giá bất thường ({price})"
    if regular < price or regular > MAX_PRICE:
        regular = price
    out = {"price": price, "regular": regular, "in_stock": it.get("is_in_stock") is True}
    imgs = it.get("images") or []
    if imgs and isinstance(imgs[0], dict):
        src = str(imgs[0].get("src") or "")
        if src.startswith(IMG_HOST):
            out["img"] = src
            out["alt"] = html.unescape(str(imgs[0].get("alt") or ""))
            srcset = str(imgs[0].get("srcset") or "")
            if srcset and all(c.strip().startswith(IMG_HOST) for c in srcset.split(",")):
                out["srcset"] = srcset
    return out, ""

def merge(old, new):
    """Giá trị mới hợp lệ thì dùng; ảnh thiếu thì giữ ảnh cũ."""
    m = dict(new)
    if old and "img" not in new:
        for k in ("img", "alt", "srcset"):
            if k in old:
                m[k] = old[k]
    elif "img" in new:
        m.setdefault("alt", "")
    return m

def diff_text(slug, old, new):
    if old is None:
        return f"{slug}: mới (giá {fmt_vnd(new['price'])})"
    parts = []
    if old.get("price") != new.get("price"):
        parts.append(f"giá {fmt_vnd(old['price'])} -> {fmt_vnd(new['price'])}")
    if old.get("regular") != new.get("regular"):
        parts.append(f"giá gốc {fmt_vnd(old['regular'])} -> {fmt_vnd(new['regular'])}")
    if old.get("in_stock") != new.get("in_stock"):
        parts.append(f"kho {'còn' if old.get('in_stock') else 'hết'} -> {'còn' if new.get('in_stock') else 'hết'}")
    if old.get("img") != new.get("img") or old.get("srcset") != new.get("srcset") or old.get("alt") != new.get("alt"):
        parts.append("ảnh đổi")
    return f"{slug}: " + ", ".join(parts)

# ---------------------------------------------------------------- HTML
def header(prefix):
    home = prefix or "./"
    return f'''<header class="site-hd">
<div class="wrap hd-row">
<a class="logo" href="{home}"><span class="logo-mark">{ic_code(20)}</span><span class="hd logo-text">Laptop Lập Trình</span></a>
<nav class="navlinks" aria-label="Điều hướng chính">
<a href="{prefix}#nhu-cau">Theo nhu cầu</a>
<a href="{prefix}#dong-may">Dòng máy</a>
<a href="{prefix}#bai-viet">Bài viết</a>
</nav>
<a class="btn btn-white" href="https://hungphatlaptop.com/">Hưng Phát<span class="hide-sm">&nbsp;Laptop</span>{ic_upright(16)}</a>
</div>
</header>'''

def footer(prefix, updated=None):
    stamp = (f'\n<span class="mono foot-note">Giá lấy tự động từ hungphatlaptop.com · cập nhật {esc(updated)}</span>'
             if updated else "")
    return f'''<footer class="site-ft">
<div class="wrap foot">
<div class="foot-l">
<span class="hd foot-brand">Laptop Lập Trình</span>
<span>Ghi chú chọn máy cho người viết code. Máy được giới thiệu đang bán tại Hưng Phát Laptop, TP.HCM.</span>{stamp}
</div>
<nav class="foot-nav" aria-label="Liên kết cuối trang">
<a href="{prefix}#nhu-cau">Theo nhu cầu</a>
<a href="{prefix}#dong-may">Dòng máy</a>
<a href="{prefix}#bai-viet">Bài viết</a>
<a href="https://hungphatlaptop.com/">Hưng Phát Laptop</a>
</nav>
</div>
</footer>'''

def img_html(name, d, hero=False):
    if not d or not d.get("img"):
        return f'<span class="noimg" role="img" aria-label="{esc(name)}"></span>'
    alt = html.unescape(d.get("alt") or "")
    if not alt or len(alt) > 140:
        alt = name
    attrs = f'src="{esc(d["img"])}" '
    if d.get("srcset"):
        sizes = ("(max-width: 900px) 90vw, 520px" if hero
                 else "(max-width: 560px) 90vw, (max-width: 900px) 45vw, (max-width: 1180px) 30vw, 280px")
        attrs += f'srcset="{esc(d["srcset"])}" sizes="{sizes}" '
    attrs += f'alt="{esc(alt)}" width="800" height="600" '
    attrs += 'fetchpriority="high" decoding="async"' if hero else 'loading="lazy" decoding="async"'
    return f"<img {attrs}>"

def card(p, d, base):
    url = base + p["slug"] + "/"
    name = esc(p["name"])
    if d["in_stock"]:
        stock = '<span class="stock ok"><i></i>Còn hàng</span>'
    else:
        stock = '<span class="stock no"><i></i>Hết hàng - liên hệ</span>'
    if price_ok(d):
        reg = (f'\n<span class="reg">{fmt_vnd(d["regular"])}</span>'
               if MIN_PRICE <= d["regular"] <= MAX_PRICE and d["regular"] > d["price"] else "")
        pricebox = f'''<span class="pl">Giá từ</span>
<span class="hd price">{fmt_vnd(d["price"])}</span>{reg}'''
    else:
        pricebox = '<span class="pl">Liên hệ để biết giá</span>'
    return f'''<article class="card">
<div class="card-img" aria-hidden="true">{img_html(p["name"], d)}</div>
<div class="card-body">
<div class="card-top"><span class="mono brand">{esc(p["brand"])}</span>{stock}</div>
<h3 class="hd"><a href="{url}"><strong>{name}</strong></a></h3>
<p class="blurb">{esc(p["blurb"])}</p>
<div class="card-foot">
<div class="pricebox">
{pricebox}
</div>
<span class="btn go" aria-hidden="true">{ic_upright(20)}</span>
</div>
</div>
</article>'''

def render_index(cfg, prods, updated, posts):
    base = cfg["base"]
    groups = cfg["groups"]
    by_group = {g["id"]: [p for p in cfg["products"] if p["group"] == g["id"]] for g in groups}
    valid = [prods[p["slug"]] for p in cfg["products"] if price_ok(prods[p["slug"]])]
    stocked = [d["price"] for d in valid if d["in_stock"]]
    min_price = min(stocked) if stocked else (min(d["price"] for d in valid) if valid else None)
    hero_p = cfg["products"][0]
    hero_d = prods[hero_p["slug"]]
    u = esc(updated)

    needs = "\n".join(
        f'''<a class="need" href="#{g["id"]}">
<span class="mono need-num">{g["num"]}</span>
<span class="need-txt"><span class="hd need-t">{esc(g["short"])}</span><span class="need-c">{len(by_group[g["id"]])} mẫu máy</span></span>
{ic_right(20)}
</a>''' for g in groups)

    sections = []
    for g in groups:
        cards = "\n".join(card(p, prods[p["slug"]], base) for p in by_group[g["id"]])
        sections.append(f'''<section id="{g["id"]}" class="wrap sec-pad">
<div class="sec-head">
<div class="sec-title">
<span class="mono kicker">{g["num"]} / {esc(g["tag"])}</span>
<h2 class="hd h2">{esc(g["title"])}</h2>
<p class="sec-desc">{esc(g["desc"])}</p>
</div>
<span class="pill">{ic_refresh(15)}Giá cập nhật tự động {u}</span>
</div>
<div class="{g["grid"]}">
{cards}
</div>
</section>''')

    series = "\n".join(f'''<div class="series">
<span class="mono s-brand">{esc(s["brand"])}</span>
<h3 class="hd s-name"><a href="{base}{s["slug"]}/"><strong>{esc(s["name"])}</strong></a></h3>
<span class="s-desc">{esc(s["desc"])}</span>
<span class="s-more">Xem dòng máy{ic_right(16)}</span>
</div>''' for s in cfg["series"])

    title = "Laptop cho lập trình viên - Chọn máy nào để code mượt?"
    desc = ("Gợi ý laptop cho lập trình viên theo nhu cầu: máy gọn nhẹ để code hằng ngày, máy tầm trung dễ mua "
            "và máy trạm chạy Docker, máy ảo, AI. Các mẫu đang có tại Hưng Phát Laptop.")
    intro = ("Lập trình không cần máy quá mạnh, nhưng cần máy ổn định, bàn phím gõ sướng, màn hình dễ nhìn lâu "
             "và đủ RAM để mở cùng lúc trình soạn code, trình duyệt, Docker hay máy ảo. Trang này gom các mẫu "
             "laptop đang bán tại Hưng Phát Laptop, chia theo nhu cầu thật của người viết code.")
    checks = "\n".join(f'<div><span class="chk">{ic_check(14)}</span> {t}</div>' for t in (
        "RAM đủ cho IDE, trình duyệt, Docker", "Bàn phím gõ lâu không mỏi",
        "Màn hình dễ nhìn cả ngày", "Pin đủ một buổi làm việc"))

    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE_URL}">
{FONTS}
<link rel="stylesheet" href="style.css">
</head>
<body>
<a class="skip" href="#main">Bỏ qua đến nội dung</a>
{header("")}
<main id="main">
<section class="hero">
<div class="wrap hero-pad">
<div class="hero-grid">
<div class="hero-l">
<span class="mono hero-tag">// ghi chú chọn máy cho người viết code</span>
<h1 class="hd h1">Laptop cho lập trình viên - Chọn máy nào để <span class="acc">code mượt?</span></h1>
<p class="lead">{esc(intro)}</p>
<p class="note">Giá lấy tự động từ hungphatlaptop.com, cập nhật {u}. Giá có thể thay đổi theo cấu hình và thời điểm.</p>
<div class="cta-row">
<a class="btn btn-lg btn-acc" href="#nhu-cau">Xem máy theo nhu cầu{ic_down(18)}</a>
<a class="btn btn-lg btn-ghost" href="https://hungphatlaptop.com/">Vào web Hưng Phát</a>
</div>
</div>
<div class="hero-vis">
<div class="hero-card">
{f'<span class="hd badge">Máy từ {fmt_vnd(min_price)}</span>' if min_price else ""}
{img_html(hero_p["name"], hero_d, hero=True)}
</div>
<div class="term mono">
<div class="term-bar"><span class="d r"></span><span class="d y"></span><span class="d g"></span><span class="term-name">chon-may.sh</span></div>
<div><span class="acc">$</span> kiem-tra --may-code</div>
{checks}
</div>
</div>
</div>
<nav id="nhu-cau" class="needs" aria-label="Chọn theo nhu cầu">
{needs}
</nav>
</div>
</section>

{chr(10).join(sections)}

<section id="dong-may" class="dark-sec">
<div class="wrap sec-pad dm-pad">
<div class="sec-head">
<div class="sec-title">
<span class="mono kicker acc">04 / DÒNG MÁY</span>
<h2 class="hd h2">Xem theo dòng máy</h2>
</div>
<p class="dm-desc">Mỗi dòng có nhiều cấu hình hơn những mẫu ở trên. Bấm vào để xem đủ máy đang bán.</p>
</div>
<div class="grid5">
{series}
</div>
</div>
</section>

{posts_section(posts)}
</main>
{footer("", updated)}
</body>
</html>
'''

def render_article(src):
    """Chỉ đổi khung (head link, header, footer, class body); giữ nguyên title/meta/canonical/nội dung."""
    s = src
    if "fonts.googleapis.com" not in s:
        s = s.replace('<link rel="stylesheet" href="../../style.css">',
                      FONTS + '\n<link rel="stylesheet" href="../../style.css">')
    if '<body class="page-post">' not in s:
        s = s.replace("<body>", '<body class="page-post">\n<a class="skip" href="#main">Bỏ qua đến nội dung</a>', 1)
    s = re.sub(r"<header\b.*?</header>", lambda m: header("../../"), s, count=1, flags=re.S)
    s = re.sub(r"<footer\b.*?</footer>", lambda m: footer("../../"), s, count=1, flags=re.S)
    if '<main id="main">' not in s:
        s = s.replace("<main>", '<main id="main">', 1)
    return s

# ---------------------------------------------------------------- CSS
CSS = r''':root{--ink:#0B1020;--bg:#F4F5F0;--acc:#C6F36B;--mut:#4B5563;--line:#E2E5DA;--lt:#C9D1E0;--dim:#A9B4C8;--panel:#10182C;--pline:#26304A}
*,*::before,*::after{box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg);line-height:1.5}
img{max-width:100%}
a{color:inherit}
a:focus-visible,.btn:focus-visible{outline:3px solid #5B7CFA;outline-offset:3px;border-radius:6px}
.skip{position:absolute;left:-9999px;top:8px;background:#fff;color:var(--ink);padding:12px 16px;border-radius:8px;z-index:10}
.skip:focus{left:8px}
.hd{font-family:'Space Grotesk',Inter,system-ui,sans-serif;letter-spacing:-0.02em}
.mono{font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace}
.acc{color:var(--acc)}
.wrap{max-width:none;margin:0 auto;padding-left:clamp(16px,4vw,64px);padding-right:clamp(16px,4vw,64px)}
.btn{display:inline-flex;align-items:center;gap:8px;text-decoration:none;transition:filter .2s}
.btn:hover{filter:brightness(1.08)}
.btn-white{min-height:44px;padding:0 18px;border-radius:12px;background:#fff;color:var(--ink);font-weight:600;font-size:14px}
.btn-lg{gap:10px;min-height:52px;padding:0 24px;border-radius:14px;font-weight:700;font-size:16px}
.btn-acc{background:var(--acc);color:var(--ink)}
.btn-ghost{border:1px solid #36415E;color:#fff;font-weight:600}
.btn-dark{background:var(--ink);color:#fff}

.site-hd{background:var(--ink);border-bottom:1px solid #1E2740}
.hd-row{display:flex;align-items:center;justify-content:space-between;gap:16px;height:76px}
.logo{display:flex;align-items:center;gap:10px;text-decoration:none;color:#fff;min-height:44px}
.logo-mark{width:36px;height:36px;border-radius:10px;background:var(--acc);color:var(--ink);display:inline-flex;align-items:center;justify-content:center}
.logo-text{font-size:19px;font-weight:700}
.navlinks{display:flex;gap:32px;align-items:center;font-size:15px;font-weight:500}
.navlinks a{display:inline-flex;align-items:center;min-height:44px;text-decoration:none;color:var(--lt)}
.navlinks a:hover{color:#fff}

.hero{background:var(--ink);color:#fff}
.hero-pad{padding-top:72px;padding-bottom:88px}
.hero-grid{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr);gap:64px;align-items:center}
.hero-l{display:flex;flex-direction:column;gap:28px}
.hero-tag{font-size:14px;color:var(--acc)}
.h1{font-size:68px;line-height:1.02;margin:0;font-weight:700}
.lead{font-size:19px;line-height:1.6;margin:0;color:var(--lt);max-width:560px}
.note{margin:-12px 0 0;font-size:14px;line-height:1.6;color:var(--dim);max-width:560px}
.cta-row{display:flex;gap:12px;flex-wrap:wrap}
.hero-vis{position:relative;padding:0 0 56px 40px}
.hero-card{background:#fff;border-radius:28px;padding:28px;position:relative}
.hero-card img,.hero-card .noimg{width:100%;height:auto;aspect-ratio:4/3;object-fit:contain;display:block}
.badge{position:absolute;top:20px;right:20px;background:var(--acc);color:var(--ink);font-weight:700;font-size:15px;padding:8px 14px;border-radius:999px;z-index:1}
.term{position:absolute;left:0;bottom:0;width:360px;background:#121A2E;border:1px solid #2A3553;border-radius:18px;padding:18px 20px;font-size:13px;line-height:1.85;color:var(--lt);box-shadow:0 30px 60px -30px rgba(0,0,0,.8)}
.term-bar{display:flex;align-items:center;gap:6px;margin-bottom:8px}
.term .d{width:10px;height:10px;border-radius:50%}
.term .r{background:#FF6B5E}.term .y{background:#F5C04E}.term .g{background:#5FD068}
.term-name{margin-left:8px;color:#8E9AB3}
.chk{display:inline-flex;vertical-align:-2px;color:var(--acc)}
.noimg{background:#EEF0E8;border-radius:12px}

.needs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-top:64px}
.need{display:flex;align-items:center;gap:16px;padding:20px 22px;min-height:88px;border-radius:18px;border:1px solid var(--pline);background:var(--panel);color:#fff;text-decoration:none;transition:border-color .2s,background .2s}
.need:hover{border-color:var(--acc);background:#141C33}
.need svg{flex:none}
.need-num{font-size:14px;color:var(--acc)}
.need-txt{display:flex;flex-direction:column;gap:4px;flex:1}
.need-t{font-size:18px;font-weight:600}
.need-c{font-size:14px;color:var(--dim)}

.sec-pad{padding-top:96px;padding-bottom:16px}
.sec-head{display:flex;justify-content:space-between;align-items:flex-end;gap:24px;flex-wrap:wrap;margin-bottom:36px}
.sec-title{display:flex;flex-direction:column;gap:14px;max-width:none}
.kicker{font-size:13px;color:var(--mut);letter-spacing:.06em;margin:0;font-weight:500;text-transform:uppercase}
.kicker.acc{color:var(--acc)}
.h2{font-size:44px;line-height:1.08;margin:0;font-weight:700}
.sec-desc{margin:0;font-size:17px;line-height:1.6;color:var(--mut)}
.pill{display:inline-flex;align-items:center;gap:8px;font-size:13px;color:#374151;background:#fff;border:1px solid #DCDFD3;border-radius:999px;padding:8px 14px}
.grid4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:20px}
.grid3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.grid5{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:16px}

.card{position:relative;background:#fff;border:1px solid var(--line);border-radius:22px;overflow:hidden;display:flex;flex-direction:column;transition:transform .2s,box-shadow .2s}
.card:hover{transform:translateY(-4px);box-shadow:0 24px 48px -28px rgba(11,16,32,.45)}
.card-img{display:block;padding:24px 24px 4px;background:#fff}
.card-img img,.card-img .noimg{width:100%;height:auto;aspect-ratio:4/3;object-fit:contain;display:block}
.card-body{padding:16px 22px 22px;display:flex;flex-direction:column;gap:10px;flex:1}
.card-top{display:flex;justify-content:space-between;align-items:center;gap:8px}
.brand{font-size:12px;color:var(--mut);letter-spacing:.06em;text-transform:uppercase}
.stock{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600}
.stock i{width:7px;height:7px;border-radius:50%;display:inline-block}
.stock.ok{color:#1E6B30}.stock.ok i{background:#2E9E47}
.stock.no{color:#9B1C1C}.stock.no i{background:#D14343}
.card h3{margin:0;font-size:19px;line-height:1.28;font-weight:600}
.card h3 strong{font-weight:inherit}
.card h3 a{text-decoration:none}
.card h3 a::after{content:"";position:absolute;inset:0}
.card h3 a:focus-visible{outline:none}
.card h3 a:focus-visible::after{outline:3px solid #5B7CFA;outline-offset:-3px;border-radius:22px}
.card h3 a:hover{text-decoration:underline}
.blurb{margin:0;font-size:14px;line-height:1.6;color:var(--mut);flex:1}
.card-foot{display:flex;align-items:flex-end;justify-content:space-between;gap:12px;padding-top:14px;border-top:1px dashed #D6D9CD}
.pricebox{display:flex;flex-direction:column;gap:2px}
.pl{font-size:12px;color:var(--mut)}
.price{font-size:23px;font-weight:700}
.reg{font-size:13px;color:#6B7280;text-decoration:line-through}
.go{width:46px;height:46px;flex:none;border-radius:14px;background:var(--ink);color:var(--acc);justify-content:center}

.dark-sec{background:var(--ink);color:#fff;margin-top:96px}
.dm-pad{padding-bottom:88px}
.dm-desc{margin:0;font-size:16px;line-height:1.6;color:var(--dim);max-width:420px}
.series{position:relative;display:flex;flex-direction:column;gap:14px;padding:24px;min-height:190px;border-radius:20px;border:1px solid var(--pline);background:var(--panel);color:#fff;transition:border-color .2s}
.series:hover{border-color:var(--acc)}
.s-brand{font-size:12px;color:var(--dim);letter-spacing:.06em}
.s-name{margin:0;font-size:22px;font-weight:700;line-height:1.15}
.s-name a{text-decoration:none}
.s-name a::after{content:"";position:absolute;inset:0;border-radius:20px}
.s-name strong{font-weight:inherit}
.s-desc{font-size:14px;line-height:1.55;color:var(--dim);flex:1}
.s-more{display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:var(--acc)}

.post-sec{padding-top:88px;padding-bottom:96px}
.duo{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:20px}
.duo+.duo{margin-top:20px}
.post-card{display:flex;flex-direction:column;justify-content:space-between;gap:32px;padding:36px;border-radius:26px;background:#fff;border:1px solid var(--line);text-decoration:none}
.post-card-in{display:flex;flex-direction:column;gap:16px}
.post-t{font-size:28px;line-height:1.2;font-weight:700;color:var(--ink)}
.post-d{font-size:16px;line-height:1.6;color:var(--mut)}
.post-go{display:inline-flex;align-items:center;gap:8px;font-weight:600;min-height:44px}
.cta-box{padding:48px;border-radius:26px;background:var(--acc);color:var(--ink);display:flex;flex-direction:column;justify-content:space-between;gap:32px}
.cta-in{display:flex;flex-direction:column;gap:16px}
.cta-in p{margin:0;font-size:17px;line-height:1.6;color:#1F2A12}
.cta-k{font-size:13px;letter-spacing:.06em}

.site-ft{background:var(--ink);color:var(--dim)}
.foot{display:flex;justify-content:space-between;gap:32px;flex-wrap:wrap;padding-top:48px;padding-bottom:48px;font-size:14px;line-height:1.7}
.foot-l{display:flex;flex-direction:column;gap:10px;max-width:560px}
.foot-brand{font-size:18px;font-weight:700;color:#fff}
.foot-note{font-size:12px}
.foot-nav{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
.foot-nav a{display:inline-flex;align-items:center;min-height:44px;color:#fff}

/* trang bài viết */
.page-post main{max-width:none;margin:0 auto;padding:56px clamp(16px,4vw,64px) 80px;font-size:18px;line-height:1.75}
.page-post h1{font-family:'Space Grotesk',Inter,system-ui,sans-serif;letter-spacing:-0.02em;font-size:40px;line-height:1.15;margin:0 0 24px;font-weight:700}
.page-post h2{font-family:'Space Grotesk',Inter,system-ui,sans-serif;letter-spacing:-0.02em;font-size:28px;line-height:1.25;margin:2em 0 .5em;font-weight:700}
.page-post p{margin:0 0 1.1em}
.page-post main a{text-decoration:underline;text-decoration-color:#8FBF2E;text-decoration-thickness:2px;text-underline-offset:3px}
.page-post main a:hover{text-decoration-color:var(--ink)}
.page-post .gia{color:var(--mut);font-size:15px;margin-top:2em}

@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.card,.need,.series,.btn{transition:none}.card:hover{transform:none}}

@media (max-width:1180px){
  .grid4{grid-template-columns:repeat(3,minmax(0,1fr))}
  .grid5{grid-template-columns:repeat(3,minmax(0,1fr))}
  .h1{font-size:58px}
}
@media (max-width:900px){
  .wrap{padding-left:32px;padding-right:32px}
  .page-post main{padding-left:32px;padding-right:32px}
  .navlinks{display:none}
  .hero-pad{padding-top:48px;padding-bottom:64px}
  .hero-grid{grid-template-columns:minmax(0,1fr);gap:48px}
  .h1{font-size:52px}
  .grid4,.grid3,.grid5{grid-template-columns:repeat(2,minmax(0,1fr))}
  .needs{grid-template-columns:minmax(0,1fr);margin-top:48px}
  .duo{grid-template-columns:minmax(0,1fr)}
  .sec-pad{padding-top:72px}
  .h2{font-size:38px}
}
@media (max-width:560px){
  .wrap{padding-left:16px;padding-right:16px}
  .hero-pad{padding-top:32px;padding-bottom:48px}
  .h1{font-size:40px}
  .lead{font-size:17px}
  .logo-text{font-size:17px}
  .hero-vis{padding:0}
  .term{position:static;width:auto;margin:-28px 12px 0}
  .grid4,.grid3,.grid5{grid-template-columns:minmax(0,1fr)}
  .sec-pad{padding-top:56px}
  .sec-head{margin-bottom:24px}
  .h2{font-size:30px}
  .cta-box{padding:32px 24px}
  .post-card{padding:28px 22px}
  .post-t{font-size:24px}
  .hide-sm{display:none}
  .page-post main{padding:36px 16px 56px;font-size:17px}
  .page-post h1{font-size:30px}
  .page-post h2{font-size:23px}
}
'''

# ---------------------------------------------------------------- ghi tệp
def write_if_changed(path, text):
    old = path.read_text(encoding="utf-8") if path.exists() else None
    if old != text:
        path.write_text(text, encoding="utf-8")
        return True
    return False

def update_sitemap(iso_date):
    s = SITEMAP.read_text(encoding="utf-8")
    pat = re.compile(r"(<loc>" + re.escape(SITE_URL) + r"</loc><lastmod>)[^<]*(</lastmod>)")
    if not pat.search(s):
        print("CẢNH BÁO: không thấy mục trang chủ trong sitemap.xml", file=sys.stderr)
        return False
    return write_if_changed(SITEMAP, pat.sub(lambda m: m.group(1) + iso_date + m.group(2), s, count=1))

def sync_sitemap_posts(posts, fallback_iso):
    """Thêm <url> cho bài chưa có trong sitemap.xml; không đụng mục đã có."""
    s = SITEMAP.read_text(encoding="utf-8")
    new = s
    for p in posts:
        loc = f'{SITE_URL}bai-viet/{p["slug"]}/'
        if f"<loc>{loc}</loc>" in new:
            continue
        entry = f'<url><loc>{loc}</loc><lastmod>{p["iso"] or fallback_iso}</lastmod></url>\n'
        new = new.replace("</urlset>", entry + "</urlset>", 1)
    return write_if_changed(SITEMAP, new)

def print_table(cfg, prods):
    for p in cfg["products"]:
        d = prods[p["slug"]]
        print(f"  {p['slug'][:55]:55s} {fmt_vnd(d['price']):>14s}  gốc {fmt_vnd(d['regular']):>14s}  "
              f"{'còn hàng' if d['in_stock'] else 'HẾT HÀNG'}  {'ảnh' if d.get('img') else 'KHÔNG ẢNH'}")

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--offline", action="store_true", help="không gọi mạng, dựng lại từ state.json")
    args = ap.parse_args()

    cfg = load_json(PRODUCTS_JSON)
    if not cfg:
        print("Thiếu tools/products.json", file=sys.stderr)
        return 1
    state = load_json(STATE_JSON, None)
    old_prods = (state or {}).get("products", {})
    slugs = [p["slug"] for p in cfg["products"]]
    changed = False
    changes = []
    data_changed_files = []

    if args.offline:
        if not state or any(s not in old_prods for s in slugs):
            print("--offline cần tools/state.json đủ mọi sản phẩm (chạy online trước)", file=sys.stderr)
            return 1
        prods, updated = old_prods, state["updated"]
    else:
        new_prods, errors = {}, []
        for i, slug in enumerate(slugs):
            if i:
                time.sleep(PAUSE)
            d, err = fetch_product(slug)
            if d is None:
                errors.append((slug, err))
                print(f"  LỖI {slug}: {err}", file=sys.stderr)
            else:
                new_prods[slug] = merge(old_prods.get(slug), d)
        if len(errors) * 2 > len(slugs):
            print(f"{len(errors)}/{len(slugs)} sản phẩm lỗi (quá nửa) - KHÔNG ghi file.", file=sys.stderr)
            return 2
        prods = {}
        for slug in slugs:
            cur = new_prods.get(slug) or old_prods.get(slug)
            if cur is None:
                print(f"{slug} lỗi và chưa có dữ liệu cũ - KHÔNG ghi file.", file=sys.stderr)
                return 2
            prods[slug] = cur
        for slug in slugs:
            if old_prods.get(slug) != prods[slug]:
                changes.append(diff_text(slug, old_prods.get(slug), prods[slug]))
        changed = bool(changes) or not state
        now = now_vn()
        updated = now.strftime("%d/%m/%Y") if changed else state["updated"]
        if changed:
            new_state = {"updated": updated, "products": {s: prods[s] for s in slugs}}
            if write_if_changed(STATE_JSON, json.dumps(new_state, ensure_ascii=False, indent=2) + "\n"):
                data_changed_files.append("tools/state.json")
            if update_sitemap(now.strftime("%Y-%m-%d")):
                data_changed_files.append("sitemap.xml")

    posts = scan_posts()
    wrote = []
    if write_if_changed(INDEX_HTML, render_index(cfg, prods, updated, posts)):
        wrote.append("index.html")
    if write_if_changed(STYLE_CSS, CSS):
        wrote.append("style.css")
    for p in posts:
        if write_if_changed(p["path"], render_article(p["src"])):
            wrote.append(f'bai-viet/{p["slug"]}/index.html')
    if SITEMAP.exists() and sync_sitemap_posts(posts, now_vn().strftime("%Y-%m-%d")):
        wrote.append("sitemap.xml")
    if data_changed_files:
        wrote += [f for f in data_changed_files if f not in wrote]
    changed = changed or bool(wrote)

    print_table(cfg, prods)
    if args.offline:
        print(f"OFFLINE (cập nhật {updated}) - " + ("ĐÃ GHI: " + ", ".join(wrote) if wrote else "KHÔNG ĐỔI"))
    elif changed:
        print("CHANGED")
        for c in changes:
            print("  - " + c)
        if wrote:
            print("  - ghi tệp: " + ", ".join(wrote))
        print(f"updated = {updated}")
    else:
        print("UNCHANGED")
    return 0

if __name__ == "__main__":
    sys.exit(main())
