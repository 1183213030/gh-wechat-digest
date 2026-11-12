"""封面图与正文配图：Chrome headless 渲染 HTML 模板 → PNG。

为什么不用 PIL：这个技能的原则是「clone 下来就能跑」。PIL 要 pip 装，
装了换台机器还得再装；而本机一定有浏览器（Chrome / Edge），截图这条路
零依赖，且中文排版靠系统字体，比 PIL 手画字距准得多。

出什么图：
  · 封面大图 2.35:1 → 900x383（公众号首图，按 2x 出图 1800x766）
  · 封面小图 1:1   → 500x500（次条/转发卡片）
  · 正文配图        → og 卡片的本地副本（微信正文不收外链图，必须本地插入）

封面不依赖 og 图，全部由文字 + 色块生成：og 卡片长得千篇一律且有的仓库图很丑，
自己排的文字卡在信息流里更整齐，也保证每期风格一致。
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

C_BG_1 = "#16302A"      # 深墨绿，与正文 accent #1F6F4A 同族
C_BG_2 = "#0B1613"
C_INK = "#F3F0E7"       # 米白
C_DIM = "#9DB0A7"
C_ACCENT = "#6FCF97"

FONT_STACK = ('"Microsoft YaHei","PingFang SC","Hiragino Sans GB",'
              '"Source Han Sans SC","Noto Sans CJK SC",sans-serif')
MONO_STACK = '"JetBrains Mono",Consolas,"Courier New",monospace'

BROWSERS = [
    r"C:/Program Files/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    r"C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    r"C:/Program Files/Microsoft/Edge/Application/msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def find_browser():
    for p in BROWSERS:
        if os.path.exists(p):
            return p
    return None


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _wrap(text, size, max_w, max_lines=2, ls=0.0):
    """按估算字宽折行。中文按 1em，英文/数字按 0.56em，ls 是 letter-spacing（em）。
    不用浏览器自己折是因为要精确控制「最多两行 + 省略号」——估算必须把字距算进去，
    否则 CSS 里字距一加，浏览器会自己再折一次，文字就被切在框外。"""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return []
    lines, cur, w = [], "", 0.0
    for ch in text:
        cw = (size if ord(ch) > 0x2000 else size * 0.56) * (1 + ls)
        if w + cw > max_w and cur:
            lines.append(cur)
            cur, w = "", 0.0
            if len(lines) == max_lines:
                break
        cur += ch
        w += cw
    if cur and len(lines) < max_lines:
        lines.append(cur)
    if len(lines) == max_lines and len("".join(lines)) < len(text):
        lines[-1] = lines[-1].rstrip()[:-1] + "…"
    return lines


def _fill(tpl, **kw):
    """JS 模板里用 __KEY__ 占位，避免和 CSS 的花括号打架。"""
    out = tpl
    for k, v in kw.items():
        out = out.replace("__" + k.upper() + "__", str(v))
    return out


# ---------------------------------------------------------------- 封面模板

COVER_TPL = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { margin:0; padding:0; box-sizing:border-box; }
  html,body { width:__W__px; height:__H__px; overflow:hidden; }
  body { font-family:__FONT__; -webkit-font-smoothing:antialiased; }
  .cover {
    position:relative; width:__W__px; height:__H__px; overflow:hidden;
    background:
      radial-gradient(circle at 88% 8%, rgba(111,207,151,0.20) 0%, rgba(111,207,151,0) 46%),
      radial-gradient(circle at 6% 96%, rgba(111,207,151,0.10) 0%, rgba(111,207,151,0) 40%),
      linear-gradient(135deg, __BG1__ 0%, __BG2__ 100%);
    display:flex; flex-direction:column; justify-content:space-between;
    padding:__PAD__px;
  }
  /* 细网格，压住纯色底的廉价感 */
  .grid {
    position:absolute; inset:0;
    background-image:
      linear-gradient(to right, rgba(255,255,255,0.045) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(255,255,255,0.045) 1px, transparent 1px);
    background-size:__GRID__px __GRID__px;
    mask-image:linear-gradient(120deg, rgba(0,0,0,0.85), rgba(0,0,0,0.15));
    -webkit-mask-image:linear-gradient(120deg, rgba(0,0,0,0.85), rgba(0,0,0,0.15));
  }
  .ring {
    position:absolute; border-radius:50%;
    border:1px solid rgba(111,207,151,0.22);
  }
  .top { position:relative; display:flex; align-items:center; gap:__GAP__px; }
  .badge {
    font-size:__S_BADGE__px; letter-spacing:0.28em; color:__ACCENT__;
    font-weight:700; text-transform:uppercase;
  }
  .sep { width:__SEP__px; height:1px; background:rgba(157,176,167,0.45); }
  .no { font-size:__S_BADGE__px; letter-spacing:0.16em; color:__DIM__; }
  .mid { position:relative; padding-right:__MIDR__px; }
  .kicker {
    font-size:__S_KICK__px; letter-spacing:0.16em; color:__ACCENT__;
    font-weight:700; margin-bottom:__GAP2__px;
  }
  .title {
    font-size:__S_TITLE__px; line-height:1.22; color:__INK__;
    font-weight:900; letter-spacing:0.01em;
  }
  .sub {
    margin-top:__GAP3__px; font-size:__S_SUB__px; line-height:1.6;
    color:__DIM__; letter-spacing:0.02em;
  }
  .bot { position:relative; display:flex; align-items:center; justify-content:space-between; }
  .repo {
    font-family:__MONO__; font-size:__S_REPO__px; color:rgba(243,240,231,0.62);
    letter-spacing:0.04em;
  }
  .meta { display:flex; align-items:center; gap:__GAP__px; }
  .star { font-size:__S_REPO__px; color:__ACCENT__; font-weight:700; }
  .by { font-size:__S_REPO__px; color:rgba(243,240,231,0.40); letter-spacing:0.08em; }
  .num {
    position:absolute; right:__NUMR__px; bottom:__NUMB__px;
    font-size:__S_NUM__px; font-weight:900; color:rgba(111,207,151,0.13);
    line-height:1; letter-spacing:-0.04em;
  }
</style></head>
<body><div class="cover">
  <div class="grid"></div>
  <div class="ring" style="width:__R1__px;height:__R1__px;right:__R1R__px;top:__R1T__px;"></div>
  <div class="top">
    <span class="badge">__COLUMN__</span>
    <span class="sep"></span>
    <span class="no">__NO__</span>
  </div>
  <div class="mid">
    __KICKER__
    <div class="title">__TITLE__</div>
    __SUB__
  </div>
  <div class="bot">
    <span class="repo">__REPO__</span>
    <span class="meta">__STAR__<span class="by">__BY__</span></span>
  </div>
  <div class="num">__NUM__</div>
</div></body></html>"""


def cover_html(item, prof, size=(900, 383), big=False):
    """item 是打包好的项目字典（zh_name / one_liner / full_name / stars / kicker）。
    导读封面传 kind='index'，用 title/sub 直接覆盖。"""
    w, h = size
    ratio = h / w
    # 2.35:1 按 900 宽算，1:1 按 500 宽算 —— 方图要是也跟着 900 缩，
    # 500 宽的图字号只剩七成，看起来又空又轻
    k = w / (500.0 if ratio > 0.7 else 900.0)

    kicker = item.get("cover_kicker") or item.get("kicker") or ""
    title_txt = item.get("cover_title") or item.get("zh_name") or item.get("full_name", "")
    # 副标只在显式给了 cover_sub 时才显示：kicker 本身已是定位句，
    # 再垫一行 one_liner（多半是英文原句）在中文封面上很出戏，还容易语义重复
    sub_txt = item.get("cover_sub") or ""

    # 1:1 的横向空间少，字号和边距都要重算
    pad = int(48 * k) if ratio > 0.7 else int(52 * k)
    mid_r = int(24 * k) if ratio > 0.7 else int(60 * k)

    s_title = int((46 if len(title_txt) <= 10 else 38) * k)
    if ratio > 0.7:
        s_title = int(s_title * 1.12)
    s_kick = int((15 if ratio > 0.7 else 14) * k)
    title_lines = _wrap(title_txt, s_title, w - pad * 2 - mid_r, 2 if ratio < 0.7 else 3)
    title_html = "<br>".join(_esc(x) for x in title_lines) or _esc(title_txt)

    kw = w - pad * 2 - mid_r
    kicker_html = ""
    if kicker:
        k_lines = _wrap(kicker, s_kick, kw, 2, ls=0.16)
        kicker_html = ('<div class="kicker">'
                       + "<br>".join(_esc(x) for x in k_lines) + '</div>')
    sub_lines = _wrap(sub_txt, s_kick, kw, 1 if ratio < 0.7 else 2)
    sub_html = (f'<div class="sub">{_esc(" ".join(sub_lines))}</div>'
                if sub_lines else "")

    star = item.get("stars")
    star_html = (f'<span class="star">★ {star:,}</span>' if isinstance(star, int) else "")

    return _fill(
        COVER_TPL,
        W=w, H=h, FONT=FONT_STACK, MONO=MONO_STACK,
        BG1=C_BG_1, BG2=C_BG_2, INK=C_INK, DIM=C_DIM, ACCENT=C_ACCENT,
        PAD=pad, GRID=int(44 * k), GAP=int(14 * k), SEP=int(28 * k),
        GAP2=int(12 * k), GAP3=int(14 * k), MIDR=mid_r,
        S_BADGE=int(13 * k), S_KICK=s_kick, S_TITLE=s_title,
        S_SUB=int(15 * k), S_REPO=int(13 * k), S_NUM=int(180 * k),
        NUMR=int(40 * k), NUMB=int(16 * k),
        R1=int(360 * k), R1R=int(-120 * k), R1T=int(-150 * k),
        COLUMN=_esc(prof.get("column", "")),
        NO=_esc(f"第 {int(item.get('_issue_no') or 1):02d} 期"),
        KICKER=kicker_html, TITLE=title_html, SUB=sub_html,
        REPO=_esc(item.get("full_name") or ""),
        STAR=star_html, BY=_esc(prof.get("account", "")),
        NUM=_esc(item.get("_num") or "01"),
    )


def shot(browser, html_path, png_path, size):
    """Chrome headless 截图。2x 出图，微信压缩后文字边缘不会糊。

    必须走 ASCII 路径：Chrome 拿到未编码的中文 file:/// 会静默失败（rc=0 但不落盘），
    所以先在临时目录出图，再移动到中文名的目标位置。
    """
    w, h = size
    tmp_png = os.path.join(tempfile.gettempdir(), f"ghcover_{uuid.uuid4().hex}.png")
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           "--force-device-scale-factor=2",
           f"--window-size={w},{h}",
           f"--screenshot={tmp_png}",
           "file:///" + html_path.replace("\\", "/").lstrip("/")]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=90,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception as e:
        return False, str(e)
    if not os.path.exists(tmp_png) or os.path.getsize(tmp_png) < 2000:
        msg = (r.stderr or b"").decode("utf-8", "ignore")[:200]
        return False, msg or "截图未生成"
    shutil.move(tmp_png, png_path)
    return True, ""


def make(html_str, png_path, size, browser):
    tmp = os.path.join(tempfile.gettempdir(), f"ghcover_{uuid.uuid4().hex}.html")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html_str)
    ok, err = shot(browser, tmp, png_path, size)
    try:
        os.remove(tmp)
    except OSError:
        pass
    return ok, err


# ---------------------------------------------------------------- 对外

SIZES = {"big": (900, 383), "square": (500, 500)}


def build(issue, out_dir, want=("big", "square"), browser=None):
    """为一期生成全部封面。返回 [(tag, 文件路径, 说明)]。"""
    browser = browser or find_browser()
    if not browser:
        return [], "没找到 Chrome / Edge，封面需要浏览器渲染"

    os.makedirs(out_dir, exist_ok=True)
    prof = issue.get("profile") or {}
    made = []
    items = [issue["main"]] + (issue.get("shorts") or [])

    for idx, it in enumerate(items, 1):
        if not it.get("deep"):
            continue
        it = dict(it)
        it["_issue_no"] = issue.get("issue_no")
        it["_num"] = "①②③④⑤⑥⑦⑧⑨"[min(idx, 9) - 1]
        slug = it.get("slug") or it["full_name"].split("/")[-1].lower()
        for kind in want:
            size = SIZES[kind]
            p = os.path.join(out_dir, f"a{idx}_{slug}_封面_{'2.35x1' if kind == 'big' else '1x1'}.png")
            ok, err = make(cover_html(it, prof, size), p, size, browser)
            if ok:
                made.append((f"a{idx}", p, f"{it.get('zh_name')} · {size[0]}x{size[1]}"))
            else:
                print(f"[!] 封面失败 {p}: {err}", file=sys.stderr)

    # 导读封面：标题是「这 N 个项目」，副标题用筛选原则
    n = len([x for x in items])
    index_item = {
        "cover_title": f"这 {n} 个项目",
        "cover_kicker": prof.get("cover_kicker") or "本期导读",
        "cover_sub": prof.get("cover_sub") or f"筛选只有三个原则：{prof.get('criteria', '')}",
        "full_name": prof.get("account", ""),
        "stars": None,
        "_issue_no": issue.get("issue_no"),
        # 右下装饰大号：与顶部期号呼应；别用 № 这类符号，中文字体渲染出来很怪
        "_num": f"{int(issue.get('issue_no') or 1):02d}",
    }
    for kind in want:
        size = SIZES[kind]
        p = os.path.join(out_dir, f"issue_封面_{'2.35x1' if kind == 'big' else '1x1'}.png")
        ok, err = make(cover_html(index_item, prof, size), p, size, browser)
        if ok:
            made.insert(0, ("导读", p, f"索引页 · {size[0]}x{size[1]}"))
        else:
            print(f"[!] 封面失败 {p}: {err}", file=sys.stderr)

    return made, ""
