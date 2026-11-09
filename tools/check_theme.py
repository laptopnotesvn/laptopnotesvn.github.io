#!/usr/bin/env python3
"""check_theme.py - kiem theme.py. Dung: python3 tools/check_theme.py [thu_muc_site]
Chi dung thu vien chuan. In cac dong PASS/FAIL ngan va 1 dong TONG KET cuoi.
tools/_goc/ = ban luu truoc theme (tu tao neu chua co, tu thu muc hien tai).
"""
import sys, re, os, subprocess, hashlib, shutil, html, json
from pathlib import Path
from urllib.parse import urlsplit, unquote

S = re.S
ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
TOOLS = ROOT / "tools"
GOC = TOOLS / "_goc"
THEME = TOOLS / "theme.py"
LOGO_SRC = Path("/home/stevenlam/work/blog-redesign-1011/hp-wide.png")
FORBID = [r"Hưng Phát", r"hungphat", r"Phát Lâm", r"—",
          r"xem thêm", r"tham khảo thêm", r"hãy cùng", r"hoàn hảo", r"tuyệt vời", r"đột phá", r"mượt mà",
          r"\d[\d.,]*\s?(?:đ\b|₫|VNĐ|VND|triệu|tr\b)"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆✅❌️]")
results = []

def ok(name, cond, info=""):
    results.append((name, bool(cond), info))
    print(("PASS " if cond else "FAIL ") + name + ((" | " + info) if info else ""))

def rd(p):
    return Path(p).read_text(encoding="utf-8")

def run_theme():
    r = subprocess.run([sys.executable, str(THEME), str(ROOT)], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-800:])
    return r.returncode == 0

def site_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and "tools" not in p.relative_to(ROOT).parts
                  and not any(x.startswith(".") for x in p.relative_to(ROOT).parts))

def hash_all():
    h = {}
    for p in site_files():
        h[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return h

def html_files(base=ROOT):
    return sorted(p for p in base.rglob("*.html") if "tools" not in p.relative_to(base).parts)

def article(t):
    a = t.find("<article")
    b = t.rfind("</article>")
    return t[a:b + 10] if a >= 0 and b > a else None

def drop_banner(t):
    return re.sub(r'<aside class="ad-hp"[^>]*>.*?</aside>', "", t, flags=S)

def ext_links(t):
    return re.findall(r'<a\b[^>]*\bhref="(https?://[^"]+)"', drop_banner(t))

def meta(t):
    g = lambda r: (re.search(r, t, S).group(1) if re.search(r, t, S) else None)
    ld = re.findall(r'<script type="application/ld\+json">(.*?)</script>', t, S)
    return (g(r"<title>(.*?)</title>"), g(r'<meta name="description" content="([^"]*)"'),
            g(r'<link rel="canonical" href="([^"]*)"'), ld,
            g(r'<meta property="og:title" content="([^"]*)"'), g(r'<meta name="robots" content="([^"]*)"'))

def visible_frame(t, rel):
    """Chu nhin thay cua phan khung: bo head, article, main danh muc, banner, script."""
    b = re.search(r"<body[^>]*>(.*)</body>", t, S)
    x = b.group(1) if b else t
    x = drop_banner(x)
    a = article(x)
    if a:
        x = x.replace(a, "")
    x = re.sub(r"<script.*?</script>", "", x, flags=S)
    alts = " ".join(re.findall(r'\b(?:alt|title|aria-label)="([^"]*)"', x))
    txt = html.unescape(re.sub(r"<[^>]+>", " ", x)) + " " + html.unescape(alts)
    return txt

# ----- 0. ban luu goc
if not GOC.is_dir():
    for p in html_files() + [ROOT / "style.css"]:
        d = GOC / p.relative_to(ROOT)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, d)
    print("da tao tools/_goc/ tu trang thai hien tai")
goc_pages = sorted(p for p in GOC.rglob("*.html"))

# ----- 1. idempotent
ok("theme.py chay 1", run_theme())
h1 = hash_all()
import time
t0 = time.time()
ok("theme.py chay 2", run_theme())
dt = time.time() - t0
h2 = hash_all()
diff = [k for k in h1 if h1[k] != h2.get(k)] + [k for k in h2 if k not in h1]
ok("1 idempotent (hash moi file giong nhau)", not diff, "khac: %s" % diff[:3] if diff else "%d file, %.2fs" % (len(h1), dt))
ok("1b duoi 5 giay", dt < 5)

# ----- 2. article nguyen byte
bad = []
n = 0
for g in goc_pages:
    rel = g.relative_to(GOC)
    cur = ROOT / rel
    if not cur.is_file():
        bad.append("thieu " + str(rel)); continue
    a0, a1 = article(rd(g)), article(rd(cur))
    if (a0 is None and a1 is None) or str(rel) == "index.html":
        continue    # index.html duoc dung lai hoan toan tu du lieu cac bai, khong nam trong luat article
    n += 1
    if a0 != a1:
        bad.append(str(rel))
ok("2 article giong tung byte so voi _goc", not bad, "%d trang co article; loi: %s" % (n, bad[:3]))

# ----- 3. SEO
bad = []
for g in goc_pages:
    rel = g.relative_to(GOC)
    if meta(rd(g)) != meta(rd(ROOT / rel)):
        bad.append(str(rel))
ok("3 title/description/canonical/og/robots/JSON-LD khong doi", not bad, "loi: %s" % bad[:3])
for f in ("robots.txt", "sitemap.xml"):
    ok("3b %s con nguyen" % f, (ROOT / f).is_file())

# ----- 4. trang chu link du bai, 1 marker
home = rd(ROOT / "index.html")
slugs = sorted(p.parent.name for p in ROOT.glob("bai-viet/*/index.html"))
missing = [s for s in slugs if 'href="bai-viet/%s/"' % s not in home]
ok("4 trang chu link du moi bai", not missing, "%d bai; thieu %s" % (len(slugs), missing[:3]))
ok("4b dung 1 POSTS:START", home.count("<!-- POSTS:START -->") == 1, "so luong %d" % home.count("<!-- POSTS:START -->"))
ids = ["bai-viet", "main", "nhu-cau", "gon-nhe", "sinh-vien", "may-tram", "dong-may", "c-so-sanh", "c-danh-gia-may", "c-chon-may", "c-kien-thuc"]
ok("4d du id neo", all('id="%s"' % i in home for i in ids), str([i for i in ids if 'id="%s"' % i not in home]))
ok("4e dung 1 h1 tren trang chu", len(re.findall(r"<h1\b", home)) == 1)
ok("4f marker nam ngay dau danh sach Bai moi nhat", bool(re.search(r'<div class="pl gh-pl">\s*<!-- POSTS:START -->', home)))

# ----- 5. chu cam + link ngoai
hits = []
for p in html_files():
    rel = str(p.relative_to(ROOT))
    txt = visible_frame(rd(p), rel)
    for pat in FORBID:
        m = re.search(pat, txt, re.I)
        if m:
            hits.append("%s:%s" % (rel, m.group(0)))
    if EMOJI.search(txt):
        hits.append(rel + ":emoji")
ok("5 khung khong co chu cam/emoji/gia", not hits, "%d trang; vi pham: %s" % (len(html_files()), hits[:4]))
# thong tin: noi dung giu nguyen co chu cam
info = 0
for p in html_files():
    t = rd(p)
    a = article(t)
    body = a or ""
    if re.search(r"Hưng Phát|\d[\d.,]*\s?(?:đ\b|₫)", html.unescape(re.sub(r"<[^>]+>", " ", body))):
        info += 1
print("INFO %d trang co chu Hung Phat/gia trong phan GIU NGUYEN (article hoac main danh muc), khong sua theo luat" % info)

bad = []
for g in goc_pages:
    rel = g.relative_to(GOC)
    a, b = ext_links(rd(g)), ext_links(rd(ROOT / rel))
    if str(rel) == "index.html":
        if set(a) != set(b):
            bad.append("index (tap link): -%s +%s" % (sorted(set(a) - set(b))[:2], sorted(set(b) - set(a))[:2]))
    elif sorted(a) != sorted(b):
        bad.append("%s: %d -> %d" % (rel, len(a), len(b)))
ok("5b link ra ngoai truoc/sau bang nhau (index: theo tap duy nhat)", not bad, "; ".join(bad[:3]))

# ----- 6. bai test
tdir = ROOT / "bai-viet" / "zz-test-bai-moi"
src = sorted(ROOT.glob("bai-viet/*/index.html"))
src = [p for p in src if p.parent.name != "zz-test-bai-moi"][0]
t = rd(src)
t = re.sub(r"<title>.*?</title>", "<title>Bài thử nghiệm mới - Laptop Lập Trình</title>", t, count=1, flags=S)
t = re.sub(r"(<article[^>]*>.*?<h1[^>]*>).*?(</h1>)", r"\1Bài thử nghiệm mới\2", t, count=1, flags=S)
t = re.sub(r'(<p class="gia">\s*Đăng ngày )\d{2}/\d{2}/\d{4}', r"\g<1>31/12/2099", t)
t = re.sub(r'("datePublished"\s*:\s*")[^"]+', r"\g<1>2099-12-31T08:00:00+07:00", t)
t = re.sub(r'<figure class="feat">.*?</figure>', "", t, flags=S)
tdir.mkdir(exist_ok=True)
(tdir / "index.html").write_text(t, encoding="utf-8")
ok("6 chay theme khi co bai test", run_theme())
home = rd(ROOT / "index.html")
hero = re.search(r'<a class="gh-lead".*?</a>', home, S)
hero = hero.group(0) if hero else ""
ok("6a bai test len hero", 'href="bai-viet/zz-test-bai-moi/"' in hero and "Bài thử nghiệm mới" in hero)
ok("6b hero dung o thay the CSS (khong anh)", 'class="ph ph' in hero and "<img" not in hero)
ok("6c trang bai test duoc boc khung moi", 'class="gh-top"' in rd(tdir / "index.html") and 'class="gh-aside"' in rd(tdir / "index.html") and 'class="gh-paper"' in rd(tdir / "index.html"))
ok("6d trang chu van 1 marker, bai test co trong nhom chuyen muc", home.count("<!-- POSTS:START -->") == 1 and home.count('href="bai-viet/zz-test-bai-moi/"') >= 2)
shutil.rmtree(tdir)
ok("6e xoa bai test + chay lai theme", run_theme())
home = rd(ROOT / "index.html")
ok("6f sach bai test", "zz-test-bai-moi" not in home and not tdir.exists())
h3 = hash_all()
ok("6g trang thai sau xoa giong truoc khi thu", h3 == h2)

# ----- 7. tham chieu css/anh
bad = []
for p in html_files():
    t = rd(p)
    for u in re.findall(r'(?:href|src)="([^"]+)"', t):
        if re.match(r"(https?:|mailto:|tel:|data:|#|//)", u):
            continue
        path = unquote(urlsplit(u).path)
        if not path:
            continue
        tgt = (ROOT / path.lstrip("/")) if path.startswith("/") else (p.parent / path)
        if tgt.is_dir():
            tgt = tgt / "index.html"
        if not tgt.exists():
            bad.append("%s -> %s" % (p.relative_to(ROOT), u))
ok("7 khong tham chieu toi file thieu", not bad, "%d loi: %s" % (len(bad), bad[:3]))

# ----- 8. banner
home = rd(ROOT / "index.html")
banners = re.findall(r'<aside class="ad-hp"[^>]*data-ad="hungphat"[^>]*>.*?</aside>', home, S)
ok("8 index co dung 1 banner", len(banners) == 1 and home.count('class="ad-hp"') == 1)
b = banners[0] if banners else ""
links = re.findall(r'<a\b[^>]*href="(https?://[^"]+)"[^>]*>', b)
ok("8b banner co dung 1 link hungphatlaptop.com", links == ["https://hungphatlaptop.com/"])
tag = re.search(r'<a\b[^>]*href="https://hungphatlaptop\.com/"[^>]*>', b)
ok("8c rel noopener, target _blank", bool(tag) and 'rel="noopener"' in tag.group(0) and 'target="_blank"' in tag.group(0))
ok("8d banner co nhan Quang cao, cau, nut, alt",
   all(x in b for x in ["Quảng cáo", "Laptop chính hãng đời 2025-2026 cho văn phòng, đồ hoạ và học tập.", "Xem máy", 'alt="Hưng Phát Laptop"', 'width="195" height="64"']))
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
logo = ROOT / "assets" / "hp-wide.png"
ok("8e assets/hp-wide.png cung sha256 voi ban goc", logo.is_file() and LOGO_SRC.is_file() and sha(logo) == sha(LOGO_SRC))
others = [str(p.relative_to(ROOT)) for p in html_files() if p.name != "index.html" or p.parent != ROOT]
leak = [x for x in others if "ad-hp" in rd(ROOT / x)]
ok("8f trang bai KHONG co banner", not leak, str(leak[:3]))
ok("8g banner khong gia/emoji/gach dai", not re.search(r"—|\d[\d.,]*\s?(?:đ\b|₫)", b) and not EMOJI.search(b))

# ----- 9. gioi han font/JS
fonts = re.findall(r'<link href="(https://fonts\.googleapis\.com[^"]+)"', home)
fam = re.findall(r"family=([^:&]+)", html.unescape(fonts[0])) if fonts else []
ok("9 font toi da 2 ho, co display=swap", fonts and len(fam) <= 2 and "display=swap" in fonts[0], str(fam))
ok("9b ban viet khong co script ngoai", "<script src" not in home)

fails = [r for r in results if not r[1]]
print("TONG KET %s: %d kiem, %d PASS, %d FAIL%s" % (ROOT.name, len(results), len(results) - len(fails), len(fails),
      (" -> " + "; ".join(f[0] for f in fails[:4])) if fails else ""))
sys.exit(1 if fails else 0)
