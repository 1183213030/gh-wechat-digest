"""主色主题：一个词切换，正文强调色 + 浅色块 + 封面底色全套跟着换。

为什么不让用户去改 render.py 里的常量：主色不是单个色值，它带一串派生色
（引用块底的淡色、链接位虚线框、坑块的灰边、封面上的深底和亮强调色）。
手改一处、忘一处，出来的稿子就会花。这里按一个 accent 算出整组派生色，
渲染前 apply 一次，正文和封面拿到的是同一套。

用法（代码里）：
    import theme
    theme.resolve("brick")        # 预设名
    theme.resolve("#2f4a8c")      # 任意 hex
    theme.resolve(None)           # 回默认

用法（命令行）：
    python scripts/digest.py theme                     # 看现在用什么、有哪些预设
    python scripts/digest.py theme green               # 换预设
    python scripts/digest.py theme "#2f4a8c"           # 换自定义色
    python scripts/digest.py theme --preview           # 出一张配色对照图
"""
import re

# 预设：名字取日常色名，label 给中文。note 是给用户挑色时看的场景说明。
PRESETS = {
    "brick": {
        "label": "砖红",
        "accent": "#ba3b28",
        "note": "已发文章同款。偏纸感的暗红，长文里当强调色不刺眼。",
    },
    "inkgreen": {
        "label": "墨绿",
        "accent": "#1f6f4a",
        "note": "技术号的稳妥选择，冷静、耐看，和绿底封面同族。",
    },
    "indigo": {
        "label": "靛蓝",
        "accent": "#2f4a8c",
        "note": "偏工程感，适合工具/开源类内容，白底上很清晰。",
    },
    "amber": {
        "label": "琥珀",
        "accent": "#9a5f12",
        "note": "暖调但不是红，适合「挖到宝」的口气，注意别配太亮的黄。",
    },
    "plum": {
        "label": "梅紫",
        "accent": "#743a58",
        "note": "少见、有辨识度，偏内容号；大面积用会显闷，只做强调正好。",
    },
    "graphite": {
        "label": "石墨",
        "accent": "#43505a",
        "note": "几乎无彩的冷灰蓝，最克制。想彻底不留「营销感」时用。",
    },
}
DEFAULT = "brick"


# ---------------------------------------------------------------- 颜色计算

def _rgb(h):
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in rgb)


def mix(a, b, t):
    """a 与 b 按 t 混（t=0 全 a，t=1 全 b）。"""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def light(c, t):
    return mix(c, "#ffffff", t)


def dark(c, t):
    return mix(c, "#000000", t)


def lum(h):
    """相对亮度，用来判断强调色放到深底上够不够亮。"""
    def f(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = _rgb(h)
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def readable_on_dark(accent, target=0.42):
    """深色封面上要用的强调色：不够亮就往白里提，提够了就停。"""
    c = accent
    for i in range(41):
        if lum(c) >= target:
            return c
        c = light(accent, i * 0.02)
    return c


def is_hex(s):
    return bool(re.fullmatch(r"#?[0-9a-fA-F]{6}", (s or "").strip()))


# 语言色：GitHub linguist 的主语言色，正文强调色用它当种子。
# 用户的原则是「每篇的配色跟文章主题走」，最稳定的「主题信号」就是仓库主语言——
# Python 蓝调、Rust 橙调、Kotlin 紫……每个语言一挂上色，一期的四篇自然就各有性格。
# 注意 linguist 原色很多太荧光（Shell 的绿、JS 的黄），进正文前都要过 tune() 压一压。
LANG_COLORS = {
    "Python": "#3572A5", "Kotlin": "#A97BFF", "TypeScript": "#3178C6",
    "JavaScript": "#C79A15", "Rust": "#B4713E", "Go": "#0089A8",
    "Java": "#B07219", "C": "#555555", "C++": "#C13B66", "C#": "#178600",
    "Shell": "#3E9649", "HTML": "#C2431D", "CSS": "#7A5CB0", "Vue": "#359468",
    "Dart": "#00948F", "PHP": "#5C6BA1", "Ruby": "#9B1B30", "Swift": "#C74535",
    "Lua": "#4C4C9E", "Jupyter Notebook": "#C2520E", "Zig": "#C69A00",
    "MDX": "#2A56A5", "Markdown": "#2A56A5", "Blade": "#9E5C2E",
}

# 正文强调色的亮度区间：太亮像高亮笔，太暗发闷。砖红/墨绿/靛蓝都在这个带里。
# 上限要压得比较狠：蓝紫色的蓝光通道亮度权重小，0.30 的亮紫看起来还是像粉笔，
# 0.24 以下才会沉下来。
LUM_MIN, LUM_MAX = 0.09, 0.24


def tune(h):
    """把任意颜色拉进正文强调色可用的亮度带。

    linguist 的语言色直接当强调色大多不行：JS 的黄、Shell 的绿亮度 0.6+，
    白底上一大片像荧光笔。往黑里压（亮度高）或往白里提（太暗），调到带内就停。
    饱和度高的荧光感也会随压暗一起降下来。
    """
    c = h
    if lum(c) > LUM_MAX:
        for i in range(60):
            c = dark(h, i * 0.03)
            if lum(c) <= LUM_MAX:
                return c
        return dark(h, 0.9)
    if lum(c) < LUM_MIN:
        for i in range(60):
            c = light(h, i * 0.03)
            if lum(c) >= LUM_MIN:
                return c
        return light(h, 0.6)
    return h


def for_article(item, fallback=None):
    """单篇的主题色，优先级：手动 theme 字段 > 主语言推导 > 账号主色。

    item 里的 theme 写预设名（indigo）或色值（#2f4a8c）都行，来自 write.json
    的 articles 段——某篇想用内容主题色（比如 rea-video 用紫），写一句就换。
    """
    spec = (item.get("theme") or "").strip() if isinstance(item, dict) else ""
    lang = ((item.get("lang") or "").strip() if isinstance(item, dict) else "")
    if spec and (spec.lower() in PRESETS or is_hex(spec)):
        p = resolve(spec)
        p["label"] = f"{p['label']}（手指定）"
        return p
    if lang in LANG_COLORS:
        p = resolve(tune(LANG_COLORS[lang]))
        p["label"] = f"{lang}系"
        p["note"] = f"按主语言 {lang} 推导：{LANG_COLORS[lang]} → {p['accent']}"
        return p
    return resolve(fallback)


# ---------------------------------------------------------------- 解析

def resolve(spec=None):
    """把「预设名 / #hex / 空」解析成一整套颜色。

    返回 dict：
      accent        强调色（小节编号、金句、链接、抬头）
      soft          浅色块底（链接位、提示块）
      quote_bg      引用块底（比 soft 更淡）
      hairline      浅边线（坑块左条）
      cover_bg1/2   封面深底（两个端点做渐变）
      cover_accent  封面上的强调色（已在深底上校验过亮度）
      cover_dim     封面次要文字色
      label/name    中文名与原始串
    """
    raw = (spec or "").strip()
    name, label, note = "", "", ""
    if not raw:
        raw = DEFAULT
    key = raw.lower()

    if key in PRESETS:
        accent = PRESETS[key]["accent"]
        name, label, note = key, PRESETS[key]["label"], PRESETS[key]["note"]
    elif is_hex(raw):
        accent = "#" + raw.lstrip("#").lower()
        name, label, note = accent, "自定义", "自定义主色"
    else:
        accent = PRESETS[DEFAULT]["accent"]
        name = DEFAULT
        label = PRESETS[DEFAULT]["label"]
        note = PRESETS[DEFAULT]["note"] + f"（没认出「{raw}」，用回默认）"

    # 正文用：淡底只带一点色相，避免大面积染色
    accent_light = readable_on_dark(accent)
    return {
        "name": name,
        "label": label,
        "note": note,
        "accent": accent,
        "soft": mix(accent, "#ffffff", 0.93),
        "quote_bg": mix(accent, "#ffffff", 0.962),
        "hairline": mix(accent, "#ffffff", 0.72),
        "cover_bg1": mix(accent, "#0a0a0a", 0.86),
        "cover_bg2": mix(accent, "#000000", 0.94),
        "cover_accent": accent_light,
        "cover_dim": mix(accent_light, mix(accent, "#0a0a0a", 0.86), 0.5),
    }


def current_spec(profile):
    """profile.json 里的 theme 字段，兼容直接写 accent 色值。"""
    if not isinstance(profile, dict):
        return None
    return profile.get("theme") or profile.get("accent")


def choices():
    """给命令行列表用。"""
    return [(k, v["label"], v["accent"], v["note"]) for k, v in PRESETS.items()]


# ---------------------------------------------------------------- 对照预览

def preview_html(specs=None):
    """把几套主色排在一张纸上，出的图能直接给用户挑。

    每张卡都放同样的元素（栏目抬头 / 标题 / 定位句 / 引用块 / 编号小节 /
    链接位 / 金句），这样才能看出差别到底在哪儿，而不是只比色块。
    """
    specs = specs or list(PRESETS.keys())
    cards = []
    for sp in specs:
        p = resolve(sp)
        cur = " 当前" if sp == spec_field_default else ""
        cards.append(f"""
    <div style="background:#ffffff;border:1px solid #e6e2da;border-radius:12px;
                padding:20px 20px 18px 20px;box-shadow:0 1px 4px rgba(0,0,0,.05);">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:14px;">
        <span style="display:inline-block;width:14px;height:14px;border-radius:50%;
                     background:{p['accent']};"></span>
        <span style="font-size:15px;font-weight:700;color:#1a1a1a;">{p['label']}</span>
        <span style="font-family:Consolas,monospace;font-size:11px;color:#a09a90;">
          {p['accent']}{cur}</span>
      </div>

      <p style="margin:0 0 10px 0;font-size:11px;letter-spacing:2px;font-weight:700;
                color:{p['accent']};">GITHUB 开源观察 · 第 01 期</p>

      <p style="margin:0 0 10px 0;font-size:17px;font-weight:700;color:#141414;
                line-height:1.5;">他写了个软件把开机广告删了</p>

      <section style="margin:0 0 12px 0;padding:9px 12px;background:{p['quote_bg']};
                      border-left:3px solid {p['accent']};border-radius:0 6px 6px 0;">
        <p style="margin:0;font-size:12px;line-height:1.7;color:#555555;">
          一句话说清：装个 App，电视开机不再看广告。</p>
      </section>

      <p style="margin:0 0 10px 0;font-size:14px;font-weight:700;color:#1a1a1a;">
        <span style="color:{p['accent']};">01｜</span>它替你省掉哪件烦事</p>

      <p style="margin:0 0 12px 0;font-size:12px;line-height:1.75;color:#333333;">
        每天开机那 15 秒，遥控器按不掉。这个项目直接在系统层把广告位断了。</p>

      <section style="margin:0 0 10px 0;padding:8px 10px;border:1px dashed {p['accent']};
                      border-radius:6px;background:{p['soft']};">
        <p style="margin:0;font-size:12px;font-weight:700;color:{p['accent']};">
          → 点这里看全文</p>
      </section>

      <p style="margin:0;font-size:12px;font-weight:700;color:{p['accent']};
                line-height:1.7;">说句实话：它不免责，出事自己担。</p>
    </div>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>body{{margin:0;}}</style></head>
<body style="margin:0;background:#f4f2ee;padding:34px 30px 30px 30px;
             font-family:'Microsoft YaHei','PingFang SC',sans-serif;">
  <p style="margin:0 0 6px 0;font-size:22px;font-weight:700;color:#1a1a1a;">
    主色对照 · 同一个版式，只换强调色</p>
  <p style="margin:0 0 24px 0;font-size:13px;color:#8a8378;line-height:1.7;">
    砖红是已发文章在用的；其余五套是备选。看的时候注意三处：栏目抬头、编号小节、金句段。</p>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:18px;">
    {"".join(cards)}
  </div>
</body></html>"""


# 预览时标「当前」用；由调用方在渲染前设一下即可，不必传参
spec_field_default = DEFAULT
