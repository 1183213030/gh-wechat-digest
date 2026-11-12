---
name: gh-wechat-digest
description: 从 GitHub 找有意思、有用的开源项目，打包成一篇能直接粘进微信公众号的稿子。含公众号口径的选题打分、人工精修文案、微信兼容的内联样式 HTML（带一键复制富文本）。触发词：GitHub 公众号选题、写一篇 GitHub 合集、这几个项目发公众号、做一期项目推荐、gh-wechat-digest。
---

# GitHub 公众号选题台

给公众号写「这周挖到几个 GitHub 项目」这类稿子的工具。它只做三件事：**挑项目、写文案、出可粘贴的稿**。

发布这一步故意留给人工 —— 微信的正文一旦发出去改不了几个字，最后一眼必须你自己看。

> 一条铁律：`run` 出来的文案是规则拼的，读起来像模板。**必须走 todo → 自己写 → apply**，跳过这步等于交了一篇 AI 味的通稿。

---

## 一、它和「涨星榜」的区别

| | trending 榜 | 本技能 |
|---|---|---|
| 排序 | 星数、涨星速度 | **读者会不会点开、看完、转出去**（四维） |
| 选谁 | 谁今天最火 | 谁还没被写烂（火的反而不选） |
| 文案 | 英文简介照抄 | 一句话说清 / 痛点 / 三步 / 一句毒舌 |
| 产出 | 一个链接列表 | **一篇能直接粘进公众号的稿子** |
| 发布 | — | 内联样式 HTML，点一下复制富文本 |

核心判断只有一句：**读者不缺项目列表，缺的是「这个跟我有什么关系」。**

---

## 二、Agent 执行契约（照这个顺序走，别跳）

用户说「给我写一期公众号」时：

| 步 | 做什么 | 命令 | 跳过会怎样 |
|---|---|---|---|
| 1 | 体检 | `python scripts/digest.py doctor` | 可能白等两分钟才发现网或额度有问题 |
| 2 | 抓 + 选 + 出骨架 | `python scripts/digest.py run` | — |
| 3 | 看要写哪几段 | `python scripts/digest.py todo` | — |
| 4 | **自己写文案**（见第四节） | 写 `data/write.json` → `apply` | 交出去的是模板文案 |
| 5 | 出稿 | `python scripts/digest.py render` | — |
| 6 | 交付 | 给 HTML 路径 + 一句话说清「这期主打哪个、为什么」 | 用户还得自己判断 |

**选题不合口味就手动点名**，别跟公式较劲：

```bash
python scripts/digest.py run                 # 先抓池子
python scripts/digest.py pick --main owner/repo --shorts a/b,c/d
```

`pick` 不重新抓网，直接从 `data/pool.json` 里组一期。看到好的就点名，公式只是兜底。

---

## 三、命令行

```bash
python scripts/digest.py doctor        # 体检：token、额度、trending 可达
python scripts/digest.py run           # 抓 trending + 新建高星 + 老项目活跃 → 打分 → 组一期
python scripts/digest.py pick --main owner/repo --shorts a/b,c/d
python scripts/digest.py todo          # 列出这一期哪些段落还是规则文案
python scripts/digest.py apply         # 读 data/write.json 覆盖进去
python scripts/digest.py render         # 出 HTML / md / 配图清单
python scripts/digest.py log --url 链接  # 记一条发布记录
python scripts/digest.py history        # 看发过几期、发过哪些项目
```

`run` 的旋钮：

| 参数 | 默认 | 什么时候改 |
|---|---|---|
| `--days 30` | 30 | 想挖更新的，改 14；想挖更多的，改 60 |
| `--min-stars 400` | 400 | 小号可以降到 200 |
| `--shorts 3` | 3 | 一期想放几个短评 |
| `--detail-cap 20` | 20（有 token 时 26） | 候选池大小，影响耗时 |
| `--allow-repeat` | 关 | 想写一个 30 天内推过的项目 |
| `--force` | 关 | 分数不够也硬出一期 |

---

## 四、文案怎么写（这是这个技能真正的价值）

写 `data/write.json`，格式：

```json
{"title": "", "intro": ["", ""], "ending": [""], "cta": "",
 "items": [{"which": "main",  "fill": {"zh_name": "", "one_liner": "", "why_now": "", "pain": "", "steps": ["", "", ""], "verdict": ""}},
           {"which": "short1", "fill": {"zh_name": "", "one_liner": "", "verdict": ""}}]}
```

`which` 就是 `todo` 里打印的 `main` / `short1` / `short2`。

### 六个字段各写什么

| 字段 | 要求 | 反例 |
|---|---|---|
| **zh_name** | 中文名字 + 一句它是干什么的，不超过 25 字 | 「Aerial」——光给名字，读者不知道点不点 |
| **one_liner** | 一句话说清它替读者省了哪件烦事，**不出现「基于」「赋能」「一站式」** | 「一个基于 Kotlin 的 Android TV Launcher」 |
| **why_now** | 为什么现在写它：建库多少天 / 涨了多少 / 别人还没写过 | 「这个项目很不错，值得一试」 |
| **pain** | 一个具体场景，要有画面；许用「你家那台……」 | 「提升了用户体验」 |
| **steps** | 三步，真的只有三步，每步一件动作 | 「安装依赖并配置环境后运行」 |
| **verdict** | **必须说一个缺点或门槛**。不说缺点，读者当广告看 | 「非常好用，强烈推荐」 |

### 硬规矩

- `verdict` 里必须有真缺点：要门禁、要 API key、只支持某个系统、作者三个月没更新、许可证不能商用 —— 没有缺点就写「门槛在哪」。
- **许可证要说**：CC BY-NC（不能商用）、GPL（二创要注意）、无许可证（别商用）都必须点一句。读者会拿去做别的事。
- 数字要用真数字：`1644 个知识点`，不是「大量知识点」。
- 正文里不要放 Markdown 链接（微信点不动），GitHub 地址会自动作为文本行输出。
- 一期 1 主打 + 2–4 短评。短评只写 `one_liner` + `verdict`，别展开。

### 标题

`run` 会从模板里挑一个，但基本要你改。好标题的公式是**「具体动作 + 具体收益 + 一点代价」**：

- 好：「我把家里电视的开机广告干掉了，只装了一个 GitHub 项目」
- 差：「GitHub 优质项目推荐第 12 期」（没有画面）
- 差：「这 5 个项目太强了，建议收藏」（全是形容词）

---

## 五、微信的硬约束（代码已经处理，但你要知道为什么）

| 约束 | 表现 | 代码怎么处理 |
|---|---|---|
| 编辑器不认 `<style>` / `class` | 粘过去排版全丢 | 全部样式 inline 写在标签上 |
| 不吃 flex / grid | 布局塌掉 | 只用 `section` 嵌套 + padding |
| 正文图片不收外链 | 图挂掉 | 只出**图占位框**，图要你在编辑器里手动插入 |
| 正文链接点不动 | 读者点不了 | 地址作文本；可点的只能放「阅读原文」 |
| 一天只能群发 1 次 | 订阅号限制 | 天然是「一天一期」的节奏 |

出稿后打开 `issue_YYYY-MM-DD.html`，点「复制正文（富文本）」，粘进编辑器。**占位框删掉、图片拖进去、封面单独上传。**

---

## 六、评分：四个维度（满分 100）

| 维度 | 分值 | 判据 |
|---|---|---|
| **有用** | 30 | 有官网 +8、有安装段 +7、应用层语言 +6、topics≥3 +4、体积小 +5 |
| **好讲** | 25 | 简介短且没 buzzword +8、作者写了中文 +6、有反差词（不用/替代/一键）+6、星数在 800–3 万之间 +5 |
| **可演示** | 20 | README 有 2 张以上图 +9、有 demo/gif 字样 +5、有官网 +6 |
| **没被写烂** | 25 | 建库 ≤30 天 +16、≤90 天 +12、≤1 年 +7；当天涨 800+ 星 −6（全网都在写它）；来自新建榜 +4 |

**硬淘汰**：已归档、星 < 200、awesome/合集类、破解盗版类（`crack` / `破解` / `白嫖` 等）、仓库超 900MB。

**为什么不按星排序**：3 万星以上的项目，几十个号都写过；建库 20 天的 1 万星，才是你独有的。

---

## 七、数据从哪来

三条公开通道（`scripts/sources.py`）：

1. `github.com/trending` —— 今日榜 + 本周榜，抓 HTML，能拿到真实涨星数
2. `search/repositories` `created:>30天 stars:>400` —— 新项目爆发榜，**主力来源**
3. `search/repositories` `pushed:>7天 stars:>1500` —— 老树发新芽

补数据时的省钱设计（额度为 0 也能跑）：
- 搜索接口返回的记录**自带**建库时间、许可证、体积、主页 —— 不用再查详情
- 只有 trending 来的缺这些，才打 core API；core 用光时自动改走 `search?q=repo:owner/name`（搜索额度是另一本账）
- README 一律走 `raw.githubusercontent.com`，**完全不消耗额度**

token 从环境变量 `GH_TOKEN` / `config.json` 的 `gh_token` / `gh auth token` 里自动找。没有也能跑，就是慢点。

---

## 八、文件在哪

```
data/
├── pool.json          当天候选池（含打分、README 摘要）
├── issue.json         本期稿件（渲染就吃这个）
├── todo_write.json    待写清单
├── write.json         你写的文案（apply 读它）
├── seen.json          查重账本（30 天冷却）
├── published.json     发布记录（log 写它，history 读它）
├── state.json         期号
└── reports/           issue_日期.html / .md / _配图清单.txt
```

备份 `data/` 就等于备份了选题库：哪天想知道「三个月前那期主打是什么」，`history` 一句话就有。

---

## 九、什么时候该改脚本

- 选题口味不对 → 改 `scripts/score.py` 的权重，别改 SKILL.md
- 抓不到项目 → 先跑 `doctor` 看 trending 是否可达；trending 返回 0 条就是 GitHub 改版了
- 稿子排版乱 → 大概率有人往模板里加了 `class` 或 `<style>`，微信会把它丢掉

---

## 十、署名

稿子默认不写署名。想加就在 `data/write.json` 的 `ending` 里加一行，别改代码。
