# gh-wechat-digest

> 从 GitHub 找有意思、有用的开源项目，打包成一篇能直接粘进微信公众号的稿子。

GitHub 每天新增几千个仓库。公众号作者翻两小时 trending，最后什么都没写成——因为榜单回答的是"什么火"，不回答"读者愿意看完哪一篇"。

这个工具只干一件事：**把"火"翻译成"有人看"**。

它是一个 [WorkBuddy](https://www.workbuddy.cn/) Skill，也可以当普通 Python 工具用。

---

## 它和涨星榜有什么不一样

| | GitHub trending | gh-wechat-digest |
|---|---|---|
| 排序依据 | 星数、涨星速度 | 读者会不会点开、看完、转出去（四维） |
| 选谁 | 谁今天最火 | **谁还没被写烂**（当天暴涨 800+ 星反而扣分——那天几十个号都在写它） |
| 文案 | 英文简介照抄 | 一句话说清 / 痛点场景 / 三步上手 / 一句真缺点 |
| 产出 | 一个链接列表 | **一篇能直接粘进公众号编辑器的富文本稿** |
| 撞题 | 期期撞 | 查重账本，推过的项目 30 天冷却 |

核心判断只有一句：**读者不缺项目列表，缺的是"这个跟我有什么关系"。**

## 一期长什么样

[examples/issue_2026-11-12.md](examples/issue_2026-11-12.md) 是一个真实跑出来的例子：1 个主打深挖（600 字）+ 3 条短评（各 100 字），标题是《我把家里电视的开机广告干掉了，只装了一个 GitHub 项目》。

每个项目的固定结构：

1. **一句话说清** —— 不出现"基于""赋能""一站式"
2. **痛点场景** —— 一个有画面的具体场景
3. **三步用起来** —— 真的只有三步
4. **说句实话** —— 必须有一个真缺点。不说缺点，读者当广告看

## 快速开始

要求：Python 3.8+，`pip install requests`。不需要数据库、不需要 API key、不需要登录。

```bash
git clone https://github.com/1183213030/gh-wechat-digest.git
cd gh-wechat-digest

python scripts/digest.py doctor    # 体检：网络、额度、trending 可达（约 5 秒）
python scripts/digest.py run       # 抓取 + 打分 + 组一期骨架（2-4 分钟）
python scripts/digest.py todo      # 列出哪些段落需要人写
#   ……把文案写进 data/write.json（见下）
python scripts/digest.py apply     # 写回
python scripts/digest.py render    # 出稿：HTML / Markdown / 配图清单
```

打开 `data/reports/issue_日期.html`，点**「复制正文（富文本）」**按钮，粘进公众号编辑器，图片手动拖进去，发布。

### 每天的日常

```bash
python scripts/digest.py run       # 就这一条。之后写文案 → apply → render
```

推过的自动避让（30 天冷却），期号自动 +1。

### 文案为什么要自己写一遍

`run` 出来的是规则拼装的模板文案，读起来像机器稿。工具的分工是：**它管选题和数据，你管"这个项目到底哪里打动人"**——这一步 AI 能代劳大半（如果你在 WorkBuddy 里用，Agent 会按 SKILL.md 的规范自己写），但必须发生，跳过它等于交了一篇 AI 味的通稿。

写法（存成 `data/write.json` 再 `apply`）：

```json
{"title": "我把家里电视的开机广告干掉了，只装了一个 GitHub 项目",
 "intro": ["筛选标准就三条：能装、能看懂、不折腾。"],
 "ending": ["就这些。收藏之前先装一个试试。"],
 "cta": "想让我盯哪个方向，留言说一句。",
 "items": [
   {"which": "main", "fill": {
     "zh_name": "Aerial：给国产电视换一块没有广告的桌面",
     "one_liner": "把开机广告和推荐流一次性清掉，换成照着 Apple TV 做的桌面。",
     "why_now": "10 月 20 日才建库，22 天涨到 1.1 万 star，中文圈还没人写过。",
     "pain": "国产电视烦人的不是硬件，是开机 15 秒的广告位和关不掉的推荐流。",
     "steps": ["电脑和电视连同一个 Wi-Fi，打开电视的 ADB 调试",
                "跑仓库里的 install.sh，不 root、随时能还原",
                "重启电视，开机直接进新桌面"],
     "verdict": "海信要进工厂菜单的机型有风险，这也是它最适合「有人帮你装」的原因。"
   }},
   {"which": "short1", "fill": {"zh_name": "", "one_liner": "", "verdict": ""}}
 ]}
```

`verdict` 必须说真缺点：要门禁、只支持某个系统、许可证不能商用（CC BY-NC / GPL / 无许可证都要点一句）——读者会拿去做别的事。

### 不认同公式选的项目？点名

```bash
python scripts/digest.py pick --main owner/repo --shorts a/b,c/d
```

不重新抓网，直接从当天候选池组一期。公式只是兜底。

## 全部命令

| 命令 | 作用 |
|---|---|
| `doctor` | 体检：Python / requests / token / 额度 / trending 可达 |
| `run` | 抓 trending + 近 30 天新建高星 + 老项目活跃 → 打分 → 组一期 |
| `pick --main --shorts` | 从候选池点名组一期，绕过公式 |
| `todo` | 列出本期哪些段落还是模板文案 |
| `apply` | 读 `data/write.json` 覆盖文案 |
| `render` | 出 HTML（可复制富文本）/ Markdown / 配图清单 |
| `log --url` | 发完记一条，阅读数据以后好复盘 |
| `history` | 看发过几期、发过哪些项目 |

`run` 常用旋钮：`--days 30`（回看窗口）、`--min-stars 400`、`--shorts 3`、`--allow-repeat`（写冷却期内的项目）、`--force`（分数不够也硬出一期）。

## 评分怎么打

满分 100，四维：

| 维度 | 分值 | 判据（节选） |
|---|---|---|
| **有用** | 30 | 有官网、有安装段、应用层语言、体积小 |
| **好讲** | 25 | 简介短且没 buzzword、作者写了中文、有反差词（不用/替代/一键） |
| **可演示** | 20 | README 自带图、有 demo、有官网 |
| **没被写烂** | 25 | 建库 ≤30 天 +16；**当天涨 800+ 星 −6**；来自新建榜 +4 |

硬淘汰：已归档、星 < 200、awesome/合集类、**疑似破解/盗版类**、仓库超 900MB。

**为什么不按星排序**：3 万星以上的项目几十个号都写过；建库 20 天的 1 万星，才是你独有的选题。

## 微信的硬约束（渲染层已处理，但你应该知道）

| 约束 | 处理方式 |
|---|---|
| 编辑器不认 `<style>` / `class` | 全部样式 inline 写在标签上 |
| 不吃 flex / grid | 只用 `section` 嵌套 + padding |
| 正文图片不收外链 | 出**图占位框** + GitHub og 图地址，粘贴时手动插入 |
| 正文链接点不动 | GitHub 地址作纯文本，可点链接放「阅读原文」 |
| 订阅号一天只能群发 1 次 | 天然是"一天一期"的节奏 |

## 数据从哪来（以及为什么没 API key 也能跑）

三条公开通道：`github.com/trending`（今日 + 本周，解析 HTML，拿真实涨星数）、搜索 API `created:>30d stars:>400`（主力）、`pushed:>7d stars:>1500`（老树发新芽）。

省额度设计——**匿名、核心额度为 0 也能跑完整流程**：

- 搜索接口返回的记录自带建库时间、许可证、体积、主页，不用再查详情
- 只有 trending 来的才打 core API；core 用光自动退到 `search?q=repo:owner/name`（搜索额度是另一本账）
- README 一律走 `raw.githubusercontent.com`，零额度消耗

有 token 更快（可选）：`config.json` 填 `gh_token`，或设环境变量 `GH_TOKEN`。申请：[github.com/settings/tokens](https://github.com/settings/tokens) → Generate new token (classic) → 勾 `public_repo`。

## 目录结构

```
├── SKILL.md              WorkBuddy Skill 说明（Agent 契约、文案规范）
├── scripts/
│   ├── digest.py          主入口
│   ├── sources.py         取数：trending + search + raw README
│   ├── score.py           四维打分 + 硬淘汰
│   └── render.py          微信兼容渲染（内联样式、图占位框）
├── examples/              示例稿
└── data/                  运行时产物（gitignore，备份它=备份选题库）
    ├── pool.json           当天候选池
    ├── seen.json          查重账本（30 天冷却）
    ├── published.json     发布记录
    └── reports/           成稿
```

## License

MIT
