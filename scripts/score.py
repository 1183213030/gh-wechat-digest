"""公众号口径的四维打分。

跟「能不能变现」那套不一样，这里排序的是「读者愿不愿意点开、看完、转出去」：
  有用 30 · 好讲 25 · 可演示 20 · 没被写烂 25

硬淘汰照旧：归档、星太少、awesome 合集、破解/盗版类。
"""
import re
from datetime import datetime, timezone

BUZZ = ["blazing", "next-gen", "revolutionary", "seamless", "empower", "ai-powered",
        "enterprise-grade", "cutting-edge", "赋能", "一站式", "全链路", "底层逻辑"]
CONTRAST = ["不用", "无需", "告别", "替代", "丢进去", "一键", "零配置", "离线", "本地运行",
            "instead of", "without", "no need", "offline", "self-hosted", "local-first",
            "replace", "one command", "single binary"]
KILL = ["awesome", "curated list", "collection of", "roadmap", "interview", "leetcode",
        "学习笔记", "读书笔记", "教程合集", "面试题", "课程资料"]
PIRATE = ["crack", "keygen", "nulled", "torrent", "pirated", "bypass paywall",
          "破解", "盗版", "激活码", "白嫖", "免登录破解"]

APP_LANG = {"TypeScript", "JavaScript", "Python", "Kotlin", "Swift", "Dart",
            "Vue", "Svelte", "Java", "C#", "Lua"}
HEAVY_LANG = {"C", "C++", "CUDA", "Assembly", "Rust", "Go"}


def _age_days(created):
    if not created:
        return None
    try:
        t = datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - t).days
    except Exception:
        return None


def form_of(p):
    """给读者看的形态，决定文案里「怎么用」那段的写法。"""
    lang = p.get("lang") or ""
    desc = (p.get("desc") or "").lower()
    topics = " ".join(p.get("topics") or []).lower()
    name = p.get("name", "").lower()
    blob = f"{desc} {topics} {name}"
    if any(k in blob for k in ("cli", "command-line", "terminal", "命令行")):
        return "命令行"
    if any(k in blob for k in ("vs code", "vscode", "extension", "plugin", "插件")):
        return "插件"
    if any(k in blob for k in ("skill", "agent", "mcp")):
        return "Agent 技能"
    if any(k in blob for k in ("macos app", "desktop", "electron", "tauri", "windows app")):
        return "桌面应用"
    if lang in ("Kotlin", "Swift", "Dart") or any(k in blob for k in ("android", "ios", "iphone")):
        return "手机/电视 App"
    if any(k in blob for k in ("http", "api", "sdk", "framework", "library", "engine")):
        return "引擎/库"
    return "网页应用"


def hard_kill(p, readme_text=""):
    """返回淘汰原因，None 表示留下。"""
    blob = ((p.get("desc") or "") + " " + (p.get("name") or "")).lower()
    if p.get("archived"):
        return "已归档"
    if (p.get("stars") or 0) < 200:
        return "星数不足 200，需求没被验证"
    if any(k in blob for k in KILL):
        return "awesome/合集类，跑不起来"
    if any(k in blob for k in PIRATE):
        return "疑似破解/盗版，不能发"
    if p.get("size_kb") and p["size_kb"] > 900 * 1024:
        return "仓库超过 900MB，写稿时截图和读懂都费劲"
    return None


def score(p, readme_text=""):
    """返回 (总分, 明细dict)。明细给报告里的编辑看，不印给读者。"""
    d = {}
    desc = p.get("desc") or ""
    low = desc.lower()
    readme = readme_text or ""
    age = _age_days(p.get("created_at"))
    p["_age_days"] = age
    p["form"] = form_of(p)

    # ---------------- 有用 30
    u = 0
    if p.get("homepage"):
        u += 8                      # 有官网 = 读者能立刻试
    if re.search(r"(^|\n)\s*(##+\s*(install|安装|getting started|quick ?start|usage))", readme, re.I):
        u += 7                      # 有安装/上手段
    if p.get("lang") in APP_LANG:
        u += 6                      # 应用层语言，普通人装得上
    elif p.get("lang") in HEAVY_LANG:
        u += 2
    if len(p.get("topics") or []) >= 3:
        u += 4
    if (p.get("size_kb") or 999999) < 30 * 1024:
        u += 5                      # 体积小，装起来不折腾
    d["有用"] = min(u, 30)

    # ---------------- 好讲 25
    s = 0
    if desc and len(desc) <= 140 and not any(b in low for b in BUZZ):
        s += 8                      # 一句话说得清，没堆 buzzword
    if re.search(r"[\u4e00-\u9fa5]", desc):
        s += 6                      # 作者自己写了中文，等于送你标题
    if any(c in low for c in CONTRAST):
        s += 6                      # 有反差：不用/替代/一键
    st = p.get("stars") or 0
    if 800 <= st <= 30000:
        s += 5                      # 够有分量，又还没到人人都写过
    elif st > 30000:
        s += 1
    d["好讲"] = min(s, 25)

    # ---------------- 可演示 20
    v = 0
    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    imgs += re.findall(r'<img[^>]+src="([^"]+)"', readme, re.I)
    if len(imgs) >= 2:
        v += 9                      # 作者自己配了图，省你截图
    elif len(imgs) == 1:
        v += 5
    if re.search(r"(demo|preview|screenshot|演示|截图|\.gif)", readme, re.I):
        v += 5
    if p.get("homepage"):
        v += 6                      # 有在线 demo 最好演示
    d["可演示"] = min(v, 20)

    # ---------------- 没被写烂 25
    f = 0
    if age is not None:
        if age <= 30:
            f += 16
        elif age <= 90:
            f += 12
        elif age <= 365:
            f += 7
        else:
            f += 2
    if p.get("source") == "trending" and (p.get("gained") or 0) > 800:
        f -= 6                      # 当天狂涨 = 全网的号都在写它，撞题
    if p.get("source") == "new":
        f += 4
    d["没被写烂"] = max(0, min(f, 25))

    total = sum(d.values())
    d["total"] = total
    return total, d


def velocity(p):
    """星速，用来标「刚冒头」还是「老底」。"""
    age = p.get("_age_days")
    if not age or age < 1:
        return 0
    return round((p.get("stars") or 0) / max(age, 1), 1)


def suspect(p):
    """建号不到半年、日均涨 700+ 星，多半是被大 V 转了一次，先别当真需求。"""
    age = p.get("_age_days")
    return bool(age and age < 180 and velocity(p) > 700)
