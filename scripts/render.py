"""把一期稿件渲成两种东西：

1. issue_YYYY-MM-DD.html —— 带「复制正文」按钮的独立页面，点一下复制**富文本**，
   粘进公众号编辑器基本能保住排版（mdnice 那套思路，只是不依赖任何平台）。
2. issue_YYYY-MM-DD.md  —— 纯文字版，编辑器抽风时的手动兜底。

微信的硬约束，代码里全部照着做了：
  · 不用 <style>/class，所有样式 inline 写在标签上（微信会丢弃样式表）
  · 不用 flex/grid/float，只用 section 嵌套 + padding
  · 正文里的图片不能外链，所以只放「图占位框」，图片要你在编辑器里手动插入
  · 正文链接点不动，GitHub 地址只作文本，外链只能放「阅读原文」
"""
import html
import os

C_TEXT = "#2f2f2f"
C_SUB = "#8c8c8c"
C_ACCENT = "#1F6F4A"
C_LINE = "#e8e4dc"
FONT = ('-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",'
        '"Microsoft YaHei",sans-serif')


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


def figure(full_name, caption="", compact=False):
    """图占位框。微信正文不收外链图，所以这里只给占位 + 可直接拖的地址。"""
    url = f"https://opengraph.githubassets.com/1/{full_name}"
    cap = f'<br><span style="color:{C_SUB};font-size:12px;">{esc(caption)}</span>' if caption else ""
    pad = "12px 12px" if compact else "22px 14px"
    mb = "12px" if compact else "20px"
    tip = "［ 图 ］" if compact else "［ 图片占位 · 粘贴时删掉本框，把下面这张图拖进来 ］"
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


# ---------------------------------------------------------------- 整篇

def header(issue):
    """固定开头，顺序照读者认知走：

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
    n_short = len(issue.get("shorts") or [])
    if issue.get("guide"):
        out.append(para(esc(issue["guide"])))
    else:
        total = 1 + n_short
        out.append(para(
            f'这一期挑了 <span style="font-weight:700;">{total}</span> 个值得关注的开源项目：'
            f'1 个重点深挖，{n_short} 个短评。'))

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

    out.append(divider())
    return "".join(out)


def body(issue):
    main = issue["main"]
    shorts = issue.get("shorts") or []
    out = [header(issue)]

    # 导语
    if issue.get("intro"):
        for line in issue["intro"]:
            out.append(para(esc(line)))
        out.append(divider())

    # 主打
    out.append(section_title(main.get("zh_name") or main["full_name"], "1"))
    if main.get("one_liner"):
        out.append(quote(main["one_liner"]))
    out.append(figure(main["full_name"], main.get("figure_caption", "")))
    if main.get("why_now"):
        out.append(para(f'<span style="color:{C_ACCENT};font-weight:700;">为什么是它 · </span>'
                        + esc(main["why_now"])))
    if main.get("pain"):
        out.append(para(esc(main["pain"])))
    out.append(steps_block(main.get("steps") or []))
    out.append(verdict_block(main.get("verdict")))
    out.append(link_line(main.get("url", ""), main.get("stars"), main.get("lang")))
    out.append(divider())

    # 短评
    if shorts:
        out.append(section_title("另外几个，短的", ""))
        for i, s in enumerate(shorts, 2):
            out.append(f'<p style="margin:22px 0 6px 0;font-size:17px;font-weight:700;'
                       f'color:#1a1a1a;line-height:1.6;">'
                       f'<span style="color:{C_ACCENT};">{i}.</span> '
                       f'{esc(s.get("zh_name") or s["full_name"])}</p>')
            if s.get("one_liner"):
                out.append(para(esc(s["one_liner"]), mb="6px"))
            out.append(figure(s["full_name"], compact=True))
            if s.get("verdict"):
                out.append(para(f'<span style="color:{C_SUB};">点评 · </span>' + esc(s["verdict"]),
                                size="15px", color="#666666", mb="8px"))
            out.append(link_line(s.get("url", ""), s.get("stars"), s.get("lang")))
        out.append(divider())

    # 结尾
    ending = issue.get("ending") or []
    for line in ending:
        out.append(para(esc(line)))
    if issue.get("cta"):
        out.append(para(f'<span style="color:{C_ACCENT};font-weight:700;">'
                        f'{esc(issue["cta"])}</span>'))

    wrap = ('<section style="font-family:' + FONT + ';font-size:16px;color:' + C_TEXT +
            ';letter-spacing:0.4px;">' + "".join(out) + '</section>')
    return wrap


def page(issue, body_html, meta_html=""):
    title = esc(issue.get("title") or "GitHub 这周值得看的几个项目")
    n_words = issue.get("word_count", "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title></head>
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
      复制正文（富文本）</button>
    <span id="ok" style="color:#3ddc97;font-size:13px;margin-left:10px;opacity:0;">已复制</span>
  </section>

  <section style="background:#ffffff;border-radius:10px;padding:26px 22px;
    box-shadow:0 1px 3px rgba(0,0,0,.06);">
    <div id="wxbody">{body_html}</div>
  </section>

  <p style="margin:16px 4px 0 4px;color:#9a9a92;font-size:12px;line-height:1.8;">
    粘贴提示：正文图片微信不认外链，占位框里的 og 图请先另存再插入；GitHub 地址正文里点不动，
    需要留一个可点的就往「阅读原文」里放。
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


def markdown(issue):
    main = issue["main"]
    L = []
    L.append(f"# {issue.get('title','')}\n")
    prof = issue.get("profile") or {}
    if issue.get("header_lines"):
        lines = issue["header_lines"]
    elif issue.get("first_issue"):
        lines = prof.get("intro_first") or prof.get("intro_lines") or []
    else:
        lines = prof.get("intro_short") or prof.get("intro_lines") or []
    for line in lines:
        L.append(f"{line}\n\n")
    L.append("---\n\n")
    col = prof.get("column", "")
    no = issue.get("issue_no")
    if col or no:
        L.append(f"**{col}" + (f" · 第 {int(no):02d} 期" if no else "") + "**\n\n")
    for line in prof.get("column_intro") or []:
        L.append(f"{line}\n\n")
    n_short = len(issue.get("shorts") or [])
    L.append((issue.get("guide") or
              f"这一期挑了 {1 + n_short} 个值得关注的开源项目：1 个重点深挖，{n_short} 个短评。") + "\n\n")
    menu = issue.get("menu") or []
    if menu:
        L.append("**本期看什么**\n\n")
        marks = "①②③④⑤⑥⑦⑧"
        for i, m in enumerate(menu):
            L.append(f"{marks[i]} {m}\n\n")
    if prof.get("criteria"):
        L.append(f"这次筛选只有三个原则：**{prof['criteria']}**。\n\n")
    L.append("---\n\n")
    for line in issue.get("intro") or []:
        L.append(f"{line}\n")

    L.append(f"\n## 1. {main.get('zh_name') or main['full_name']}\n")
    if main.get("one_liner"):
        L.append(f"> {main['one_liner']}\n")
    L.append(f"\n![{main['full_name']}](https://opengraph.githubassets.com/1/{main['full_name']})\n")
    if main.get("why_now"):
        L.append(f"\n**为什么是它**：{main['why_now']}\n")
    if main.get("pain"):
        L.append(f"\n{main['pain']}\n")
    if main.get("steps"):
        L.append("\n**三步用起来**\n")
        for i, s in enumerate(main["steps"], 1):
            L.append(f"{i}. {s}\n")
    if main.get("verdict"):
        L.append(f"\n**说句实话**：{main['verdict']}\n")
    L.append(f"\n{main.get('url','')}（{main.get('stars','')} star · {main.get('lang','')}）\n")

    for i, s in enumerate(issue.get("shorts") or [], 2):
        L.append(f"\n## {i}. {s.get('zh_name') or s['full_name']}\n")
        if s.get("one_liner"):
            L.append(f"{s['one_liner']}\n")
        if s.get("verdict"):
            L.append(f"\n**点评**：{s['verdict']}\n")
        L.append(f"\n{s.get('url','')}（{s.get('stars','')} star · {s.get('lang','')}）\n")

    for line in issue.get("ending") or []:
        L.append(f"\n{line}\n")
    if issue.get("cta"):
        L.append(f"\n**{issue['cta']}**\n")
    return "".join(L)


def write_files(issue, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    date = issue["date"]
    b = body(issue)

    stat = []
    if issue.get("stats"):
        st = issue["stats"]
        stat.append(f"候选池 {st.get('pool','?')} → 本期 1 主打 + {len(issue.get('shorts') or [])} 短评")
        if st.get("mode"):
            stat.append(st["mode"])
    if issue.get("word_count"):
        stat.append(f"约 {issue['word_count']} 字")
    meta = " · ".join(stat)

    p_html = os.path.join(out_dir, f"issue_{date}.html")
    with open(p_html, "w", encoding="utf-8") as f:
        f.write(page(issue, b, meta))

    p_md = os.path.join(out_dir, f"issue_{date}.md")
    with open(p_md, "w", encoding="utf-8") as f:
        f.write(markdown(issue))

    # 配图清单：省得你在编辑器里翻
    p_fig = os.path.join(out_dir, f"issue_{date}_配图清单.txt")
    with open(p_fig, "w", encoding="utf-8") as f:
        f.write(f"本期配图（另存后插入正文对应位置）\n日期 {date}\n\n")
        f.write(f"[1] 封面 2.35:1（900x383）建议：用主打项目的 og 图裁切\n"
                f"    https://opengraph.githubassets.com/1/{issue['main']['full_name']}\n\n")
        for i, s in enumerate(issue.get("shorts") or [], 2):
            f.write(f"[{i}] {s['full_name']}\n"
                    f"    https://opengraph.githubassets.com/1/{s['full_name']}\n\n")
        f.write("封面图在公众号后台单独上传，不占正文；正文里只放每张 og 图。\n")
    return p_html, p_md, p_fig
