#!/usr/bin/env python3
"""theme.py - giao dien blog ca nhan "Ca Phe Code" cho Laptop Lap Trinh (GitHub Pages).

Cach dung:  python3 tools/theme.py <thu_muc_site>
Chi dung thu vien chuan Python 3.11. Chay lai nhieu lan cho ket qua giong het (chi ghi file khi noi dung doi).

Viec lam:
  1. Ghi style.css (ban cu da luu o tools/_goc/style.css).
  2. Thay phan dau <head> (font, css), header, footer cua moi trang bai-viet/*/index.html.
     Phan <article> giu NGUYEN BYTE; bao no vao layout (cot bai + sidebar).
  3. Dung lai toan bo index.html tu du lieu cac bai (doc bai-viet/*/index.html) va tools/products.json.
     Banner quang cao Hung Phat Laptop do script sinh ra, chi nam o trang chu.

Ngay dang cua bai, thu tu uu tien:
  (1) dong ngay co san trong bai:  <p class="gia">Dang ngay dd/mm/yyyy</p>
  (2) JSON-LD "datePublished"
  (3) mtime cua file (du phong cuoi, doc TRUOC khi script ghi file)
Khoa sap xep (giam dan): (ngay, moc thoi gian JSON-LD, slug). mtime chi dung du phong ngay.

Trang chu giu dung 1 comment <!-- POSTS:START --> ngay dau danh sach "Bai moi nhat".
Cac moc pages_pub dung (giu nguyen): <article ...><h1>..</h1>..</article>, <title>, meta description, link canonical.
Cach goi trong luc dang bai: chay tools/build.py truoc (dung lai ItemList JSON-LD + sitemap), roi theme.py.
"""
import sys, os, re, json, html, zlib, datetime
from pathlib import Path

S = re.S
SITE_NAME = "Laptop Lập Trình"
PEN = "Cà Phê Code"
SHOP = "https://hungphatlaptop.com/"
FONT_HREF = ("https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700"
             "&amp;family=Lora:wght@500;600;700&amp;display=swap")
MARK = "<!-- POSTS:START -->"

# ---------------------------------------------------------------- tiện ích
def rd(p):
    return Path(p).read_text(encoding="utf-8")

def wr(p, s):
    p = Path(p)
    if p.exists() and p.read_bytes() == s.encode("utf-8"):
        return False
    p.parent.mkdir(parents=True, exist_ok=True)
    st = p.stat() if p.exists() else None
    p.write_text(s, encoding="utf-8")
    if st is not None:      # giu mtime cu: mtime la khoa phan ngay khi hai bai cung ngay, khong duoc doi sau moi lan chay
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns))
    return True

def esc(s):
    return html.escape(s, quote=True)

def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

def attr(tag, name):
    m = re.search(r'\b' + name + r'="([^"]*)"', tag)
    return html.unescape(m.group(1)) if m else ""

# ---------------------------------------------------------------- chuyên mục
# Thứ tự: khớp trước thắng. Suy từ slug (chữ thường, gạch nối) hoặc tiêu đề.
CATS = [
    ("so-sanh", "So sánh", "Đặt hai máy cạnh nhau, nói rõ khác ở chỗ nào và ai hợp máy nào."),
    ("danh-gia-may", "Đánh giá máy", "Từng mẫu máy nhìn dưới con mắt người viết code: cân nặng, bàn phím, cổng, tản nhiệt."),
    ("chon-may", "Chọn máy", "Chọn laptop theo công việc cụ thể: web, mobile, Docker, dữ liệu, game, nhúng."),
    ("kien-thuc", "Kiến thức", "RAM, SSD, CPU, pin, tản nhiệt và những thông số nên hiểu trước khi mua."),
]
CAT_NAME = {c[0]: c[1] for c in CATS}

def category(slug, title):
    s = slug.lower()
    t = title.lower()
    if re.search(r"(^|-)vs(-|$)|so-sanh", s) or " vs " in t or "so sánh" in t:
        return "so-sanh"
    if s.endswith("-lap-trinh") and not s.endswith("-cho-lap-trinh"):
        return "danh-gia-may"
    if s.startswith("laptop-") or s.startswith("may-tram-") or "nên chọn" in t or "chọn máy" in t:
        return "chon-may"
    return "kien-thuc"

PH_N = 6
def ph_n(label):
    return zlib.crc32(label.encode("utf-8")) % PH_N

def fmt_date(d):
    return "%02d/%02d/%04d" % (d[2], d[1], d[0])

# ---------------------------------------------------------------- đọc dữ liệu
def read_data(root):
    posts = []
    for f in sorted(root.glob("bai-viet/*/index.html")):
        slug = f.parent.name
        mt = f.stat().st_mtime          # đọc trước khi ghi
        t = rd(f)
        m = re.search(r"<title>(.*?)</title>", t, S)
        title_tag = html.unescape(m.group(1)).strip() if m else slug
        m = re.search(r'<meta name="description" content="([^"]*)"', t)
        desc = html.unescape(m.group(1)).strip() if m else ""
        a0 = t.find("<article")
        a1 = t.rfind("</article>")
        art = t[a0:a1] if a0 >= 0 and a1 > a0 else ""
        m = re.search(r"<h1[^>]*>(.*?)</h1>", art, S)
        h1 = strip_tags(m.group(1)) if m else title_tag
        # ngày: (1) dòng ngày  (2) JSON-LD  (3) mtime
        d = None
        ld_ts = ""
        m = re.search(r'<p class="gia">\s*Đăng ngày (\d{2})/(\d{2})/(\d{4})', t)
        if m:
            d = (int(m.group(3)), int(m.group(2)), int(m.group(1)))
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', t)
        if m:
            ld_ts = m.group(1)
            if d is None:
                mm = re.match(r"(\d{4})-(\d{2})-(\d{2})", ld_ts)
                if mm:
                    d = (int(mm.group(1)), int(mm.group(2)), int(mm.group(3)))
        if d is None:
            x = datetime.datetime.fromtimestamp(mt)
            d = (x.year, x.month, x.day)
        # ảnh featured
        img = None
        m = re.search(r'<figure class="feat">\s*(?:<!--feat-->)?\s*(<img[^>]*>)', art)
        if not m:
            m = re.search(r'<figure class="feat">\s*(<img[^>]*>)', art)
        if m:
            tag = m.group(1)
            src = attr(tag, "src")
            if src and not re.match(r"https?:", src) and (f.parent / src).is_file():
                img = {"src": "bai-viet/%s/%s" % (slug, src), "w": attr(tag, "width") or "1200",
                       "h": attr(tag, "height") or "750", "alt": attr(tag, "alt") or h1}
        posts.append({"slug": slug, "title": h1, "desc": desc, "date": d, "ld": ld_ts, "mt": mt,
                      "img": img, "cat": category(slug, h1)})
    posts.sort(key=lambda p: (p["date"], p["ld"], p["slug"]), reverse=True)   # 10/11: bỏ mtime (git clone + build.py không giữ mtime → thứ tự nhảy)
    prod = {"base": SHOP, "groups": [], "products": [], "series": []}
    p = root / "tools" / "products.json"
    if p.is_file():
        prod = json.loads(rd(p))
    return posts, prod

# ---------------------------------------------------------------- khung chung
NAV = [("bai-viet", "Bài mới"), ("c-so-sanh", "So sánh"), ("c-danh-gia-may", "Đánh giá máy"),
       ("c-chon-may", "Chọn máy"), ("c-kien-thuc", "Kiến thức"), ("may-minh-nhac", "Máy mình nhắc tới")]

def head_block(rel):
    return ("<!-- theme:head -->\n"
            '<meta name="theme-color" content="#faf5ec">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
            '<link href="%s" rel="stylesheet">\n'
            '<link rel="stylesheet" href="%sstyle.css">\n'
            "<!-- /theme:head -->\n" % (FONT_HREF, rel))

def fix_head(t, rel_css):
    m = re.search(r"(<head[^>]*>)(.*?)(</head>)", t, S)
    h = m.group(2)
    h = re.sub(r"<!-- theme:head -->.*?<!-- /theme:head -->\n?", "", h, flags=S)
    h = re.sub(r'<link rel="preconnect"[^>]*>\n?', "", h)
    h = re.sub(r'<link[^>]*href="https://fonts\.googleapis\.com[^>]*>\n?', "", h)
    h = re.sub(r'<link rel="stylesheet"[^>]*>\n?', "", h)
    h = re.sub(r'<meta name="theme-color"[^>]*>\n?', "", h)
    if not h.endswith("\n"):
        h += "\n"
    if "<!--seo-->" in h:
        h = h.replace("<!--seo-->", head_block(rel_css) + "<!--seo-->", 1)
    else:
        h += head_block(rel_css)
    return t[:m.start(2)] + h + t[m.end(2):]

ARROW = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
         'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7"></path>'
         '<path d="M8 7h9v9"></path></svg>')

def header_html(rel, home_href):
    nav = "".join('<a href="%s#%s">%s</a>' % (rel, i, n) for i, n in NAV)
    return ('<a class="skip" href="#main">Bỏ qua tới nội dung</a>\n'
            '<header class="gh-top">\n'
            '<div class="gh-strip gh-wrap"><span>Ghi chú chọn máy cho người viết code</span>'
            '<a class="gh-shop" href="%s">Cửa hàng%s</a></div>\n'
            '<div class="gh-mast gh-wrap"><a class="gh-name" href="%s">%s</a>'
            '<p class="gh-tag">Nhật ký của %s, viết cho người gõ code cả ngày</p></div>\n'
            '<nav class="gh-nav gh-wrap" aria-label="Điều hướng chính">%s</nav>\n</header>\n'
            % (SHOP, ARROW, home_href, esc(SITE_NAME), esc(PEN), nav))

ABOUT = ("Mình ghi lại những gì mình để ý khi chọn laptop để viết code: cân nặng, bàn phím, RAM, cổng và tản nhiệt. "
         "Bài nào cũng đi từ việc cần làm rồi mới tới cấu hình.")

PICKS = ["lap-trinh-vien-can-bao-nhieu-ram", "laptop-cho-nguoi-moi-hoc-code", "laptop-cho-lap-trinh-web-fullstack",
         "cpu-u-h-hx-nao-hop-build-code", "laptop-cho-sinh-vien-cong-nghe-thong-tin", "tan-nhiet-khi-build-lau-tren-laptop"]

def aside_html(rel, posts, link_prefix, show_new):
    counts = {}
    for p in posts:
        counts[p["cat"]] = counts.get(p["cat"], 0) + 1
    chips = "".join('<a class="gh-chip" href="%s#c-%s">%s<small>%d</small></a>' % (rel, k, esc(n), counts.get(k, 0))
                    for k, n, _ in CATS)
    by = {p["slug"]: p for p in posts}
    pick = [by[s] for s in PICKS if s in by][:5]
    if len(pick) < 5:
        pick += [p for p in posts if p not in pick][:5 - len(pick)]
    pl = "".join('<li><a href="%s%s/">%s</a></li>' % (link_prefix, p["slug"], esc(p["title"])) for p in pick)
    new = ""
    if show_new:
        new = ('<section class="gh-w"><h2>Bài mới đăng</h2><ul class="gh-ul">%s</ul></section>\n'
               % "".join('<li><a href="%s%s/">%s</a></li>' % (link_prefix, p["slug"], esc(p["title"])) for p in posts[:5]))
    return ('<aside class="gh-aside" aria-label="Thanh bên">\n'
            '<section class="gh-w gh-about"><h2>Về tác giả</h2>'
            '<div class="gh-au"><span class="gh-av" aria-hidden="true">C</span><b>%s</b></div>'
            '<p>%s</p></section>\n'
            '<section class="gh-w"><h2>Chủ đề</h2><div class="gh-chips">%s</div></section>\n'
            '<section class="gh-w"><h2>Bài nên đọc trước</h2><ol class="gh-ul gh-ol">%s</ol></section>\n%s'
            '</aside>\n' % (esc(PEN), esc(ABOUT), chips, pl, new))

def footer_html(rel):
    return ('<footer class="gh-f"><div class="gh-wrap gh-fin"><div class="gh-fb"><b>%s</b>'
            '<span>Ghi chú chọn máy cho người viết code, do %s viết. Mỗi bài đi từ nhu cầu thật rồi mới tới thông số.</span></div>'
            '<nav aria-label="Liên kết cuối trang"><a href="%s#bai-viet">Bài mới</a>'
            '<a href="%s#may-minh-nhac">Máy mình nhắc tới</a><a href="%s#dong-may">Theo dòng máy</a>'
            '<a href="%s">Cửa hàng</a></nav></div></footer>\n' % (esc(SITE_NAME), esc(PEN), rel, rel, rel, SHOP))

# ---------------------------------------------------------------- các trang con
def reframe_post(f, posts):
    t = rd(f)
    rel = "../../"
    t = fix_head(t, rel)
    b = re.search(r"<body[^>]*>", t)
    a0 = t.index("<article")
    a1 = t.rindex("</article>") + len("</article>")
    article = t[a0:a1]
    ft = t.find("</footer>", a1)
    tail = t[ft + len("</footer>"):].lstrip("\n") if ft >= 0 else "</body>\n</html>\n"
    if not tail.strip():
        tail = "</body>\n</html>\n"
    top = ("\n" + header_html(rel, rel) +
           '<main id="main"><div class="gh-wrap gh-cols"><div class="gh-main"><div class="gh-paper">\n')
    bot = ("\n</div></div>\n" + aside_html(rel, posts, "../", True) + "</div></main>\n" + footer_html(rel))
    out = t[:b.end()] + top + article + bot + tail
    wr(f, out)

# ---------------------------------------------------------------- trang chủ
def ph(item):
    return ('<span class="ph ph%d" aria-hidden="true"><b>%s</b><i>%s</i></span>'
            % (ph_n(item["label"]), esc(item["title"][:1].upper()), esc(item["label"])))

def media(item, hero=False):
    im = item["img"]
    if im:
        extra = 'fetchpriority="high" decoding="async"' if hero else 'loading="lazy" decoding="async"'
        return ('<img src="%s" width="%s" height="%s" alt="%s" %s>'
                % (im["src"], im["w"], im["h"], esc(im["alt"]) if hero else "", extra))
    return ph(item)

def post_item(p):
    return {"href": "bai-viet/%s/" % p["slug"], "label": CAT_NAME[p["cat"]], "title": p["title"],
            "desc": p["desc"], "date": fmt_date(p["date"]), "img": p["img"]}

def row(i):
    return ('<a class="gh-row" href="%s"><span class="gh-rm">%s</span><span class="gh-rb">'
            '<span class="gh-k">%s</span><h3 class="gh-rt">%s</h3><span class="gh-rd">%s</span>'
            '<span class="gh-dt">%s</span></span></a>\n'
            % (i["href"], media(i), esc(i["label"]), esc(i["title"]), esc(i["desc"]), i["date"]))

BANNER = ('<aside class="ad-hp" data-ad="hungphat" aria-label="Quảng cáo"><span class="ad-lab">Quảng cáo</span>'
          '<a class="ad-a" href="https://hungphatlaptop.com/" target="_blank" rel="noopener">'
          '<img src="assets/hp-wide.png" width="195" height="64" alt="Hưng Phát Laptop" loading="lazy">'
          '<span class="ad-t">Laptop chính hãng đời 2025-2026 cho văn phòng, đồ hoạ và học tập.</span>'
          '<span class="ad-btn">Xem máy</span></a></aside>\n')

def render_home(posts, prod):
    items = [post_item(p) for p in posts]
    # --- bài nổi bật
    if items:
        h = items[0]
        lead = ('<a class="gh-lead" href="%s"><span class="gh-lm">%s</span><span class="gh-lb">'
                '<span class="gh-k">Bài mới nhất, %s</span><h2 class="gh-lh">%s</h2>'
                '<span class="gh-ld">%s</span><span class="gh-dt">%s</span>'
                '<span class="gh-go">Đọc bài</span></span></a>\n'
                % (h["href"], media(h, hero=True), esc(h["label"]), esc(h["title"]), esc(h["desc"]), h["date"]))
    else:
        lead = ""
    banner = BANNER
    # --- bài mới nhất (marker ngay đầu danh sách)
    rows = "".join(row(i) for i in items[1:7])
    latest = ('<section class="gh-sec" id="bai-viet" aria-labelledby="h-moi"><div class="gh-sh"><h2 id="h-moi">Bài mới nhất</h2>'
              '<p>Những bài mình vừa ghi xong.</p></div>\n<div class="pl gh-pl">\n%s\n%s</div></section>\n' % (MARK, rows))
    # --- theo chuyên mục
    cats = ""
    for k, name, desc in CATS:
        its = [i for i, p in zip(items, posts) if p["cat"] == k]
        if not its:
            continue
        top = "".join(row(i) for i in its[:3])
        rest = "".join('<li><a href="%s"><span class="gh-ct">%s</span><span class="gh-dt">%s</span></a></li>'
                       % (i["href"], esc(i["title"]), i["date"]) for i in its[3:])
        more = ('<p class="gh-more-t">Các bài còn lại</p><ul class="gh-cl">%s</ul>' % rest) if rest else ""
        cats += ('<section class="gh-sec" id="c-%s" aria-labelledby="h-%s"><div class="gh-sh"><h2 id="h-%s">%s</h2>'
                 '<p>%s <span class="gh-n">%d bài</span></p></div>\n<div class="gh-pl">%s</div>%s</section>\n'
                 % (k, k, k, esc(name), esc(desc), len(its), top, more))
    # --- máy nhắc tới (không giá)
    base = prod.get("base", SHOP)
    grp = ""
    for g in prod.get("groups", []):
        li = ""
        for p in prod.get("products", []):
            if p.get("group") != g["id"]:
                continue
            li += ('<li><span class="gh-br">%s</span><a href="%s%s/">%s</a><span class="gh-bl">%s</span></li>'
                   % (esc(p["brand"]), base, p["slug"], esc(p["name"]), esc(p["blurb"])))
        grp += ('<div class="gh-grp" id="%s"><h3>%s</h3><p>%s</p><ul class="gh-mach">%s</ul></div>\n'
                % (g["id"], esc(g["title"]), esc(g["desc"]), li))
    needs = "".join('<a href="#%s">%s</a>' % (g["id"], esc(g["short"])) for g in prod.get("groups", []))
    ser = "".join('<li><span class="gh-br">%s</span><a href="%s%s/">%s</a><span class="gh-bl">%s</span></li>'
                  % (esc(s["brand"]), base, s["slug"], esc(s["name"]), esc(s["desc"])) for s in prod.get("series", []))
    mach = ('<section class="gh-sec" id="may-minh-nhac" aria-labelledby="h-may"><div class="gh-sh"><h2 id="h-may">Máy mình nhắc tới</h2>'
            '<p>Những mẫu hay xuất hiện trong bài, gom theo nhu cầu. Bấm vào tên máy để xem cấu hình đầy đủ.</p></div>\n'
            '<nav id="nhu-cau" class="gh-needs" aria-label="Chọn theo nhu cầu">%s</nav>\n%s'
            '<div class="gh-grp" id="dong-may"><h3>Theo dòng máy</h3><p>Mỗi dòng có nhiều cấu hình hơn các mẫu ở trên.</p>'
            '<ul class="gh-mach">%s</ul></div></section>\n' % (needs, grp, ser))
    return lead, banner, latest, cats, mach

def build_home(root, posts, prod):
    f = root / "index.html"
    t = rd(f)
    t = fix_head(t, "")
    b = re.search(r"<body[^>]*>", t)
    lead, banner, latest, cats, mach = render_home(posts, prod)
    body = ("\n" + header_html("", "./") +
            '<main id="main"><div class="gh-wrap">\n'
            '<h1 class="sr">Laptop cho lập trình viên - ghi chú chọn máy của %s</h1>\n' % esc(PEN) +
            lead + banner +
            '<div class="gh-cols"><div class="gh-main">\n' + latest + cats + mach + '</div>\n' +
            aside_html("", posts, "bai-viet/", False) + '</div></div></main>\n' + footer_html(""))
    out = t[:b.end()] + body + "</body>\n</html>\n"
    wr(f, out)

# ---------------------------------------------------------------- CSS
CSS = r"""/* Ca Phe Code - Laptop Lap Trinh. File nay do tools/theme.py ghi, khong sua tay. */
:root{--bg:#faf5ec;--paper:#fffdf8;--ink:#2b2118;--mut:#6a5a4b;--line:#e6dccb;--ac:#b4490a;--ac2:#8f3906;--soft:#f4e6d2;--r:10px}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;font-family:"Be Vietnam Pro",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);line-height:1.7;background:var(--bg);overflow-wrap:break-word}
img{max-width:100%;height:auto;display:block}
a{color:inherit}
p{margin:0}
h1,h2,h3{font-family:Lora,Georgia,"Times New Roman",serif}
[id]{scroll-margin-top:16px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.skip{position:absolute;left:-9999px;top:8px;background:var(--paper);padding:10px 14px;border-radius:8px;z-index:60;font-weight:700}
.skip:focus{left:8px}
a:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid var(--ac);outline-offset:2px;border-radius:4px}
.gh-wrap{max-width:1180px;margin:0 auto;padding-left:clamp(16px,3vw,32px);padding-right:clamp(16px,3vw,32px)}
/* masthead */
.gh-top{border-bottom:1px solid var(--line);background:var(--bg)}
.gh-strip{display:flex;justify-content:space-between;align-items:center;gap:12px;min-height:44px;font-size:13px;color:var(--mut)}
.gh-shop{display:inline-flex;align-items:center;gap:6px;min-height:44px;font-weight:600;color:var(--ac2);text-decoration:none}
.gh-shop:hover{text-decoration:underline;text-underline-offset:3px}
.gh-mast{text-align:center;padding-top:14px;padding-bottom:6px}
.gh-name{display:inline-block;font-family:Lora,Georgia,serif;font-weight:700;font-size:clamp(34px,6.4vw,64px);line-height:1.1;letter-spacing:-.02em;text-decoration:none;color:var(--ink)}
.gh-name:hover{color:var(--ac2)}
.gh-tag{margin-top:6px;font-size:15px;color:var(--mut);font-style:italic;font-family:Lora,Georgia,serif}
.gh-nav{display:flex;flex-wrap:wrap;justify-content:center;gap:0 6px;padding-top:10px;padding-bottom:10px;border-top:1px solid var(--line);margin-top:14px;max-width:none}
.gh-nav a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;font-size:14.5px;font-weight:600;color:var(--ink);text-decoration:none;border-bottom:2px solid transparent}
.gh-nav a:hover{color:var(--ac2);border-bottom-color:var(--ac)}
/* bố cục */
.gh-cols{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:44px;align-items:start;padding-top:8px}
.gh-main{min-width:0}
.gh-aside{position:sticky;top:16px;display:grid;gap:18px;margin-top:28px}
.gh-w{background:var(--paper);border:1px solid var(--line);border-radius:var(--r);padding:20px}
.gh-w h2{margin:0 0 12px;font-size:19px;line-height:1.25;color:var(--ink)}
.gh-w p{font-size:15px;color:var(--mut)}
.gh-au{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.gh-av{width:46px;height:46px;border-radius:50%;background:var(--ac);color:#fff;font-family:Lora,Georgia,serif;font-weight:700;font-size:22px;display:inline-flex;align-items:center;justify-content:center}
.gh-chips{display:flex;flex-wrap:wrap;gap:8px}
.gh-chip{display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:0 14px;border-radius:999px;background:var(--soft);color:var(--ac2);font-size:14px;font-weight:600;text-decoration:none}
.gh-chip small{font-size:12px;color:var(--mut)}
.gh-chip:hover{background:var(--ac);color:#fff}
.gh-chip:hover small{color:#fff}
.gh-ul{list-style:none;margin:0;padding:0}
.gh-ul li+li{border-top:1px solid var(--line)}
.gh-ul a{display:block;padding:10px 0;font-size:15px;font-weight:500;text-decoration:none;line-height:1.45}
.gh-ul a:hover{color:var(--ac2);text-decoration:underline;text-underline-offset:3px}
.gh-ol{counter-reset:n}
.gh-ol li{counter-increment:n;position:relative;padding-left:30px}
.gh-ol li::before{content:counter(n);position:absolute;left:0;top:10px;font-family:Lora,Georgia,serif;font-weight:700;font-size:18px;color:var(--ac)}
/* bài nổi bật */
.gh-lead{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:36px;align-items:center;padding:34px 0 12px;text-decoration:none}
.gh-lm{position:relative;display:block;aspect-ratio:16/10;border-radius:var(--r);overflow:hidden;background:var(--soft)}
.gh-lm>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.gh-lb{display:grid;gap:12px}
.gh-k{font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--ac2)}
.gh-lh{margin:0;font-size:clamp(26px,3.4vw,40px);line-height:1.2;font-weight:700;letter-spacing:-.015em}
.gh-lead:hover .gh-lh{text-decoration:underline;text-underline-offset:5px;text-decoration-color:var(--ac)}
.gh-ld{font-size:16px;color:var(--mut);display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.gh-dt{font-size:13px;color:var(--mut)}
.gh-go{justify-self:start;display:inline-flex;align-items:center;min-height:44px;padding:0 22px;border-radius:999px;background:var(--ac);color:#fff;font-weight:600;font-size:15px}
.gh-lead:hover .gh-go{background:var(--ac2)}
/* placeholder */
.ph{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:14px;color:#fff;overflow:hidden}
.ph b{position:absolute;right:14px;top:-6px;font-family:Lora,Georgia,serif;font-size:clamp(80px,12vw,150px);font-weight:700;line-height:1;color:rgba(255,255,255,.2)}
.ph i{font-style:normal;font-size:11px;letter-spacing:.12em;text-transform:uppercase;font-weight:700}
.ph0{background:linear-gradient(135deg,#8f3906,#4a2410)}
.ph1{background:linear-gradient(135deg,#5c4a1a,#2f2a12)}
.ph2{background:linear-gradient(135deg,#a8530f,#5b2a14)}
.ph3{background:linear-gradient(135deg,#6b3d2a,#2b2118)}
.ph4{background:linear-gradient(135deg,#7a5a14,#4a2f0e)}
.ph5{background:linear-gradient(135deg,#8a3a22,#3d1c12)}
/* banner quảng cáo */
.ad-hp{position:relative;margin-top:30px;border:1px solid var(--line);border-radius:14px;background:#fff;padding:26px 22px 16px}
.ad-lab{position:absolute;left:20px;top:8px;font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#6b5f52;font-weight:700}
.ad-a{display:flex;align-items:center;gap:24px;text-decoration:none;flex-wrap:wrap}
.ad-a img{width:195px;height:64px;flex:none}
.ad-t{flex:1 1 260px;font-size:17px;font-weight:600;line-height:1.45;color:var(--ink)}
.ad-btn{display:inline-flex;align-items:center;min-height:46px;padding:0 26px;border-radius:999px;background:var(--ac);color:#fff;font-weight:700;font-size:15px}
.ad-a:hover .ad-btn{background:var(--ac2)}
/* khối */
.gh-sec{padding-top:52px}
.gh-sh{margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid var(--ink)}
.gh-sh h2{margin:0;font-size:clamp(24px,3vw,30px);line-height:1.2;font-weight:700;letter-spacing:-.01em}
.gh-sh p{margin-top:4px;font-size:15px;color:var(--mut)}
.gh-n{display:inline-block;margin-left:6px;padding:0 10px;border-radius:999px;background:var(--soft);color:var(--ac2);font-size:12.5px;font-weight:600}
.gh-pl{display:grid;gap:0}
/* hàng bài: ảnh trái, chữ phải (cũng là kiểu của thẻ post-card cũ) */
.gh-row,.gh-pl .post-card{display:grid;grid-template-columns:240px minmax(0,1fr);gap:22px;align-items:start;padding:20px 0;border-bottom:1px solid var(--line);text-decoration:none}
.gh-rm{position:relative;display:block;aspect-ratio:16/10;border-radius:8px;overflow:hidden;background:var(--soft)}
.gh-rm>img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.gh-rb,.gh-pl .post-card>div{display:grid;gap:6px;min-width:0}
.gh-rt{margin:0;font-size:21px;line-height:1.3;font-weight:700;letter-spacing:-.01em}
.gh-row:hover .gh-rt{color:var(--ac2);text-decoration:underline;text-underline-offset:4px;text-decoration-color:var(--ac)}
.gh-rd,.gh-pl .post-card p{font-size:15px;color:var(--mut);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.gh-pl .post-card .eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--ac2)}
.gh-pl .post-card .hd{font-family:Lora,Georgia,serif;font-size:21px;font-weight:700}
.gh-more-t{margin-top:22px;font-size:13px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--mut)}
.gh-cl{list-style:none;margin:6px 0 0;padding:0;columns:2;column-gap:36px}
.gh-cl li{break-inside:avoid;border-bottom:1px solid var(--line)}
.gh-cl a{display:grid;gap:2px;padding:10px 0;text-decoration:none}
.gh-ct{font-size:15.5px;font-weight:500;line-height:1.4}
.gh-cl a:hover .gh-ct{color:var(--ac2);text-decoration:underline;text-underline-offset:3px}
/* máy nhắc tới */
.gh-needs{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:6px}
.gh-needs a{display:inline-flex;align-items:center;min-height:44px;padding:0 18px;border-radius:999px;border:1px solid var(--ac);color:var(--ac2);font-weight:600;font-size:14.5px;text-decoration:none;background:var(--paper)}
.gh-needs a:hover{background:var(--ac);color:#fff}
.gh-grp{padding-top:28px}
.gh-grp h3{margin:0;font-size:21px;font-weight:700;line-height:1.3}
.gh-grp>p{margin:4px 0 10px;font-size:15px;color:var(--mut);max-width:62ch}
.gh-mach{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 36px}
.gh-mach li{display:grid;gap:2px;padding:12px 0;border-bottom:1px solid var(--line);align-content:start}
.gh-br{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;color:var(--mut)}
.gh-mach a{font-weight:600;font-size:16px;line-height:1.4;color:var(--ac2);text-underline-offset:3px}
.gh-mach a:hover{color:var(--ink)}
.gh-bl{font-size:14px;color:var(--mut);line-height:1.5}
/* footer */
.gh-f{margin-top:80px;background:var(--ink);color:#e9dfd0}
.gh-fin{display:flex;justify-content:space-between;gap:28px;flex-wrap:wrap;padding-top:40px;padding-bottom:40px;font-size:14.5px}
.gh-fb b{display:block;font-family:Lora,Georgia,serif;font-size:24px;color:#fff;margin-bottom:6px}
.gh-fb span{display:block;max-width:48ch;color:#dccfbb}
.gh-f nav{display:flex;gap:0 22px;flex-wrap:wrap;align-items:flex-start}
.gh-f a{color:#fff;text-decoration:none}
.gh-f a:hover{text-decoration:underline;text-underline-offset:3px}
.gh-f nav a{display:inline-flex;align-items:center;min-height:44px}
/* bài viết */
.gh-paper{background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:clamp(18px,4.5vw,48px);margin-top:28px}
.gh-paper article{font-size:17.5px;line-height:1.82;min-width:0}
.gh-paper h1{margin:0 0 20px;font-size:clamp(28px,4.2vw,40px);line-height:1.22;font-weight:700;letter-spacing:-.015em}
.gh-paper h2{margin:44px 0 12px;font-size:clamp(23px,3vw,29px);line-height:1.28;font-weight:700}
.gh-paper h3{margin:30px 0 8px;font-size:21px;line-height:1.3;font-weight:700}
.gh-paper p,.gh-paper ul,.gh-paper ol{margin:0 0 16px}
.gh-paper li{margin:4px 0}
.gh-paper article a{color:var(--ac2);text-underline-offset:3px}
.gh-paper article a:hover{color:var(--ink)}
.gh-paper strong{font-weight:700}
.gh-paper figure{margin:22px 0}
.gh-paper figure img{width:100%;border-radius:10px}
.gh-paper figcaption{font-size:14px;color:var(--mut);margin-top:8px}
.gh-paper blockquote{margin:22px 0;padding:12px 20px;border-left:4px solid var(--ac);background:var(--soft);border-radius:0 8px 8px 0}
.gh-paper .gia{font-size:14px;color:var(--mut);margin-top:32px;padding-top:14px;border-top:1px solid var(--line)}
.gh-paper .toc{margin:22px 0;border:1px solid var(--line);border-radius:10px;background:var(--bg);padding:6px 20px}
.gh-paper .toc summary{cursor:pointer;font-weight:700;padding:10px 0;min-height:44px;display:flex;align-items:center;font-family:Lora,Georgia,serif;font-size:18px}
.gh-paper .toc ol{margin:0 0 12px;padding-left:22px;font-size:16px}
.gh-paper .tbl{overflow-x:auto;margin:22px 0;border:1px solid var(--line);border-radius:10px}
.gh-paper table{width:100%;border-collapse:collapse;font-size:15px;line-height:1.55;min-width:520px}
.gh-paper th,.gh-paper td{padding:10px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line)}
.gh-paper thead th{background:var(--soft);color:var(--ink);font-weight:700}
.gh-paper tbody tr:last-child th,.gh-paper tbody tr:last-child td{border-bottom:0}
@media (max-width:1000px){
.gh-cols{grid-template-columns:minmax(0,1fr)}
.gh-aside{position:static;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.gh-lead{grid-template-columns:minmax(0,1fr);gap:20px}
}
@media (max-width:640px){
.gh-strip span{font-size:12px}
.gh-row,.gh-pl .post-card{grid-template-columns:104px minmax(0,1fr);gap:14px;padding:16px 0}
.gh-rd,.gh-pl .post-card p{display:none}
.gh-rt,.gh-pl .post-card .hd{font-size:17px}
.gh-cl{columns:1}
.gh-mach{grid-template-columns:minmax(0,1fr)}
.ad-a{gap:14px}
.ad-btn{width:100%;justify-content:center}
.gh-paper article{font-size:17px}
}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
"""

# ---------------------------------------------------------------- chạy
def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    posts, prod = read_data(root)
    wr(root / "style.css", CSS)
    for f in sorted(root.glob("bai-viet/*/index.html")):
        reframe_post(f, posts)
    build_home(root, posts, prod)
    print("theme OK: %d bai" % len(posts))

if __name__ == "__main__":
    main()
