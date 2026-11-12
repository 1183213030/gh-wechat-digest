"""gh-wechat-digest · GitHub 公众号选题台

用法
  python scripts/digest.py doctor          体检：token、额度、trending 可达
  python scripts/digest.py run             抓池子 → 打分 → 组一期 → 出待写清单
  python scripts/digest.py todo            看还差哪些段落需要人（Agent）写
  python scripts/digest.py apply           读 data/write.json，覆盖规则文案
  python scripts/digest.py render          出可粘贴的 HTML + md + 配图清单
  python scripts/digest.py log --url ...   记一条发布记录（以后统计用）
  python scripts/digest.py history         看发过的期数和项目
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))

import cover  # noqa: E402
import deploy  # noqa: E402
import render  # noqa: E402
import score as scorer  # noqa: E402
import sources  # noqa: E402

D = os.path.join(HERE, "data")
P_POOL = os.path.join(D, "pool.json")
P_ISSUE = os.path.join(D, "issue.json")
P_TODO = os.path.join(D, "todo_write.json")
P_WRITE = os.path.join(D, "write.json")
P_STATE = os.path.join(D, "state.json")
P_SEEN = os.path.join(D, "seen.json")
P_PUB = os.path.join(D, "published.json")
REPORTS = os.path.join(D, "reports")
COVERS = os.path.join(D, "covers")

COOLDOWN_DAYS = 30
MAIN_MIN = 55          # 主打最低分，低于这个宁可这期少一个
SHORT_MIN = 40


def log(m=""):
    print(m, flush=True)


def today():
    return datetime.now().strftime("%Y-%m-%d")


def load(p, default=None):
    return sources.load_json(p, default if default is not None else {})


def save(p, o):
    sources.save_json(p, o)


# ---------------------------------------------------------------- 体检

def cmd_doctor(args):
    log("[*] 体检中（几个请求，约 5 秒）...\n")
    ok = True
    log(f"OK  Python {sys.version.split()[0]}")
    try:
        import requests  # noqa: F401
        log(f"OK  requests {requests.__version__}")
    except Exception:
        log("!!  缺 requests：pip install requests")
        ok = False

    token, where = sources.find_token()
    log(("OK  token  " + where) if token else "!!  token 未配置（匿名，每小时 60 次，够跑一期）")
    rl = sources.rate_left(token)
    if rl:
        log(f"OK  API 额度  核心 {rl['core']}/60，搜索 {rl['search']}/10")
    tr = sources.trending("daily")
    log(f"{'OK' if tr else '!!'}  trending  今日榜 {len(tr)} 条" +
        ("" if tr else "（抓不到就是页面结构变了）"))
    if not tr:
        ok = False

    st = load(P_STATE)
    log(f"OK  期号  已出 {st.get('issue_no', 0)} 期 · 上次 {st.get('last_date', '—')}")
    log("\n结论：" + ("能跑。直接 python scripts/digest.py run" if ok else "先解决上面标 !! 的项。"))
    return 0 if ok else 1


# ---------------------------------------------------------------- 抓 + 选

def _dedupe(items):
    seen, out = set(), []
    for it in items:
        fn = it.get("full_name")
        if not fn or fn.lower() in seen:
            continue
        seen.add(fn.lower())
        out.append(it)
    return out


def cmd_run(args):
    token, where = sources.find_token()
    args._token = bool(token)
    log(f"[*] token：{where}")

    pool = []
    tr_d = sources.trending("daily")
    log(f"[*] trending 今日 {len(tr_d)} 条")
    tr_w = sources.trending("weekly")
    log(f"[*] trending 本周 {len(tr_w)} 条")
    new = sources.search_new(days=args.days, min_stars=args.min_stars, token=token, per_page=25)
    log(f"[*] 近 {args.days} 天新建高星 {len(new)} 条")
    hot = sources.search_hot(days=7, min_stars=1500, token=token, per_page=20)
    log(f"[*] 老项目活跃 {len(hot)} 条")

    pool = _dedupe(tr_d + tr_w + new + hot)
    for x in pool:                      # 纯字符串，不花额度，先给所有候选补上
        x["og"] = sources.og_image(x["full_name"])
        x["url"] = sources.repo_url(x["full_name"])
    log(f"[*] 去重后池子 {len(pool)} 个")

    # 补数据。关键：搜索接口返回的记录本身就带建库时间/许可证/主页/体积，
    # 只有 trending 来的缺这些，才需要打 core API。README 走 raw，完全不吃额度。
    cap = args.detail_cap or (26 if token else 22)
    order = sorted(pool, key=lambda x: x.get("stars") or 0, reverse=True)[:cap]
    n_detail = 0
    for i, p in enumerate(order, 1):
        if p.get("source") == "trending" or not p.get("created_at"):
            d = sources.detail(p["full_name"], token)
            if d:
                n_detail += 1
            p.update({k: v for k, v in d.items() if v not in (None, "", [])})
        p["readme"] = sources.readme(p["full_name"], token, p.get("default_branch") or "main")
        p["og"] = sources.og_image(p["full_name"])
        p["url"] = sources.repo_url(p["full_name"])
        if i % 6 == 0:
            log(f"    ...详情 {i}/{len(order)}")
    log(f"    补详情 {n_detail} 次（core 额度），README {sum(1 for x in order if x.get('readme'))} 份")

    # 已推过的先标出来
    seen = load(P_SEEN)
    for p in pool:
        rec = seen.get(p["full_name"])
        p["_seen_times"] = rec["times"] if rec else 0
        p["_last"] = rec["last"] if rec else ""

    save(P_POOL, {"date": today(), "mode": "token" if token else "匿名", "items": pool})
    log(f"[*] 池子落盘 -> data/pool.json")

    args._token = bool(token)
    _pick(args, pool, seen)
    return 0


def _fresh_enough(p):
    last = p.get("_last")
    if not last:
        return True
    try:
        d = datetime.strptime(last, "%Y-%m-%d")
    except Exception:
        return True
    return (datetime.now() - d).days >= COOLDOWN_DAYS


def _pick(args, pool, seen):
    dropped = []
    keep = []
    for p in pool:
        why = scorer.hard_kill(p, p.get("readme", ""))
        if why:
            dropped.append({"full_name": p["full_name"], "why": why})
            continue
        total, br = scorer.score(p, p.get("readme", ""))
        p["score"], p["breakdown"] = total, br
        p["velocity"] = scorer.velocity(p)
        p["suspect"] = scorer.suspect(p)
        if (p.get("stars") or 0) > 30000 and p.get("_seen_times"):
            dropped.append({"full_name": p["full_name"], "why": "大项目且推过，没有新角度"})
            continue
        keep.append(p)

    keep.sort(key=lambda x: x["score"], reverse=True)

    def take(n, used_owner, used_form):
        out = []
        for p in keep:
            if len(out) >= n:
                break
            if not _fresh_enough(p) and not args.allow_repeat:
                continue
            if p["owner"].lower() in used_owner:
                continue
            if used_form.get(p["form"], 0) >= 2:
                continue
            if p["score"] < args.min_score:
                continue
            out.append(p)
            used_owner.add(p["owner"].lower())
            used_form[p["form"]] = used_form.get(p["form"], 0) + 1
        return out

    used_owner, used_form = set(), {}
    picks = take(1 + args.shorts, used_owner, used_form)
    if not picks or picks[0]["score"] < MAIN_MIN and not args.force:
        log(f"[!] 没挑出够格的主打（最高 {keep[0]['score'] if keep else 0} 分 < {MAIN_MIN}）。"
            f"换 --days 7 或 --min-stars 200 再看，或者 --force 硬出一期。")
        if not args.force:
            save(P_POOL, {"date": today(), "dropped": dropped, "picked": []})
            return

    main, shorts = picks[0], picks[1:]
    issue = _draft(args, main, shorts, pool, dropped)
    save(P_ISSUE, issue)
    save(P_POOL, {"date": today(), "mode": "token" if args._token else "匿名",
                  "dropped": dropped, "picked": [x["full_name"] for x in picks],
                  "items": pool})
    _write_todo(issue)
    log(f"\n[OK] 本期：1 主打 + {len(shorts)} 短评 -> data/issue.json")
    log(f"     主打：{main['full_name']}（{main['score']} 分 / {main['form']}）")
    for s in shorts:
        log(f"     短评：{s['full_name']}（{s['score']} 分）")
    log(f"[!] 现在全是规则文案，发出去像模板。跑 python scripts/digest.py todo 看要补哪几段。")


# ---------------------------------------------------------------- 规则版文案（只是骨架）

TITLE_TPL = [
    "GitHub 上这 {n} 个项目，解决的都是又小又烦的事",
    "星星多不等于好用：这 {n} 个开源项目值得试",
    "这 {n} 个开源项目，装起来都不费劲",
    "GitHub 开源观察：这 {n} 个项目，普通人也能用上",
]
INTRO_TPL = [
    "先说清楚：这是看完仓库和文档之后的判断，不是实测结论 —— 哪个你装了，欢迎回来补一句真实体验。",
]


PAIN_TPL = {
    "命令行": "烦的从来不是难，是每次都要重新拼一遍参数。这个东西把那条命令固化成一句话。",
    "插件": "你本来就天天开那个窗口，顺手装一个，等于给已经开着的东西加个零件。",
    "Agent 技能": "让 AI 干活最烦的是它每次都从零理解你的口味。这类技能就是提前把口味写给它。",
    "桌面应用": "装完就是个普通软件，双击就走，不用配环境 —— 这是它敢给你用最大的理由。",
    "手机/电视 App": "它不是让你多学一个工具，是替掉你手机上那个一直在弹广告的。",
    "引擎/库": "自己用不上，但你要是接活或者做产品，这东西能替你省掉小半个月。",
    "网页应用": "不用装、不用登录，打开链接就能试 —— 这是决定我要不要写它的第一道门槛。",
}


def _first_sentence(t):
    t = re.sub(r"\s+", " ", (t or "").strip())
    for sep in ["。", ". ", "；", ";", "|"]:
        if sep in t:
            return t.split(sep)[0].strip() + ("。" if sep == "。" else "")
    return t


def _extract_steps(readme, name):
    """从 README 里捞能直接照抄的命令，最多 3 条。"""
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", readme or "", re.S)
    cmds = []
    for b in blocks:
        for line in b.strip().splitlines():
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            if re.match(r"^(\$|>|pip|npm|pnpm|yarn|bun|git clone|docker|brew|cargo|go |uv |python|npx|curl|wget)", s):
                s = re.sub(r"^\$\s*", "", s)
                cmds.append(s)
    out = []
    for c in cmds:
        if c not in out:
            out.append(c)
    return out[:3]


def _verdict(p):
    clues = []
    if not p.get("homepage"):
        clues.append("没官网，纯靠 README，对非技术读者不太友好")
    if not re.search(r"[\u4e00-\u9fa5]", p.get("desc") or ""):
        clues.append("全英文，中文资料还没人写")
    oi, st = p.get("open_issues") or 0, p.get("stars") or 1
    if st and oi / st > 0.05:
        clues.append(f"issue 有 {oi} 个，说明用的人多但也说明坑不少")
    if (p.get("size_kb") or 0) > 100 * 1024:
        clues.append("仓库有点大，第一次拉会等一会儿")
    if p.get("suspect"):
        clues.append("星涨得太快，可能是被大 V 带了一波，真实用户在不在还要看两周")
    if not clues:
        clues.append("暂时没发现明显的坑，作者更新也勤")
    return "；".join(clues[:2]) + "。"


def _meta_rows(p):
    rows = []
    if p.get("lang"):
        rows.append(["语言", p["lang"]])
    if p.get("license"):
        rows.append(["许可证", p["license"]])
    if p.get("stars"):
        rows.append(["star", f"{p['stars']:,}"])
    if p.get("_age_days") is not None:
        rows.append(["建库", f"{p['_age_days']} 天"])
    return rows


def _readme_paras(readme, n=3, minlen=36):
    """从 README 里抠出能当正文的段落。只留中文段 —— 英文段落放进中文文章很出戏。"""
    t = readme or ""
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"^\s*\|.*$", "", t, flags=re.M)
    t = re.sub(r"^\s*#{1,6}\s*.*$", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*>\s?", "", t, flags=re.M)
    paras = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"\n\s*\n", t)]
    out = [x for x in paras if len(x) >= minlen and re.search(r"[\u4e00-\u9fa5]", x)]
    return out[:n]


def _why_now(p):
    age = p.get("_age_days")
    if p.get("source") == "new" or (age is not None and age <= 30):
        return f"建库才 {age or '<30'} 天就有 {p.get('stars', 0):,} star，中文圈还没人写，属于捡漏窗口。"
    if p.get("source") == "trending":
        g = p.get("gained") or 0
        return f"今天单日涨了 {g:,} star，说明刚有人在用；但这类项目一上 trending，一周内会有十几篇撞题，要写就趁现在。"
    return f"已经沉淀到 {p.get('stars', 0):,} star，坑被踩完了、文档也全，做二创最省事。"


P_PROFILE = os.path.join(D, "profile.json")


def _build_menu(main, shorts):
    """本期看点：一行一个，用短句不用仓库名。"""
    def cut(t, n=34):
        """按标点断句，别把「AI」切成「A…」。"""
        t = re.sub(r"\s+", " ", t or "").strip()
        if len(t) <= n:
            return t
        head = t[:n]
        for sep in ["、", "，", "：", "；", " ", "。"]:
            i = head.rfind(sep)
            if i >= n // 2:
                return head[:i]
        return head + "…"

    def one(x):
        name = x.get("zh_name") or x["full_name"]
        line = x.get("kicker") or x.get("one_liner") or ""
        return f"{name} —— {cut(line)}" if line else name

    return [one(main)] + [one(s) for s in shorts]


def _next_issue_no():
    """期号以发布记录为准：发过几期就接几，不从 01 重来。
    今天已经出过稿但还没发，就沿用今天那个号，重跑不跳号。"""
    pub = load(P_PUB, {"items": []})
    nos = [int(x.get("issue_no") or 0) for x in (pub.get("items") or [])]
    st = load(P_STATE)
    if st.get("last_date") == today() and st.get("issue_no"):
        return int(st["issue_no"])
    return (max(nos) if nos else 0) + 1


def _pick_rotating(pool, issue_no, fallback=""):
    """结尾/互动按号轮换，别每期都同一句。"""
    pool = [x for x in (pool or []) if x]
    if not pool:
        return fallback
    return pool[(issue_no - 1) % len(pool)]


def _draft(args, main, shorts, pool, dropped):
    n = 1 + len(shorts)
    prof0 = load(P_PROFILE)
    issue_no = _next_issue_no()

    def pack(p, is_main):
        slug = p["full_name"].split("/")[-1].replace(".", "-").lower()
        d = {
            "full_name": p["full_name"],
            "slug": slug,
            "zh_name": p.get("name"),
            "one_liner": _first_sentence(p.get("desc")),
            "url": p.get("url"),
            "stars": p.get("stars"),
            "lang": p.get("lang"),
            "form": p["form"],
            "score": p["score"],
            "og": p.get("og"),
            "deep": False,
            "kicker": "",
            "lead": _first_sentence(p.get("desc")),
            "summary": [p.get("desc") or ""],
            "teaser": "",
            "figure_caption": f"{p['full_name']} · {p['form']}",
            "_auto": True,
        }
        # 深挖用的兜底：AI 提示词是规则生成也能用，正文段落只是占位
        d.update({
            "ai_prompt": deploy.prompt_tv(d, "<电视IP>") if p["form"] in ("电视/Android", "手机/电视 App")
                        else deploy.prompt_for(d),
            "ai_prompt_label": "复制下面这段，发给能操作你电脑的 AI",
            "manual": _extract_steps(p.get("readme", ""), p.get("name", "")),
            "what": _readme_paras(p.get("readme", ""), 2),
        })
        if is_main:
            d.update({
                "why_now": _why_now(p),
                "pain": PAIN_TPL.get(p["form"], PAIN_TPL["网页应用"]),
                "steps": _extract_steps(p.get("readme", ""), p.get("name", "")),
                "verdict": _verdict(p),
            })
        else:
            d["verdict"] = _verdict(p)
        return d

    tpl = TITLE_TPL[issue_no % len(TITLE_TPL)].format(n=n)
    prof = prof0
    packed = [pack(main, True)] + [pack(s, False) for s in shorts]
    # 出几篇单篇：默认全部（用户要的是"每个项目一篇"），--deep 0 也是全部
    dcount = len(packed) if (args.deep or 0) <= 0 else min(args.deep, len(packed))
    for x in packed[:dcount]:
        x["deep"] = True
        x["link_label"] = f"{x.get('zh_name') or x['full_name']}（完整安装步骤）"
    issue = {
        "date": today(),
        "issue_no": issue_no,
        "first_issue": issue_no <= 1,
        "profile": prof,
        "menu": _build_menu(packed[0], packed[1:]),
        "title": tpl,
        "intro": [INTRO_TPL[0].format(i=1)],
        "main": packed[0],
        "shorts": packed[1:],
        "ending": [_pick_rotating(prof0.get("ending_pool"), issue_no)],
        "cta": _pick_rotating(prof0.get("cta_pool"), issue_no),
        "stats": {"pool": len(pool), "mode": "token" if load(P_POOL).get("mode") == "token" else "匿名抓取"},
        "dropped": dropped[:12],
    }
    return issue


# ---------------------------------------------------------------- 待写清单

DEEP_FIELDS = ["kicker", "lead", "what", "pain", "check", "ai_why", "ai_prompt",
               "ai_follow", "manual", "first", "pits", "fit", "unfit", "verdict"]
DEEP_OPTIONAL = ["meta", "teaser", "summary", "ai_warn", "manual_title", "manual_note"]


def _fields_of(item, is_main):
    if item.get("deep"):
        # 出了单篇的，导读只留摘要 + 钩子，正文全在单篇里
        return ["kicker", "summary", "teaser"]
    return (["zh_name", "one_liner", "why_now", "pain", "steps", "verdict"]
            if is_main else ["zh_name", "one_liner", "verdict"])


def _write_todo(issue):
    items = []
    for key in ["main"]:
        it = issue[key]
        if not it.get("_auto"):
            continue
        items.append({"which": "main", "full_name": it["full_name"],
                      "form": it["form"], "score": it["score"],
                      "desc": it.get("one_liner"), "need": _fields_of(it, True),
                      "fill": {k: "" for k in _fields_of(it, True)}})
    for i, s in enumerate(issue.get("shorts") or [], 1):
        if not s.get("_auto"):
            continue
        items.append({"which": f"short{i}", "full_name": s["full_name"],
                      "form": s["form"], "score": s["score"],
                      "desc": s.get("one_liner"), "need": _fields_of(s, False),
                      "fill": {k: "" for k in _fields_of(s, False)}})
    arts = []
    for i, it in enumerate([issue["main"]] + (issue.get("shorts") or []), 1):
        if not it.get("deep"):
            continue
        arts.append({
            "which": f"article{i}", "slug": it.get("slug"), "full_name": it["full_name"],
            "zh_name": it.get("zh_name") or it["full_name"],
            "need": DEEP_FIELDS, "optional": DEEP_OPTIONAL,
            "fill": {k: "" for k in DEEP_FIELDS},
        })
    save(P_TODO, {"issue": issue["date"], "count": len(items) + len(arts),
                  "items": items, "articles": arts,
                  "_说明": "把 fill 里每个字段写成给人看的中文，存成 data/write.json，"
                           "然后 python scripts/digest.py apply"})


def cmd_pick(args):
    """不重新抓，直接从池子里点名组一期。公式不如你的判断，看到好的就指出来。"""
    data = load(P_POOL)
    pool = data.get("items") or []
    if not pool:
        log("[!] 没有池子，先跑 run")
        return 1
    for x in pool:
        if x.get("score") is None:
            t, b = scorer.score(x, x.get("readme", ""))
            x["score"], x["breakdown"] = t, b
            x["form"] = x.get("form") or scorer.form_of(x)
            x["velocity"] = scorer.velocity(x)
            x["suspect"] = scorer.suspect(x)
    for x in pool:
        x["og"] = x.get("og") or sources.og_image(x["full_name"])
        x["url"] = x.get("url") or sources.repo_url(x["full_name"])
    by = {x["full_name"].lower(): x for x in pool}

    main = by.get((args.main or "").lower())
    if not main:
        log(f"[!] 池子里没有 {args.main}。可用的有：")
        for x in sorted(pool, key=lambda i: -(i.get("score") or 0))[:15]:
            log(f"    {x['full_name']}  {x.get('score')} 分")
        return 1

    shorts = []
    for fn in (args.shorts or "").split(","):
        fn = fn.strip().lower()
        if not fn:
            continue
        if fn not in by:
            log(f"[!] 跳过（池子里没有）：{fn}")
            continue
        if by[fn] is main:
            continue
        shorts.append(by[fn])

    issue = _draft(args, main, shorts, pool, data.get("dropped") or [])
    save(P_ISSUE, issue)
    save(P_POOL, {**data, "picked": [main["full_name"]] + [x["full_name"] for x in shorts],
                  "items": pool})
    _write_todo(issue)
    log(f"[OK] 本期：{main['full_name']}（主打）+ {len(shorts)} 短评")
    log("[!] 文案还是规则版，跑 todo 看要补哪几段。")
    return 0


def cmd_todo(args):
    if not os.path.exists(P_ISSUE):
        log("[!] 还没有本期稿件，先跑 run")
        return 1
    issue = load(P_ISSUE)
    _write_todo(issue)
    todo = load(P_TODO)
    if not todo["count"]:
        log("这期文案全是人写的，没有规则兜底的段落。直接 render 就能发。")
        return 0
    log(f"本期 {todo['count']} 个位置要写：\n")
    for it in todo["items"]:
        log(f"[{it['which']}] {it['full_name']}（{it['form']} · {it['score']} 分）")
        log(f"    现在：{it['desc']}")
        log(f"    要写：{'、'.join(it['need'])}\n")
    if todo.get("articles"):
        log(f"\n另有 {len(todo['articles'])} 篇单篇要写（每篇 {len(DEEP_FIELDS)} 个字段）：\n")
        for a in todo["articles"]:
            log(f"[{a['which']}] {a['zh_name']}（{a['full_name']}）")
            log(f"    必写：{'、'.join(a['need'])}")
            log(f"    可选：{'、'.join(a['optional'])}\n")
    log("清单已存 data/todo_write.json。写完存 data/write.json 再 apply。")
    return 0


def cmd_apply(args):
    if not os.path.exists(P_WRITE):
        log(f"[!] 没找到 {P_WRITE}，先按 todo 写一份")
        return 1
    issue = load(P_ISSUE)
    w = load(P_WRITE)
    idx = {"main": issue["main"]}
    for i, s in enumerate(issue.get("shorts") or [], 1):
        idx[f"short{i}"] = s
    by_name = {v["full_name"]: v for v in idx.values()}

    n = 0
    for it in w.get("items", []):
        tgt = idx.get(it.get("which") or "") or by_name.get(it.get("full_name") or "")
        if not tgt:
            continue
        # 两种写法都收：{which, fill:{...}} 和 {which, 字段直接铺平}
        payload = it.get("fill") or {k: v for k, v in it.items()
                                     if k not in ("which", "full_name", "fill")}
        for k, v in payload.items():
            if v not in (None, "", [], {}):
                tgt[k] = v
                n += 1
        tgt["_auto"] = False
    if w.get("title"):
        issue["title"] = w["title"]
    if w.get("intro"):
        issue["intro"] = w["intro"]
    if w.get("ending"):
        issue["ending"] = w["ending"]
    if w.get("cta"):
        issue["cta"] = w["cta"]
    # 目录跟着项目走：文案改完重新生成，避免还挂着仓库英文名
    if w.get("menu"):
        issue["menu"] = w["menu"]
    else:
        issue["menu"] = _build_menu(issue["main"], issue.get("shorts") or [])
    if w.get("guide"):
        issue["guide"] = w["guide"]
    if w.get("header_lines"):
        issue["profile"] = {**(issue.get("profile") or {}), "intro_lines": w["header_lines"]}
    if w.get("read_note"):
        issue["read_note"] = w["read_note"]

    # 链接位的文字跟着「改完之后的标题」走，别还挂着仓库名
    for x in [issue["main"]] + (issue.get("shorts") or []):
        if x.get("deep"):
            x["link_label"] = f"{x.get('zh_name') or x['full_name']}（完整安装步骤）"

    # 单篇正文
    na = 0
    arts = w.get("articles") or []
    by_slug = {it.get("slug"): it for it in [issue["main"]] + (issue.get("shorts") or [])}
    for a in arts:
        tgt = by_slug.get(a.get("slug")) or by_name.get(a.get("full_name") or "")
        if not tgt:
            continue
        for k, v in a.items():
            if k in ("slug", "full_name", "which"):
                continue
            if v not in (None, "", [], {}):
                tgt[k] = v
                na += 1
        tgt["_auto"] = False
    save(P_ISSUE, issue)
    left = sum(1 for v in idx.values() if v.get("_auto"))
    log(f"[OK] 写回 {n} 个字段" + (f"，单篇 {na} 个字段" if na else ""))
    log("还有 {} 个位置是规则文案{}".format(
        left, "，跑 todo 看看" if left else "，可以 render 了"))
    return 0


# ---------------------------------------------------------------- 出稿

def cmd_render(args):
    issue = load(P_ISSUE)
    if not issue:
        log("[!] 没有稿件，先跑 run")
        return 1
    issue["date"] = issue.get("date") or today()
    txt = json.dumps(issue, ensure_ascii=False)
    issue["word_count"] = len(re.findall(r"[\u4e00-\u9fa5]", txt))
    made, p_fig, p_link = render.write_files(issue, REPORTS)

    st = load(P_STATE)
    st["issue_no"] = issue["issue_no"]
    st["last_date"] = issue["date"]
    save(P_STATE, st)

    # 记账：进冷却，下次不再推
    seen = load(P_SEEN)
    for it in [issue["main"]] + (issue.get("shorts") or []):
        rec = seen.get(it["full_name"]) or {"times": 0, "first": issue["date"]}
        if rec.get("last") != issue["date"]:
            rec["times"] = rec.get("times", 0) + 1
        rec["last"] = issue["date"]
        seen[it["full_name"]] = rec
    save(P_SEEN, seen)

    auto = sum(1 for it in [issue["main"]] + (issue.get("shorts") or []) if it.get("_auto"))
    log(f"[OK] 出了 {len(made)} 篇：")
    for tag, title, h, m in made:
        log(f"  {tag:6s} {title[:30]:32s} {os.path.basename(h)}")
    # 封面：每篇 2.35:1 + 1:1，浏览器渲染，不用装任何图像库
    if not args.no_cover:
        covers, cerr = cover.build(issue, COVERS)
        if cerr:
            log(f"\n[!] 封面没生成：{cerr}")
        elif covers:
            _append_covers(p_fig, covers)
            log(f"     封面 {len(covers)} 张 -> data/covers/")

    log(f"\n     配图清单 -> {os.path.basename(p_fig)}")
    log(f"     链接清单 -> {os.path.basename(p_link)}")
    if auto:
        log(f"\n[!] 还有 {auto} 个位置是规则文案。发之前先 todo → 写 → apply → render。")
    else:
        log("\n全部人写的，可以发了。顺序：先发单篇拿链接 → 再发导读插链接。")
    return 0


def _append_covers(p_fig, covers):
    """封面段写进配图清单。重跑时替换旧段，不叠两遍。"""
    sec = "\n== 封面（后台单独上传，每篇两张：首图 2.35:1 + 次条/转发 1:1）==\n" \
          + "".join(f"[{tag}] {cp}\n" for tag, cp, _ in covers)
    try:
        cur = open(p_fig, encoding="utf-8").read()
    except OSError:
        cur = ""
    if "== 封面" in cur:
        cur = re.split(r"\n== 封面", cur)[0].rstrip("\n")
    with open(p_fig, "w", encoding="utf-8") as f:
        f.write(cur + sec)


def cmd_cover(args):
    """单独重出封面（改了文案 / 换了主题之后用）。"""
    issue = load(P_ISSUE)
    if not issue:
        log("[!] 没有稿件，先跑 run")
        return 1
    covers, cerr = cover.build(issue, COVERS)
    if cerr:
        log(f"[!] {cerr}")
        return 1
    p_fig = os.path.join(REPORTS, f"issue_{issue.get('date') or today()}_配图清单.txt")
    if covers and os.path.exists(p_fig):
        _append_covers(p_fig, covers)
    log(f"[OK] 封面 {len(covers)} 张 -> data/covers/")
    for tag, cp, note in covers:
        log(f"  {tag:4s} {os.path.basename(cp)}")
    return 0


# ---------------------------------------------------------------- 记账

def cmd_log(args):
    pub = load(P_PUB, {"items": []})
    issue = load(P_ISSUE)
    rec = {
        "date": issue.get("date") or today(),
        "issue_no": issue.get("issue_no"),
        "title": issue.get("title"),
        "url": args.url or "",
        "reads": args.reads or 0,
        "items": [issue["main"]["full_name"]] +
                 [s["full_name"] for s in (issue.get("shorts") or [])] if issue else [],
    }
    pub["items"] = [x for x in pub["items"] if x.get("issue_no") != rec["issue_no"]]
    pub["items"].append(rec)
    save(P_PUB, pub)
    log(f"[OK] 记下第 {rec['issue_no']} 期：{rec['title']}")
    return 0


def cmd_history(args):
    pub = load(P_PUB, {"items": []})
    if not pub["items"]:
        log("还没发过。出完稿用 log --url 记一条。")
        return 0
    log(f"共 {len(pub['items'])} 期\n")
    for r in sorted(pub["items"], key=lambda x: x.get("date", "")):
        log(f"{r['date']} · 第 {r.get('issue_no','?')} 期 · 阅读 {r.get('reads',0)}")
        log(f"  {r.get('title','')}")
        for it in r.get("items", []):
            log(f"    - {it}")
    seen = load(P_SEEN)
    log(f"\n账本里存了 {len(seen)} 个项目，{COOLDOWN_DAYS} 天内不会再推。")
    return 0


# ---------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser(description="GitHub 公众号选题台")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("doctor")
    p = sub.add_parser("run")
    p.add_argument("--days", type=int, default=30, help="新建项目的回看天数")
    p.add_argument("--min-stars", type=int, default=400, dest="min_stars")
    p.add_argument("--shorts", type=int, default=3, help="短评个数")
    p.add_argument("--min-score", type=int, default=SHORT_MIN, dest="min_score")
    p.add_argument("--detail-cap", type=int, default=0, dest="detail_cap")
    p.add_argument("--allow-repeat", action="store_true", dest="allow_repeat")
    p.add_argument("--force", action="store_true", help="分不够也硬出一期")
    p.add_argument("--deep", type=int, default=0,
                   help="出几篇单篇深挖（默认 0 = 每个项目都出一篇）")

    p = sub.add_parser("pick")
    p.add_argument("--main", required=True, help="主打项目 owner/repo")
    p.add_argument("--shorts", default="", help="其余项目，逗号分隔的 owner/repo")
    p.add_argument("--deep", type=int, default=0, help="出几篇单篇（0 = 全部）")
    sub.add_parser("todo")
    sub.add_parser("apply")
    p = sub.add_parser("render")
    p.add_argument("--no-cover", action="store_true", help="跳过封面生成")
    p = sub.add_parser("cover")
    p.add_argument("--out", default="")
    p = sub.add_parser("log")
    p.add_argument("--url", default="")
    p.add_argument("--reads", type=int, default=0)
    sub.add_parser("history")

    args = ap.parse_args()
    if not args.cmd:
        ap.print_help()
        return 0
    fn = {"doctor": cmd_doctor, "run": cmd_run, "pick": cmd_pick, "todo": cmd_todo, "apply": cmd_apply,
          "render": cmd_render, "cover": cmd_cover,
          "log": cmd_log, "history": cmd_history}[args.cmd]
    return fn(args) or 0


if __name__ == "__main__":
    sys.exit(main())
