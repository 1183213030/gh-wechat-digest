"""给读者复制的「让 AI 帮我装」提示词。

为什么单独成模块：这段文字是整组文章的骨架，四篇里的写法必须一致 ——
读者第一次照着做成功了，第二次才会信。所以规则固定在这里，不要每次临时编。

三条底线，任何变体都不许破：
  1. 一次一步，等用户确认（AI 连着跑十条命令，出了问题没人知道是哪条坏的）
  2. 报错要原文，不许"我再试试别的"（连着换方案会把环境搞脏）
  3. 不许动系统目录、不许 sudo 删东西、依赖装进虚拟环境
"""

FORM_KIND = {
    "电视/Android": "tv",
    "手机/电视 App": "tv",
    "命令行": "cli",
    "Agent 技能": "skill",
    "插件": "skill",
    "桌面应用": "desktop",
    "网页应用": "web",
    "引擎/库": "lib",
}

COMMON_RULES = [
    "1. 先把 README 和安装文档读完再动手，不要凭印象给命令；文档和我的系统对不上时，先告诉我哪里对不上。",
    "2. 一次只做一步：每步先说要干什么、有没有风险，等我回「继续」再执行下一条。",
    "3. 命令你自己执行，不要只把步骤贴给我。需要我在电视/手机/浏览器上点的，明确告诉我点哪里。",
    "4. 报错就把原始输出贴给我看，先解释原因再修；不要连着换三种方案试。",
    "5. 不要动系统目录，不要 sudo 删任何东西，不要改我已经装好的环境；要装依赖就新建虚拟环境或独立目录。",
]

VERIFY = {
    "tv": [
        "装完按这几条验收，把原始输出贴给我（不要总结）：",
        "- adb shell \"cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.HOME\"",
        "- adb shell settings get secure enabled_accessibility_services",
        "- 按主页键后跑 adb shell \"dumpsys window | grep mCurrentFocus\"",
    ],
    "cli": [
        "装完给我三条证据：命令能跑起来（打印 help）、版本号、以及一次最小可用的真实调用结果。",
    ],
    "skill": [
        "装完告诉我：技能装在哪个目录、AI 怎么触发它、以及一次最小的试用输出。",
    ],
    "desktop": [
        "装完给我：程序所在路径、版本号、以及第一次启动后的截图或窗口标题。",
    ],
    "web": [
        "装完给我：本地访问地址、启动命令、以及页面能打开的证据（截图或 curl 的状态码）。",
    ],
    "lib": [
        "装完给我：import 成功的最小示例输出，以及版本号。",
    ],
}


def _kind(item):
    return FORM_KIND.get(item.get("form") or "", "cli")


def prompt_for(item, os_hint="Windows / macOS / Linux 都可以，你先查出来"):
    """生成一段可直接粘贴的提示词（行列表，渲染时一行一个 <p>）。"""
    name = item.get("zh_name") or item.get("full_name")
    kind = _kind(item)
    lines = [
        f"帮我在我自己的电脑上装好这个开源项目，你负责装，我负责确认。",
        "",
        f"项目：{name}",
        f"仓库：{item.get('url') or 'https://github.com/' + item.get('full_name', '')}",
    ]
    if item.get("one_liner"):
        lines.append(f"它是什么：{item['one_liner']}")
    lines += [
        f"我的系统：{os_hint}",
        "",
        "要求：",
    ]
    lines += COMMON_RULES
    lines += [""] + VERIFY.get(kind, VERIFY["cli"])
    return lines


def prompt_tv(item, tv_ip="<电视IP>"):
    """电视类单独一支：多一步「电视上要你自己点」，也多一条配对提醒。"""
    lines = prompt_for(item, os_hint=f"电脑是 Windows，电视 IP 是 {tv_ip}，两个设备在同一个 Wi-Fi")
    # 插在要求之前更自然
    try:
        i = lines.index("要求：")
        lines[i:i] = [
            "电视已经打开了 ADB 调试（没有的话先告诉我在哪个菜单里开，我按品牌型号去开）。",
        ]
    except ValueError:
        pass
    return lines


def followups(kind="cli"):
    """装的过程中大概率要追问的三句，直接给读者抄。"""
    base = [
        ("它卡住了/报错了", "把完整报错原文贴给你，然后问「这是什么原因，下一步只给我一条命令」"),
        ("它想让我装一堆东西", "先问「哪些是必须的，哪些可以跳过」，再问「能不能装进虚拟环境，别动我的全局」"),
        ("它说装好了但用不了", "让它自己跑一遍验收命令，把输出贴出来，对不上就继续修"),
    ]
    if kind == "tv":
        base.insert(0, ("电视上找不到 ADB 开关", "告诉它电视品牌 + 型号 + 系统版本，让它按这个型号给具体路径，别给通用步骤"))
    return base
