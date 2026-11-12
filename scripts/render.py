"""把一期稿件渲成一组文章：1 篇导读 + N 篇单项目深挖。

每篇都出 html（带「复制正文」按钮）和 md（兜底），另外出三份清单：
配图清单、待插链接清单、发布顺序说明。

微信的硬约束，代码里全部照着做了：
  · 不用 <style>/class，所有样式 inline 写在标签上（微信会丢弃样式表）
  · 不用 flex/grid/float，只用 section 嵌套 + padding
  · 正文里的图片不能外链，所以只放「图占位框」，图片要你在编辑器里手动插入
  · 正文链接点不动 —— 指向自己公众号文章的链接只能用编辑器里的「链接」按钮插，
    所以这里只输出「链接位」占位框，粘贴后人工替换
"""
import html
import os

C_TEXT = "#2f2f2f"
C_SUB = "#8c8c8c"
C_ACCENT = "#1F6F4A"
C_LINE = "#e8e4dc"
C_CODE_BG = "#f7f7f3"
FONT = ('-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",'
        '"Microsoft YaHei",sans-serif')
MONO = 'Consolas,Menlo,"Courier New",monospace'


def esc(s):
    return html.escape(str(s or ""), quote=False)


# ---------------------------------------------------------------- 小块

def para(text, color=C_TEXT, size="16px", weight="400", mt="0", mb="16px", align="left", lh="1.8"):
    return (f'<p style="margin:{mt} 0 {mb} 0;font-size:{size};line-height:{lh};'
            f'color:{color};font-weight:{weight};text-align:{align};letter-spacing:0.4px;">'
            f'{text}</p>')


def quote(text):
    """左侧竖线的引文块，用来放「一句话说清」。"""
    return (f'<section style="border-left:3px solid {C_ACCENT};padding:2px 0 2px 12px;'
            f'margin:0 0 18px 0;">'
            f'<p style="margin:0;font-size:16px;line-height:1.75;color:{C_TEXT};'
            f'letter-spacing:0.4px;">{esc(text)}</p></section>')


def section_title(text, num=""):
    badge = ""
    if num:
        badge = (f'<span style="display:inline-block;min-width:22px;height:22px;'
                 f'line-height:22px;text-align:center;border-radius:4px;'
                 f'background:{C_ACCENT};color:#ffffff;font-size:13px;'
                 f'font-weight:700;margin-right:8px;">{esc(num)}</span>')
    return (f'<section style="margin:34px 0 14px 0;">'
            f'<p style="margin:0;font-size:19px;font-weight:700;color:#1a1a1a;'
            f'line-height:1.6;letter-spacing:0.3px;">{badge}{esc(text)}</p></section>')


def sub_title(text):
    """深挖文章里的小节标题，比 section_title 轻一档。"""
    return (f'<section style="margin:28px 0 10px 0;">'
            f'<p style="margin:0;font-size:17px;font-weight:700;color:#1a1a1a;'
            f'line-height:1.6;letter-spacing:0.3px;">{esc(text)}</p>'
            f'<span style="display:inline-block;width:28px;height:2px;'
            f'background:{C_ACCENT};margin-top:6px;"></span></section>')


def figure(full_name, caption="", compact=False):
    """图占位框。微信正文不收外链图，所以这里只给占位 + 可直接拖的地址。"""
    url = f"https://opengraph.githubassets.com/1/{full_name}"
    cap = f'<br><span style="color:{C_SUB};font-size:12px;">{esc(caption)}</span>' if caption else ""
    pad = "12px 12px" if compact else "22px 14px"
    mb = "12px" if compact else "20px"
    tip = "［ 这里放一张图 ］" if compact else "［ 这里放图：保存下面网址的图片，删掉本框拖进来 ］"
    return (f'<section style="margin:14px 0 {mb} 0;padding:{pad};'
            f'border:1px dashed #cfc9bd;border-radius:6px;background:#fbfaf7;'
            f'text-align:center;">'
            f'<p style="margin:0 0 4px 0;font-size:13px;color:#8c8c8c;line-height:1.6;">'
            f'{tip}{cap}</p>'
            f'<p style="margin:0;font-size:11px;color:#b0a99c;line-height:1.6;'
            f'word-break:break-all;">{esc(url)}</p></section>')


def kv_row(k, v):
    return (f'<p style="margin:0 0 6px 0;font-size:15px;line-height:1.75;color:{C_TEXT};'
            f'letter-spacing:0.3px;"><span style="color:{C_SUB};">{esc(k)}</span>'
            f'&nbsp;&nbsp;{esc(v)}</p>')


def steps_block(steps):
    if not steps:
        return ""
    out = ['<section style="margin:0 0 16px 0;padding:14px 16px;background:#f6f7f4;'
           'border-radius:6px;">',
           f'<p style="margin:0 0 8px 0;font-size:13px;color:{C_ACCENT};'
           f'font-weight:700;letter-spacing:1px;">三步用起来</p>']
    for i, s in enumerate(steps, 1):
        out.append(f'<p style="margin:0 0 6px 0;font-size:15px;line-height:1.75;'
                   f'color:{C_TEXT};letter-spacing:0.3px;">'
                   f'<span style="color:{C_ACCENT};font-weight:700;">{i}.</span>&nbsp;'
                   f'{esc(s)}</p>')
    out.append("</section>")
    return "".join(out)


def verdict_block(text):
    if not text:
        return ""
    return (f'<section style="margin:0 0 18px 0;padding:12px 14px;'
            f'background:#fdf6ec;border-radius:6px;">'
            f'<p style="margin:0;font-size:15px;line-height:1.75;color:#7a4b16;'
            f'letter-spacing:0.3px;"><span style="font-weight:700;">说句实话 · </span>'
            f'{esc(text)}</p></section>')


def link_line(url, stars="", lang=""):
    meta = " · ".join([x for x in [f"{stars:,} star" if stars else "", lang] if x])
    meta_html = (f'<span style="color:{C_SUB};font-size:13px;">（{esc(meta)}）</span>'
                 if meta else "")
    return (f'<p style="margin:0 0 8px 0;font-size:14px;line-height:1.75;'
            f'color:{C_ACCENT};word-break:break-all;letter-spacing:0.2px;">'
            f'{esc(url)}{meta_html}</p>')


def divider():
    return (f'<section style="margin:30px 0;text-align:center;">'
            f'<span style="display:inline-block;width:36px;height:1px;'
            f'background:{C_LINE};"></span></section>')


def code_block(lines, label=""):
    """可复制的命令 / 提示词块。

    不用 <pre>：微信编辑器对 pre 的 white-space 处理不可靠，粘完容易挤成一行。
    这里一行一个 <p>，即使样式被剥掉，换行也还在。
    """
    if not lines:
        return ""
    out = ['<section style="margin:0 0 18px 0;padding:14px 14px;'
           f'background:{C_CODE_BG};border:1px solid #eae6dd;border-radius:6px;">']
    if label:
        out.append(f'<p style="margin:0 0 8px 0;font-size:12px;color:{C_ACCENT};'
                   f'letter-spacing:1px;font-weight:700;">{esc(label)}</p>')
    for ln in lines:
        body = esc(ln) if str(ln).strip() else "&nbsp;"
        out.append(f'<p style="margin:0 0 3px 0;font-size:14px;line-height:1.7;'
                   f'color:#2b2b2b;font-family:{MONO};word-break:break-word;">{body}</p>')
    out.append("</section>")
    return "".join(out)


def bullet_list(items, marker="·"):
    if not items:
        return ""
    out = []
    for it in items:
        out.append(f'<p style="margin:0 0 8px 0;font-size:15px;line-height:1.8;'
                   f'color:{C_TEXT};letter-spacing:0.3px;">'
                   f'<span style="color:{C_ACCENT};">{esc(marker)}</span>&nbsp;{esc(it)}</p>')
    return "".join(out)


def pit_list(pits):
    """坑：一条一个「小标题 + 说明」，别写成大段。"""
    if not pits:
        return ""
    out = []
    for i, p in enumerate(pits, 1):
        if isinstance(p, (list, tuple)):
            head, body = p[0], p[1]
        else:
            head, body = "", p
        out.append('<section style="margin:0 0 12px 0;padding:12px 14px;'
                   'background:#faf9f6;border-left:3px solid #d9d2c4;border-radius:0 4px 4px 0;">')
        if head:
            out.append(f'<p style="margin:0 0 4px 0;font-size:15px;font-weight:700;'
                       f'color:#1a1a1a;line-height:1.7;">{i}. {esc(head)}</p>')
        out.append(f'<p style="margin:0;font-size:15px;line-height:1.8;color:#5a5a5a;'
                   f'letter-spacing:0.3px;">{esc(body)}</p></section>')
    return "".join(out)


def hint_block(title, lines, tone="green"):
    """提示块：适合谁 / 不适合谁 / 一期怎么读。"""
    if not lines:
        return ""
    bg = "#f2f7f3" if tone == "green" else "#fbf7f2"
    fg = C_ACCENT if tone == "green" else "#8a6a2f"
    body = "".join(f'<p style="margin:0 0 6px 0;font-size:15px;line-height:1.8;'
                   f'color:{C_TEXT};letter-spacing:0.3px;">{esc(x)}</p>' for x in lines)
    return (f'<section style="margin:0 0 16px 0;padding:14px 16px;background:{bg};'
            f'border-radius:6px;">'
            f'<p style="margin:0 0 8px 0;font-size:13px;font-weight:700;color:{fg};'
            f'letter-spacing:1px;">{esc(title)}</p>{body}</section>')


def link_slot(label="", note="发布后在这里插入超链接"):
    """指向自己公众号另一篇文章的入口占位。

    微信正文里的 <a> 会被过滤，能点的只有编辑器「链接」按钮插的站内文章，
    所以这里输出一个显眼的占位框，粘贴完在编辑器里选中它替换成链接。
    """
    return (f'<section style="margin:6px 0 20px 0;padding:14px 16px;'
            f'border:1px dashed {C_ACCENT};border-radius:6px;background:#f4f8f5;">'
            f'<p style="margin:0 0 4px 0;font-size:15px;font-weight:700;color:{C_ACCENT};'
            f'line-height:1.7;">→ {esc(label or "点这里看全文")}</p>'
            f'<p style="margin:0;font-size:12px;color:{C_SUB};line-height:1.6;">'
            f'［{esc(note)}］</p></section>')


def index_note(lines):
    """导读顶部的「这期怎么读」。"""
    if not lines:
        return ""
    body = "".join(f'<p style="margin:0 0 8px 0;font-size:15px;line-height:1.85;'
                   f'color:#3a3a3a;letter-spacing:0.3px;">{esc(x)}</p>' for x in lines)
    return ('<section style="margin:0 0 22px 0;padding:16px 16px;background:#f6f7f4;'
            'border-radius:6px;">'
            f'<p style="margin:0 0 10px 0;font-size:13px;font-weight:700;color:{C_ACCENT};'
            'letter-spacing:1px;">这期怎么读</p>'
            + body + '</section>')


# ---------------------------------------------------------------- 导读

def header(issue):
    """导读的固定开头，顺序照读者认知走：

        开场白（首期完整 / 后续精简） → 栏目 + 期数 → 栏目介绍
        → 本期导读 → 目录 → 筛选原则

    内容全部来自 data/profile.json；write.json 里的 header_lines 可临时覆盖开场白。
    """
    prof = issue.get("profile") or {}
    out = []

    # 1. 开场白
    if issue.get("header_lines"):
        lines = issue["header_lines"]
    elif issue.get("first_issue"):
        lines = prof.get("intro_first") or prof.get("intro_lines") or []
    else:
        lines = prof.get("intro_short") or prof.get("intro_lines") or []
    for ln in lines:
        out.append(para(esc(ln)))
    if lines:
        out.append(divider())

    # 2. 栏目 + 期数（居中报头）
    col = esc(prof.get("column", ""))
    no = issue.get("issue_no")
    if col or no:
        no_txt = f"第 {int(no):02d} 期" if no else ""
        sep = f'<span style="color:{C_LINE};">&nbsp;·&nbsp;</span>' if (col and no_txt) else ""
        out.append(
            '<section style="margin:6px 0 18px 0;text-align:center;">'
            f'<p style="margin:0;font-size:15px;letter-spacing:2px;color:{C_ACCENT};'
            f'font-weight:700;line-height:1.8;">{col}{sep}'
            f'<span style="color:{C_SUB};font-weight:400;">{no_txt}</span></p></section>')

    # 3. 栏目介绍
    for ln in prof.get("column_intro") or []:
        out.append(para(esc(ln)))

    # 4. 本期导读
    items = all_items(issue)
    n_deep = sum(1 for x in items if x.get("deep"))
    if issue.get("guide"):
        out.append(para(esc(issue["guide"])))
    else:
        out.append(para(
            f'这一期挑了 <span style="font-weight:700;">{len(items)}</span> 个值得关注的开源项目，'
            f'每个都单独写了一篇：怎么装、坑在哪，以及怎么让 AI 替你把安装跑完。'))

    # 5. 目录
    menu = issue.get("menu") or []
    if menu:
        marks = "①②③④⑤⑥⑦⑧"
        rows = [f'<p style="margin:0 0 6px 0;font-size:15px;line-height:1.75;'
                f'color:{C_TEXT};letter-spacing:0.3px;">'
                f'<span style="color:{C_ACCENT};font-weight:700;">{marks[i]}</span>&nbsp;'
                f'{esc(m)}</p>' for i, m in enumerate(menu)]
        out.append('<section style="margin:14px 0 6px 0;padding:14px 16px;'
                   f'background:#f6f7f4;border-radius:6px;">'
                   f'<p style="margin:0 0 8px 0;font-size:13px;color:{C_ACCENT};'
                   f'font-weight:700;letter-spacing:1px;">本期看什么</p>'
                   + "".join(rows) + '</section>')

    # 6. 筛选原则
    crit = prof.get("criteria")
    if crit:
        out.append(para(
            f'这次筛选只有三个原则：<span style="color:{C_ACCENT};font-weight:700;">'
            f'{esc(crit)}</span>。', mt="10px"))

    # 7. 这期怎么读（只在有深挖时出现）
    if n_deep:
        out.append(index_note(issue.get("read_note") or [
            f'这篇是索引，一共 {n_deep} 个项目和它们各自的文章。',
            '每篇都按同一个顺序写：它替你省掉哪件烦事 → 装之前先确认什么 → 怎么让 AI 帮你装 → 会踩到的坑。',
            '装着卡住了，把报错原文贴给 AI，比在网上搜「xx 安装失败」快得多。',
        ]))

    out.append(divider())
    return "".join(out)


def all_items(issue):
    return [issue["main"]] + list(issue.get("shorts") or [])


def body(issue):
    """导读正文：出深挖的项目只给摘要 + 入口，没出深挖的照旧展开。"""
    items = all_items(issue)
    n_deep = sum(1 for x in items if x.get("deep"))
    out = [header(issue)]

    if issue.get("intro"):
        for line in issue["intro"]:
            out.append(para(esc(line)))
        out.append(divider())

    for i, it in enumerate(items, 1):
        name = it.get("zh_name") or it["full_name"]
        if it.get("deep"):
            out.append(section_title(name, str(i)))
            if it.get("kicker"):
                out.append(quote(it["kicker"]))
            elif it.get("one_liner"):
                out.append(quote(it["one_liner"]))
            out.append(figure(it["full_name"], it.get("figure_caption", ""), compact=True))
            for seg in (it.get("summary") or []):
                out.append(para(esc(seg)))
            if it.get("teaser"):
                out.append(para(
                    f'<span style="color:{C_ACCENT};font-weight:700;">那篇里写了什么 · </span>'
                    + esc(it["teaser"]), size="15px", color="#5a5a5a"))
            out.append(link_slot(
                it.get("link_label") or f"《{name}：{it.get('kicker') or '完整安装步骤'}》",
                it.get("link_note") or "发布单篇后，在编辑器里用「链接」按钮选中这一框，指向那篇"))
            out.append(link_line(it.get("url", ""), it.get("stars"), it.get("lang")))
            out.append(divider())
        else:
            out.append(section_title(name, str(i)))
            if it.get("one_liner"):
                out.append(quote(it["one_liner"]))
            out.append(figure(it["full_name"], it.get("figure_caption", "")))
            if it.get("why_now"):
                out.append(para(f'<span style="color:{C_ACCENT};font-weight:700;">为什么是它 · </span>'
                                + esc(it["why_now"])))
            if it.get("pain"):
                out.append(para(esc(it["pain"])))
            out.append(steps_block(it.get("steps") or []))
            out.append(verdict_block(it.get("verdict")))
            out.append(link_line(it.get("url", ""), it.get("stars"), it.get("lang")))
            out.append(divider())

    for line in issue.get("ending") or []:
        out.append(para(esc(line)))
    if issue.get("cta"):
        out.append(para(f'<span style="color:{C_ACCENT};font-weight:700;">'
                        f'{esc(issue["cta"])}</span>'))

    wrap = ('<section style="font-family:' + FONT + ';font-size:16px;color:' + C_TEXT +
            ';letter-spacing:0.4px;">' + "".join(out) + '</section>')
    return wrap


# ---------------------------------------------------------------- 单篇深挖

def article_header(issue, item, idx, total):
    prof = issue.get("profile") or {}
    col = esc(prof.get("column", ""))
    no = issue.get("issue_no")
    marks = "①②③④⑤⑥⑦⑧"
    left = col
    if no:
        left += f" · 第 {int(no):02d} 期"
    right = f"{marks[idx - 1] if 0 < idx <= len(marks) else idx} / {total}"
    return ('<section style="margin:0 0 18px 0;padding-bottom:10px;'
            f'border-bottom:1px solid {C_LINE};">'
            f'<p style="margin:0;font-size:13px;letter-spacing:1px;color:{C_ACCENT};'
            f'font-weight:700;line-height:1.7;">{left}'
            f'<span style="color:{C_SUB};font-weight:400;">&nbsp;&nbsp;{esc(right)}</span>'
            '</p></section>')


def article_body(issue, item, idx, total):
    """一篇单项目深挖。字段缺了就跳过，方便先出骨架再补文案。"""
    out = [article_header(issue, item, idx, total)]

    # 标题
    name = item.get("zh_name") or item["full_name"]
    out.append(f'<section style="margin:0 0 10px 0;">'
               f'<p style="margin:0;font-size:24px;font-weight:700;color:#141414;'
               f'line-height:1.45;letter-spacing:0.2px;">{esc(name)}</p></section>')
    if item.get("kicker"):
        out.append(para(esc(item["kicker"]), size="17px", color=C_ACCENT, weight="700", mb="14px"))
    if item.get("lead"):
        out.append(quote(item["lead"]))
    out.append(figure(item["full_name"], item.get("figure_caption", "")))

    for seg in (item.get("what") or []):
        out.append(para(esc(seg)))

    if item.get("pain"):
        out.append(sub_title("它替你省掉哪件烦事"))
        for seg in item["pain"]:
            out.append(para(esc(seg)))

    if item.get("check"):
        out.append(sub_title("装之前，先确认三件事"))
        out.append('<section style="margin:0 0 16px 0;padding:14px 16px;background:#faf9f6;'
                   'border-radius:6px;">'
                   + "".join(kv_row(k, v) for k, v in item["check"]) + '</section>')

    if item.get("ai_why") or item.get("ai_prompt"):
        out.append(sub_title("怎么装：让 AI 替你跑这一步"))
        for seg in (item.get("ai_why") or []):
            out.append(para(esc(seg)))
        if item.get("ai_prompt"):
            out.append(code_block(item["ai_prompt"],
                                  item.get("ai_prompt_label") or "复制下面这段，发给能操作你电脑的 AI"))
        if item.get("ai_follow"):
            for seg in item["ai_follow"]:
                out.append(para(esc(seg)))
        if item.get("ai_warn"):
            out.append(hint_block("用之前先知道", item["ai_warn"], tone="warm"))

    if item.get("manual"):
        out.append(sub_title(item.get("manual_title") or "不想用 AI？手动三步"))
        out.append(code_block(item["manual"], item.get("manual_label") or "命令行"))
        if item.get("manual_note"):
            out.append(para(esc(item["manual_note"])))

    if item.get("first"):
        out.append(sub_title("第一次打开，先做这三件事"))
        out.append(bullet_list(item["first"], marker="›"))

    if item.get("pits"):
        out.append(sub_title("会踩到的坑"))
        out.append(pit_list(item["pits"]))

    if item.get("fit") or item.get("unfit"):
        if item.get("fit"):
            out.append(hint_block("适合", item["fit"], tone="green"))
        if item.get("unfit"):
            out.append(hint_block("不适合", item["unfit"], tone="warm"))

    if item.get("verdict"):
        out.append(verdict_block(item["verdict"]))

    out.append(link_line(item.get("url", ""), item.get("stars"), item.get("lang")))

    # 回导读
    back = issue.get("title") or "本期合集"
    out.append(link_slot(f"回《{back}》看这一期另外几个",
                         "导读已发布后，把这一框换成指向导读的链接"))

    wrap = ('<section style="font-family:' + FONT + ';font-size:16px;color:' + C_TEXT +
            ';letter-spacing:0.4px;">' + "".join(out) + '</section>')
    return wrap


# ---------------------------------------------------------------- 页面外壳

TIPS_ISSUE = ("粘贴提示：正文图片微信不认外链，占位框里的 og 图请先另存再插入；"
              "GitHub 地址正文里点不动，需要留一个可点的就往「阅读原文」里放。")
TIPS_ARTICLE = ("粘贴提示：单篇里有两个「链接位」——顶部回导读、正文里的 GitHub 地址。"
                "回导读的框，等导读发布后用编辑器「链接」按钮指向它；GitHub 地址只能作纯文本。")


def page(title, body_html, meta_html="", tips=TIPS_ISSUE, btn="复制正文（富文本）"):
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title></head>
<body style="margin:0;background:#f2f2ee;font-family:{FONT};">
<section style="max-width:760px;margin:0 auto;padding:18px 16px 60px 16px;">

  <section style="background:#1f2a24;border-radius:10px;padding:16px 18px;margin-bottom:16px;">
    <p style="margin:0 0 6px 0;color:#eae7df;font-size:14px;line-height:1.7;">
      这是给公众号用的稿子。点下面按钮复制，粘进编辑器就能发 —— 图片要手动拖。
    </p>
    <p style="margin:0 0 12px 0;color:#9fae9f;font-size:12px;line-height:1.7;">
      {meta_html}
    </p>
    <button onclick="copyBody()" style="background:#3ddc97;color:#10231a;border:0;
      border-radius:6px;padding:10px 20px;font-size:15px;font-weight:700;cursor:pointer;">
      {btn}</button>
    <span id="ok" style="color:#3ddc97;font-size:13px;margin-left:10px;opacity:0;">已复制</span>
  </section>

  <section style="background:#ffffff;border-radius:10px;padding:26px 22px;
    box-shadow:0 1px 3px rgba(0,0,0,.06);">
    <div id="wxbody">{body_html}</div>
  </section>

  <p style="margin:16px 4px 0 4px;color:#9a9a92;font-size:12px;line-height:1.8;">
    {tips}
  </p>
</section>
<script>
function copyBody(){{
  var el=document.getElementById('wxbody');
  var r=document.createRange(); r.selectNodeContents(el);
  var s=window.getSelection(); s.removeAllRanges(); s.addRange(r);
  try {{ document.execCommand('copy'); }} catch(e) {{}}
  s.removeAllRanges();
  var ok=document.getElementById('ok'); ok.style.opacity=1;
  setTimeout(function(){{ ok.style.opacity=0; }},1600);
}}
</script>
</body></html>"""


# ---------------------------------------------------------------- markdown

def _md_header(issue):
    prof = issue.get("profile") or {}
    if issue.get("header_lines"):
        lines = issue["header_lines"]
    elif issue.get("first_issue"):
        lines = prof.get("intro_first") or prof.get("intro_lines") or []
    else:
        lines = prof.get("intro_short") or prof.get("intro_lines") or []
    L = []
    for line in lines:
        L.append(f"{line}\n\n")
    L.append("---\n\n")
    col = prof.get("column", "")
    no = issue.get("issue_no")
    if col or no:
        L.append(f"**{col}" + (f" · 第 {int(no):02d} 期" if no else "") + "**\n\n")
    for line in prof.get("column_intro") or []:
        L.append(f"{line}\n\n")
    items = all_items(issue)
    L.append((issue.get("guide") or
              f"这一期挑了 {len(items)} 个值得关注的开源项目，每个都单独写了一篇："
              f"怎么装、坑在哪，以及怎么让 AI 替你把安装跑完。") + "\n\n")
    if issue.get("menu"):
        L.append("**本期看什么**\n\n")
        marks = "①②③④⑤⑥⑦⑧"
        for i, m in enumerate(issue["menu"]):
            L.append(f"{marks[i]} {m}\n\n")
    if prof.get("criteria"):
        L.append(f"这次筛选只有三个原则：**{prof['criteria']}**。\n\n")
    if any(x.get("deep") for x in items):
        L.append("**这期怎么读**\n\n")
        for x in (issue.get("read_note") or []):
            L.append(f"{x}\n\n")
    L.append("---\n\n")
    return L


def markdown(issue):
    L = [f"# {issue.get('title','')}\n\n"]
    L += _md_header(issue)
    for line in issue.get("intro") or []:
        L.append(f"{line}\n")
    for i, it in enumerate(all_items(issue), 1):
        name = it.get("zh_name") or it["full_name"]
        L.append(f"\n## {i}. {name}\n")
        if it.get("kicker"):
            L.append(f"> {it['kicker']}\n")
        elif it.get("one_liner"):
            L.append(f"> {it['one_liner']}\n")
        L.append(f"\n![{it['full_name']}](https://opengraph.githubassets.com/1/{it['full_name']})\n")
        if it.get("deep"):
            for seg in (it.get("summary") or []):
                L.append(f"\n{seg}\n")
            if it.get("teaser"):
                L.append(f"\n**那篇里写了**：{it['teaser']}\n")
            L.append(f"\n**[链接位] {it.get('link_label') or name + ' 完整安装'}"
                     f" ← 单篇发布后在此插入超链接**\n")
        else:
            if it.get("why_now"):
                L.append(f"\n**为什么是它**：{it['why_now']}\n")
            if it.get("pain"):
                L.append(f"\n{it['pain']}\n")
            if it.get("steps"):
                L.append("\n**三步用起来**\n")
                for k, s in enumerate(it["steps"], 1):
                    L.append(f"{k}. {s}\n")
            if it.get("verdict"):
                L.append(f"\n**说句实话**：{it['verdict']}\n")
        L.append(f"\n{it.get('url','')}（{it.get('stars','')} star · {it.get('lang','')}）\n")

    for line in issue.get("ending") or []:
        L.append(f"\n{line}\n")
    if issue.get("cta"):
        L.append(f"\n**{issue['cta']}**\n")
    return "".join(L)


def article_markdown(issue, item, idx, total):
    name = item.get("zh_name") or item["full_name"]
    prof = issue.get("profile") or {}
    marks = "①②③④⑤⑥⑦⑧"
    L = [f"# {name}：{item.get('kicker','')}\n"]
    L.append(f"*{prof.get('column','')} · 第 {int(issue.get('issue_no') or 1):02d} 期 · "
             f"单篇 {marks[idx-1] if 0 < idx <= len(marks) else idx}/{total}*\n\n")
    if item.get("lead"):
        L.append(f"> {item['lead']}\n")
    L.append(f"\n![{item['full_name']}](https://opengraph.githubassets.com/1/{item['full_name']})\n")
    if item.get("meta"):
        for k, v in item["meta"]:
            L.append(f"- **{k}**：{v}\n")
        L.append("\n")
    for seg in (item.get("what") or []):
        L.append(f"{seg}\n\n")
    if item.get("pain"):
        L.append("## 它替你省掉哪件烦事\n\n")
        for seg in item["pain"]:
            L.append(f"{seg}\n\n")
    if item.get("check"):
        L.append("## 装之前，先确认三件事\n\n")
        for k, v in item["check"]:
            L.append(f"- **{k}**：{v}\n")
        L.append("\n")
    if item.get("ai_why") or item.get("ai_prompt"):
        L.append("## 怎么装：让 AI 替你跑这一步\n\n")
        for seg in (item.get("ai_why") or []):
            L.append(f"{seg}\n\n")
        if item.get("ai_prompt"):
            L.append("```text\n" + "\n".join(item["ai_prompt"]) + "\n```\n\n")
        for seg in (item.get("ai_follow") or []):
            L.append(f"{seg}\n\n")
        if item.get("ai_warn"):
            L.append("**用之前先知道**\n\n")
            for x in item["ai_warn"]:
                L.append(f"- {x}\n")
            L.append("\n")
    if item.get("manual"):
        L.append(f"## {item.get('manual_title') or '不想用 AI？手动三步'}\n\n")
        L.append("```bash\n" + "\n".join(item["manual"]) + "\n```\n\n")
        if item.get("manual_note"):
            L.append(f"{item['manual_note']}\n\n")
    if item.get("first"):
        L.append("## 第一次打开，先做这三件事\n\n")
        for k, s in enumerate(item["first"], 1):
            L.append(f"{k}. {s}\n")
        L.append("\n")
    if item.get("pits"):
        L.append("## 会踩到的坑\n\n")
        for p in item["pits"]:
            head, b = (p[0], p[1]) if isinstance(p, (list, tuple)) else ("", p)
            L.append(f"**{head}**：{b}\n\n" if head else f"{b}\n\n")
    if item.get("fit"):
        L.append("## 适合\n\n" + "".join(f"- {x}\n" for x in item["fit"]) + "\n")
    if item.get("unfit"):
        L.append("## 不适合\n\n" + "".join(f"- {x}\n" for x in item["unfit"]) + "\n")
    if item.get("verdict"):
        L.append(f"**说句实话**：{item['verdict']}\n\n")
    L.append(f"{item.get('url','')}（{item.get('stars','')} star · {item.get('lang','')}）\n\n")
    L.append(f"**[回导读链接位] 《{issue.get('title','')}》**\n")
    return "".join(L)


# ---------------------------------------------------------------- 落盘

def write_files(issue, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    date = issue["date"]
    items = all_items(issue)
    deep = [(i, x) for i, x in enumerate(items, 1) if x.get("deep")]
    total = len(deep) or 1

    st = issue.get("stats") or {}
    base_meta = []
    if st.get("pool"):
        base_meta.append(f"候选池 {st.get('pool')} → 本期 {len(items)} 个")
    if st.get("mode"):
        base_meta.append(st["mode"])
    if issue.get("word_count"):
        base_meta.append(f"约 {issue['word_count']} 字")

    made = []

    # 导读
    p_html = os.path.join(out_dir, f"issue_{date}.html")
    with open(p_html, "w", encoding="utf-8") as f:
        f.write(page(issue.get("title") or "GitHub 开源观察", body(issue),
                     " · ".join(base_meta + [f"含 {len(deep)} 篇单篇"])))
    p_md = os.path.join(out_dir, f"issue_{date}.md")
    with open(p_md, "w", encoding="utf-8") as f:
        f.write(markdown(issue))
    made.append(("导读", issue.get("title") or "索引", p_html, p_md))

    # 单篇
    for idx, it in deep:
        slug = it.get("slug") or (it["full_name"].split("/")[-1].replace(".", "-"))
        name = it.get("zh_name") or it["full_name"]
        a_html = os.path.join(out_dir, f"a{idx}_{slug}.html")
        with open(a_html, "w", encoding="utf-8") as f:
            f.write(page(f"{name}：{it.get('kicker','')}", article_body(issue, it, idx, total),
                         " · ".join(base_meta + [f"单篇 {idx}/{total}"]), TIPS_ARTICLE))
        a_md = os.path.join(out_dir, f"a{idx}_{slug}.md")
        with open(a_md, "w", encoding="utf-8") as f:
            f.write(article_markdown(issue, it, idx, total))
        made.append((f"单篇{idx}", f"{name}：{it.get('kicker','')}", a_html, a_md))

    # 配图清单
    p_fig = os.path.join(out_dir, f"issue_{date}_配图清单.txt")
    with open(p_fig, "w", encoding="utf-8") as f:
        f.write(f"本期配图（另存后插入正文对应位置）\n日期 {date}\n")
        f.write("封面图会由 cover 步骤自动生成（存放在 data/covers/），后台每篇单独上传；\n"
                "正文里只放每张 og 图的本地副本。\n\n")
        for i, it in enumerate(items, 1):
            f.write(f"[{i}] {it['full_name']}\n"
                    f"    https://opengraph.githubassets.com/1/{it['full_name']}\n")
        for idx, it in deep:
            f.write(f"\n== 单篇 {idx}：{it.get('zh_name') or it['full_name']} ==\n")
            f.write(f"    https://opengraph.githubassets.com/1/{it['full_name']}\n")

    # 待插链接清单 —— 这张最容易被忘
    p_link = os.path.join(out_dir, f"issue_{date}_待插链接.txt")
    with open(p_link, "w", encoding="utf-8") as f:
        f.write("发布顺序与链接位置\n" + "=" * 40 + "\n\n")
        f.write("微信正文里的外链会被过滤，能点的只有「已发布」的公众号文章。\n"
                "所以顺序必须是：先发单篇（或先「发布」不群发）拿到链接 → 再改导读插链接。\n\n")
        f.write("做法 A（推荐，单篇集中阅读）\n"
                "  1. 三篇单篇各自「发布」（不群发，不占当天群发次数，但会生成永久链接）\n"
                "  2. 复制每篇的链接\n"
                "  3. 打开导读稿，粘进编辑器，选中每个绿色虚线框 → 点「链接」→ 粘贴对应链接\n"
                "  4. 群发导读（这才是推送给粉丝的那一条）\n\n")
        f.write("做法 B（一次群发多条，零配置）\n"
                "  1. 一次群发里加多条：第 1 条导读，2-4 条是单篇\n"
                "  2. 把导读里的链接位文字改成「本次推送第 2 条」\n"
                "  3. 缺点：点不了，只能靠读者自己划；建议同时建一个「合集」\n\n")
        f.write("导读里要替换的链接位：\n")
        for idx, it in deep:
            f.write(f"  [{idx}] {it.get('zh_name') or it['full_name']}"
                    f"  →  a{idx}_{it.get('slug') or 'x'}.html\n")
        f.write("\n单篇里要替换的链接位：\n")
        for idx, it in deep:
            f.write(f"  [{idx}] 底部「回导读」→ 导读那篇的链接\n")

    return made, p_fig, p_link
