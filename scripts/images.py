"""配图系统：槽位规划 → 搜候选 → 人工审核 → 选定入库。

设计口径（2026-11 用户定稿）：
  · 高密度图文混排——1500 字文章 8~12 张图，每 1~3 个自然段一次配图机会，
    数量由内容决定，不硬凑，也不允许连续大段纯文字
  · 图要贴上下文：槽位带「类型 + 情绪 + 理由 + 关键词」，AI 搜图前先读整篇
    文章，再按每个槽位的语境单独搜，每槽 2~3 张候选
  · 种类要混：表情包 / 梗图 / 事件截图 / 软件截图（截图必须来自真实项目，
    不虚构）
  · 版权：网络表情包默认标「授权待人工确认」，不默认可商用
  · 人工挑选：search 只出候选不出结论，review 页里人挑完把 JSON 贴回去 apply

数据落点：
  data/images.json   槽位计划 + 候选元数据 + 选定结果
  data/images/aX/    候选图片本体（文件名 = 槽位_候选号.ext）
  data/reports/images_review.html   审核页

命令：
  python scripts/images.py plan                          # 生成/刷新槽位（保留已搜候选）
  python scripts/images.py list                         # 看每个槽位的状态
  python scripts/images.py search --slot a1_s1 --kw "熊猫头 无语 表情包" [--n 3]
  python scripts/images.py search-repo --slot a1_s2     # 从仓库 README 找真实截图
  python scripts/images.py review                       # 出审核页
  python scripts/images.py apply --picks '{"a1_s1":"A"}'   # 写入选定
  python scripts/images.py apply --auto                 # 每槽先预选第一张候选
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P_IMG = os.path.join(D, "data", "images.json")
IMG_DIR = os.path.join(D, "data", "images")
REPORTS = os.path.join(D, "data", "reports")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# ---------------------------------------------------------------- 槽位模板
# (anchor, 前提字段, 类型, 情绪, 默认关键词, 默认图注, 理由)
# anchor 对应 render.article_body 里的插入点；前提字段缺了就不建这个槽。
SLOT_TEMPLATE = [
    ("lead_after", None, "表情包", "开场钩子",
     ["看不懂但大受震撼 表情包", "有意思 挺好 表情包"], "",
     "标题抛完钩子，先给读者一个情绪共鸣点，留住往下划的手指"),
    ("what_mid", "what", "软件截图", None,
     [], "项目长这样（截图来自项目仓库）",
     "讲功能时让读者看到真实界面，比文字描述省 100 字"),
    ("what_end", "what", "表情包", "有点东西",
     ["有点东西 表情包", "期待 表情包 gif"], "",
     "功能讲完垫一张梗图换口气，再进痛点"),
    ("pain_end", "pain", "表情包", "无奈共鸣",
     ["熊猫头 无语 表情包", "心累 打工人 表情包"], "",
     "吐槽痛点之后读者正有共鸣，表情包替他们说一句"),
    ("ai_mid", "ai_why", "梗图", "AI 梗",
     ["AI 机器人 表情包", "让人工智能替我打工 梗图"], "",
     "AI 安装环节放 AI 梗，贴近段落语境"),
    ("first_end", "first", "表情包", "开工",
     ["开工 表情包", "冲 干起来 表情包"], "",
     "上手清单之后给个开工情绪"),
    ("pits_end", "pits", "表情包", "踩坑头大",
     ["程序员 踩坑 表情包", "汗颜 无语 表情包 gif"], "",
     "坑列表看完心里发怵，垫张图缓口气"),
    ("fit_end", None, "表情包", "真香",
     ["真香 表情包", "开心 满足 表情包"], "",
     "适合/不适合判断后给正向情绪收尾"),
    ("verdict_after", "verdict", "表情包", "值得",
     ["鼓掌 表情包", "这波不亏 表情包"], "",
     "金句之后用一张正向表情收束全篇"),
]

ANCHOR_LABEL = {
    "lead_after": "导语后", "what_mid": "功能段中", "what_end": "功能段末",
    "pain_end": "痛点后", "ai_mid": "AI 段中", "first_end": "上手清单后",
    "pits_end": "坑后", "fit_end": "适合判断后", "verdict_after": "金句后",
}

LICENSE_BY_TYPE = {
    "表情包": "网络传播素材，授权待人工确认，不作商用默认",
    "梗图": "网络传播素材，授权待人工确认，不作商用默认",
    "动漫图": "网络传播素材，授权待人工确认，不作商用默认",
    "事件截图": "社交平台公开内容，转载需注明来源并人工确认",
    "软件截图": "项目仓库原图，注明出处使用",
}


def log(msg):
    print(msg)


def _load(path, default):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return default


def load_plan():
    return _load(P_IMG, {})


def save_plan(data):
    with open(P_IMG, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- 槽位规划

def _plan_article(art_key, item, old_art):
    """按文章字段生成槽位。old_art 是上一次的计划：候选和选定要原样保留，
    只补新槽、不重排编号——已搜好的图不能因为重跑 plan 丢了。"""
    old_slots = {s.get("id"): s for s in (old_art or {}).get("slots") or []}
    slots, n = [], 0
    what = item.get("what") or []
    for anchor, need, typ, mood, kws, cap, reason in SLOT_TEMPLATE:
        if need and not item.get(need):
            continue
        # what 只有 1 段时，功能段中和段末合并成一个槽
        if anchor == "what_mid" and len(what) < 2:
            continue
        n += 1
        sid = f"{art_key}_s{n}"
        old = old_slots.get(sid) or {}
        slots.append({
            "id": sid,
            "anchor": anchor,
            "label": ANCHOR_LABEL.get(anchor, anchor),
            "type": old.get("type") or typ,
            "mood": mood,
            "reason": reason,
            "keywords": old.get("keywords") or list(kws),
            "caption": old.get("caption", cap),
            "chosen": old.get("chosen") or "",
            "candidates": old.get("candidates") or [],
        })
    return {"slug": item.get("slug") or item["full_name"].split("/")[-1],
            "name": item.get("zh_name") or item["full_name"],
            "slots": slots}


def cmd_plan(args=None):
    issue = _load(os.path.join(D, "data", "issue.json"), None)
    if not issue:
        log("[!] 没有 data/issue.json，先跑 digest run")
        return 1
    old = load_plan()
    out = {}
    for idx, it in enumerate([issue.get("main")] + (issue.get("shorts") or []), 1):
        if not it.get("deep"):
            continue
        key = f"a{idx}"
        out[key] = _plan_article(key, it, old.get(key))
    save_plan(out)
    total = sum(len(a["slots"]) for a in out.values())
    log(f"[ok] 槽位计划：{len(out)} 篇共 {total} 个配图槽位 → data/images.json")
    for key, art in out.items():
        n_cand = sum(len(s["candidates"]) for s in art["slots"])
        log(f"  {key} {art['name'][:18]}：{len(art['slots'])} 槽，已搜候选 {n_cand} 张")
    return 0


def _find_slot(plan, sid):
    for key, art in plan.items():
        for s in art["slots"]:
            if s["id"] == sid:
                return art, s
    return None, None


# ---------------------------------------------------------------- 搜索：必应图片

def _http_get(url, timeout=20, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _sniff(data):
    """按文件头判断图片类型。微信不收 webp，遇到直接弃。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:4] in (b"GIF8", b"gif8"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _bing_images(kw, want):
    """必应图片搜索，返回 [(murl, purl), ...]。不依赖 API key。

    async 接口和普通搜索页都把元数据以 HTML 转义 JSON 的形式内嵌在页面里
    （murl=原图地址, purl=来源页），两个都试，凑够候选为止。
    """
    q = urllib.parse.quote(kw)
    urls = [
        f"https://www.bing.com/images/async?q={q}&first=1&count=35&mmasync=1",
        f"https://cn.bing.com/images/search?q={q}&form=HDRSC2&first=1",
        f"https://www.bing.com/images/search?q={q}&form=HDRSC2&first=1",
    ]
    got, seen = [], set()
    for u in urls:
        try:
            text = _http_get(u, timeout=15).decode("utf-8", "ignore")
        except Exception:
            continue
        murls = re.findall(r'murl&quot;:&quot;(.*?)&quot;', text)
        purls = re.findall(r'purl&quot;:&quot;(.*?)&quot;', text)
        if not murls:
            murls = re.findall(r'"murl":"(.*?)"', text)
            purls = re.findall(r'"purl":"(.*?)"', text)
        for i, mu in enumerate(murls):
            mu = mu.replace("\\u0026", "&").replace("\\/", "/")
            pu = purls[i] if i < len(purls) else ""
            pu = pu.replace("\\u0026", "&").replace("\\/", "/")
            if not mu.startswith(("http://", "https://")) or mu in seen:
                continue
            # 必应自家缩略图和 webp 不要
            if "bing.com/th" in mu or mu.lower().endswith(".webp"):
                continue
            seen.add(mu)
            got.append((mu, pu))
            if len(got) >= want * 4:
                return got
    return got


def _download_candidate(url, referer, dest_base, min_kb=10, max_mb=8):
    """下载一个候选。返回 (相对 data/ 的路径, bytes) 或 (None, 0)。

    过滤口径：小于 10KB 的大多是图标和残图，大于 8MB 的贴进编辑器会卡。
    """
    try:
        data = _http_get(url, timeout=25, referer=referer)
    except Exception:
        return None, 0
    ext = _sniff(data)
    if ext == "webp" or ext is None:
        return None, 0
    if not (min_kb * 1024 <= len(data) <= max_mb * 1024 * 1024):
        return None, 0
    path = dest_base + "." + ext
    with open(path, "wb") as f:
        f.write(data)
    return path, len(data)


def cmd_search_real(args):
    plan = load_plan()
    art, slot = _find_slot(plan, args.slot)
    if not slot:
        log(f"[!] 没有槽位 {args.slot}，先跑 plan")
        return 1
    kw = (args.kw or "").strip()
    if kw and kw not in (slot.get("keywords") or []):
        slot.setdefault("keywords", []).insert(0, kw)
    else:
        kw = (slot.get("keywords") or ["表情包"])[0]
    art_dir = os.path.join(IMG_DIR, slot["id"].split("_")[0])
    os.makedirs(art_dir, exist_ok=True)
    log(f"[..] 搜「{kw}」→ 槽位 {slot['id']}（{slot['type']} · {slot['label']}）")
    got = _bing_images(kw, args.n)
    if not got:
        log("[!] 必应没返回图片，换关键词再试")
        return 1
    cands = []
    for mu, pu in got:
        if len(cands) >= args.n:
            break
        key = "ABC"[len(cands)]
        rel, size = _download_candidate(
            mu, pu, os.path.join(art_dir, f"{slot['id']}_{key}"))
        if not rel:
            continue
        cands.append({
            "key": key,
            "path": "images/" + os.path.relpath(rel, IMG_DIR).replace("\\", "/"),
            "src_url": mu,
            "src_page": pu,
            "keyword": kw,
            "license": LICENSE_BY_TYPE.get(slot["type"], "来源待确认"),
            "bytes": size,
        })
        log(f"  候选 {key}：{size//1024}KB  {os.path.basename(rel)}")
    if not cands:
        log("[!] 一张都没下来（防盗链或全是 webp），换个关键词")
        return 1
    # 重新搜就把旧候选清掉，键位 A/B/C 连续
    slot["candidates"] = cands
    save_plan(plan)
    log(f"[ok] {slot['id']} 现有 {len(cands)} 张候选")
    return 0


# ---------------------------------------------------------------- 搜索：仓库截图

README_NAMES = ["README.md", "README.zh-CN.md", "readme.md", "Readme.md",
                "README_zh.md", "README_zh-CN.md", "README-CN.md"]


def _fetch_readme(full_name):
    for br in ("main", "master"):
        for name in README_NAMES:
            url = f"https://raw.githubusercontent.com/{full_name}/{br}/{name}"
            try:
                return _http_get(url, timeout=15).decode("utf-8", "ignore"), br
            except Exception:
                continue
    # raw 全 404 时退 API（格式化接口，匿名也行）
    try:
        url = f"https://api.github.com/repos/{full_name}/readme"
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/vnd.github.raw"})
        with urllib.request.urlopen(req, timeout=15) as r:
            import base64
            return base64.b64decode(json.loads(r.read())["content"]).decode("utf-8", "ignore"), ""
    except Exception:
        return None, None


def _readme_images(md, full_name, br):
    """抽 README 里的图片地址：markdown 图 + html <img>，相对路径还原成 raw 地址。"""
    urls = re.findall(r"!\[[^\]]*\]\((\S+?)(?:\s+\"[^\"]*\")?\)", md or "")
    urls += re.findall(r'<img[^>]+?src=["\']([^"\']+)["\']', md or "")
    out, seen = [], set()
    for u in urls:
        u = u.strip()
        if u.startswith("http"):
            if "shields.io" in u or "badge" in u.lower() or "img.shields" in u:
                continue  # 徽章不算截图
        elif u.startswith("/"):
            u = f"https://raw.githubusercontent.com/{full_name}/{br}{u}"
        else:
            u = f"https://raw.githubusercontent.com/{full_name}/{br}/{u}"
        if u in seen or u.endswith((".svg", ".webp")):
            continue
        seen.add(u)
        out.append(u)
    return out


def cmd_search_repo(args):
    """软件截图必须真实：直接从项目仓库 README 里抓原图当候选。"""
    plan = load_plan()
    art, slot = _find_slot(plan, args.slot)
    if not slot:
        log(f"[!] 没有槽位 {args.slot}")
        return 1
    issue = _load(os.path.join(D, "data", "issue.json"), {})
    full_name = None
    for it in [issue.get("main")] + (issue.get("shorts") or []):
        if it.get("slug") == art["slug"] or (it.get("zh_name") or it["full_name"]) == art["name"]:
            full_name = it["full_name"]
            break
    if not full_name:
        log("[!] 槽位没对上文章，检查 images.json 的 slug/name")
        return 1
    md, br = _fetch_readme(full_name)
    if not md:
        log(f"[!] 拉不到 {full_name} 的 README")
        return 1
    imgs = _readme_images(md, full_name, br or "main")
    if not imgs:
        log("[!] README 里没有可用截图，这个槽建议换表情包或人工截图")
        return 1
    art_dir = os.path.join(IMG_DIR, slot["id"].split("_")[0])
    os.makedirs(art_dir, exist_ok=True)
    cands = []
    for u in imgs:
        if len(cands) >= args.n:
            break
        key = "ABC"[len(cands)]
        rel, size = _download_candidate(
            u, f"https://github.com/{full_name}",
            os.path.join(art_dir, f"{slot['id']}_{key}"))
        if not rel:
            continue
        cands.append({
            "key": key,
            "path": "images/" + os.path.relpath(rel, IMG_DIR).replace("\\", "/"),
            "src_url": u,
            "src_page": f"https://github.com/{full_name}",
            "keyword": "仓库 README 原图",
            "license": LICENSE_BY_TYPE.get(slot["type"], "来源待确认"),
            "bytes": size,
        })
        log(f"  候选 {key}：{size//1024}KB  {os.path.basename(rel)}")
    if not cands:
        log("[!] README 图片没一张下得来（防盗链/格式问题），改用人工截图")
        return 1
    slot["candidates"] = cands
    save_plan(plan)
    log(f"[ok] {slot['id']} 现有 {len(cands)} 张候选（仓库真实截图）")
    return 0


# ---------------------------------------------------------------- 审核页

_REVIEW_JS = """
function collect(){
  var out={},rs=document.querySelectorAll('input[type=radio]:checked');
  rs.forEach(function(r){ if(r.value!=='') out[r.name]=r.value; });
  return out;
}
function copyPicks(){
  var s=JSON.stringify(collect(),null,1);
  var ta=document.createElement('textarea');
  ta.value=s;document.body.appendChild(ta);ta.select();
  try{document.execCommand('copy');}catch(e){}
  document.body.removeChild(ta);
  var ok=document.getElementById('ok');
  ok.style.opacity=1;setTimeout(function(){ok.style.opacity=0;},1800);
}
"""


def _review_slot(art_key, slot, preselect=True):
    cands = slot.get("candidates") or []
    head = (f'<section style="margin:22px 0;padding:16px 18px;background:#ffffff;'
            f'border:1px solid #e8e8e4;border-radius:10px;">'
            f'<p style="margin:0 0 2px 0;font-size:16px;font-weight:bold;color:#1a1a1a;">'
            f'{slot["id"]} · {slot["label"]} —— {slot["type"]}'
            + (f'（{slot["mood"]}）' if slot.get("mood") else "")
            + '</p>'
            f'<p style="margin:0 0 12px 0;font-size:13px;color:#888;line-height:1.7;">'
            f'为什么在这配图：{slot["reason"]}</p>')
    if not cands:
        head += ('<p style="margin:0;font-size:14px;color:#ba3b28;">'
                 '［还没搜候选 —— 告诉 AI 关键词或让它按建议词搜］</p></section>')
        return head
    chosen = slot.get("chosen") or ("A" if preselect else "")
    rows = ['<section style="display:flex;gap:12px;flex-wrap:wrap;">']
    for c in cands:
        checked = "checked" if chosen == c["key"] else ""
        rows.append(
            f'<label style="flex:1 1 200px;max-width:260px;cursor:pointer;">'
            f'<input type="radio" name="{slot["id"]}" value="{c["key"]}" {checked} '
            f'style="margin-right:6px;">'
            f'<span style="font-weight:bold;color:#1a1a1a;">候选 {c["key"]}</span>'
            f'<img src="../{c["path"]}" style="display:block;width:100%;margin:6px 0;'
            f'border-radius:8px;border:1px solid #eee;">'
            f'<span style="font-size:11px;color:#999;line-height:1.6;display:block;'
            f'word-break:break-all;">搜词：{c.get("keyword","")}<br>'
            f'{c.get("bytes",0)//1024}KB · 来源：'
            f'<a href="{c.get("src_page","")}" style="color:#666;">{c.get("src_url","")[:60]}</a><br>'
            f'版权：{c.get("license","待确认")}</span></label>')
    rows.append(
        f'<label style="flex:1 1 200px;max-width:260px;cursor:pointer;">'
        f'<input type="radio" name="{slot["id"]}" value="" '
        + ("" if chosen else "checked") +
        f' style="margin-right:6px;"><span style="color:#888;">跳过（这处不放图）</span>'
        f'<span style="display:block;margin-top:8px;font-size:40px;">🚫</span></label>')
    rows.append("</section></section>")
    return head + "".join(rows)


def cmd_review(args=None):
    plan = load_plan()
    if not plan:
        log("[!] 没有槽位计划，先跑 plan")
        return 1
    parts = []
    for art_key, art in plan.items():
        n = sum(1 for s in art["slots"] if s.get("chosen"))
        n_c = sum(len(s.get("candidates") or []) for s in art["slots"])
        parts.append(
            f'<section style="margin:40px 0 6px 0;">'
            f'<p style="margin:0;font-size:20px;font-weight:bold;color:#1a1a1a;">'
            f'{art_key} · {art["name"]}</p>'
            f'<p style="margin:0;font-size:13px;color:#888;">'
            f'{len(art["slots"])} 个槽位 · 已搜 {n_c} 张候选 · 已选定 {n} 张 —— '
            f'不合适的槽选「跳过」，不确定就留给 AI 换关键词重搜</p></section>')
        for s in art["slots"]:
            parts.append(_review_slot(art_key, s))
    page = (
        '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>本期文章 · 配图素材审核</title></head>'
        '<body style="margin:0;background:#f4f4f0;font-family:-apple-system,'
        '\'PingFang SC\',\'Microsoft YaHei\',sans-serif;">'
        '<section style="max-width:900px;margin:0 auto;padding:20px 16px 80px 16px;">'
        '<section style="position:sticky;top:0;z-index:9;background:#1a1a1a;'
        'border-radius:10px;padding:14px 18px;margin-bottom:18px;'
        'display:flex;align-items:center;justify-content:space-between;">'
        '<p style="margin:0;color:#eaeaea;font-size:15px;font-weight:bold;">'
        '📷 本期文章 · 配图素材审核</p>'
        '<section style="text-align:right;">'
        '<button onclick="copyPicks()" style="background:#3ddc97;color:#10231a;'
        'border:0;border-radius:6px;padding:10px 18px;font-size:14px;'
        'font-weight:bold;cursor:pointer;">复制选择结果（JSON）</button>'
        '<span id="ok" style="color:#3ddc97;font-size:12px;margin-left:10px;'
        'opacity:0;">已复制，粘贴回对话即可</span></section></section>'
        + "".join(parts) +
        '<p style="margin:30px 4px;color:#999;font-size:12px;line-height:1.8;">'
        '选完点右上角按钮复制 JSON，贴回对话让 AI 应用；改主意可以随时重挑再复制。'
        '表情包来自网络搜索，版权状态见每张图下方标注，发布前请过一眼。</p>'
        '</section><script>' + _REVIEW_JS + '</script></body></html>')
    os.makedirs(REPORTS, exist_ok=True)
    out = os.path.join(REPORTS, "images_review.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    log(f"[ok] 审核页 → data/reports/images_review.html")
    return 0


# ---------------------------------------------------------------- 应用选择

def cmd_apply(args):
    plan = load_plan()
    if args.auto:
        changed = 0
        for art in plan.values():
            for s in art["slots"]:
                cands = s.get("candidates") or []
                if cands and not s.get("chosen"):
                    s["chosen"] = cands[0]["key"]
                    changed += 1
        save_plan(plan)
        log(f"[ok] 预选完成：{changed} 个槽位填了第一张候选（审核页可随时改）")
        return 0
    picks = {}
    if args.picks:
        picks = json.loads(args.picks)
    elif args.picks_file:
        with open(args.picks_file, encoding="utf-8") as f:
            picks = json.load(f)
    if not picks:
        log("[!] 没有选择内容：--picks '{...}' 或 --auto")
        return 1
    hit = miss = 0
    for art in plan.values():
        for s in art["slots"]:
            if s["id"] in picks:
                v = picks[s["id"]]
                keys = [c["key"] for c in s.get("candidates") or []]
                if v == "" or v in keys:
                    s["chosen"] = v
                    hit += 1
                else:
                    log(f"[!] {s['id']} 没有 {v} 号候选（现有 {keys}）")
                    miss += 1
    save_plan(plan)
    log(f"[ok] 应用 {hit} 个选择" + (f"，{miss} 个无效" if miss else ""))
    return 0


def cmd_list(args=None):
    plan = load_plan()
    if not plan:
        log("[!] 没有计划，先跑 plan")
        return 1
    for art_key, art in plan.items():
        log(f"\n{art_key} {art['name']}")
        for s in art["slots"]:
            cands = s.get("candidates") or []
            mark = f"已选 {s['chosen']}" if s.get("chosen") else (
                f"{len(cands)} 候选待选" if cands else "待搜")
            log(f"  {s['id']}  {s['label']:<6} {s['type']:<4} {mark}")
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser(description="配图系统")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan", help="生成/刷新槽位计划")
    sub.add_parser("list", help="查看槽位与候选状态")
    p = sub.add_parser("search", help="按关键词搜候选（槽位语境）")
    p.add_argument("--slot", required=True)
    p.add_argument("--kw", default="")
    p.add_argument("--n", type=int, default=3)
    p = sub.add_parser("search-repo", help="从仓库 README 抓真实截图当候选")
    p.add_argument("--slot", required=True)
    p.add_argument("--n", type=int, default=3)
    sub.add_parser("review", help="生成配图审核页")
    p = sub.add_parser("apply", help="应用选择结果")
    p.add_argument("--picks", default="")
    p.add_argument("--picks-file", default="")
    p.add_argument("--auto", action="store_true", help="每槽预选第一张候选")
    args = ap.parse_args()
    fn = {"plan": cmd_plan, "list": cmd_list, "search": cmd_search_real,
          "search-repo": cmd_search_repo, "review": cmd_review, "apply": cmd_apply}
    sys.exit(fn[args.cmd](args) or 0)


if __name__ == "__main__":
    main()
