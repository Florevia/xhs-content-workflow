下面给你一套**合规、可落地的小红书发文工作流**：用 **Cursor 负责搭建自动化系统/脚本**，用 **Claude 负责选题、文案、标题、封面文案、合规检查和复盘分析**。重点说明：我不建议做“Cookie 登录、绕过验证码、模拟真人批量无人值守发文”这类自动发布；更稳的方式是 **AI 自动生成与打包 + 人工审核 + 小红书官方创作服务平台发布/定时发布 + 数据复盘**。小红书官方创作服务平台本身定位为支持“创作发布、数据分析、商业变现”的创作者工作台；小红书也有分享/开放能力，但分享开放平台页面当前显示“暂停接入”，广告开放平台更多面向账户、投放、报表、蒲公英等经营/广告场景，并不等同于给个人创作者开放通用笔记发布 API。([creator.xiaohongshu.com](https://creator.xiaohongshu.com/?source=official&utm_source=openai))

---

## 一、推荐的整体架构

### 1. 工作流总览

你要搭的不是“自动发垃圾内容机器”，而是一个**内容生产流水线**：

```text
选题池
  ↓
Claude 生成选题角度 / 爆款标题 / 大纲
  ↓
生成小红书笔记正文
  ↓
合规检查 / 品牌调性检查 / 去AI味
  ↓
生成封面文案 / 图片提示词 / 配图清单
  ↓
人工审核
  ↓
导出发布包：标题、正文、话题、封面、图片、发布时间建议
  ↓
小红书创作服务平台手动发布或预约发布
  ↓
人工导出/录入数据
  ↓
Claude 做复盘，反哺选题池
```

### 2. 三种实现级别

| 级别 | 适合人群 | 自动化程度 | 发文方式 |
|---|---|---:|---|
| **MVP 版** | 个人博主、新手 | 低 | Claude 生成内容，手动复制到小红书 |
| **半自动版** | 每周 5-20 篇 | 中 | Cursor 搭系统，自动生成“发布包”，人工审核发布 |
| **团队版** | 品牌、MCN、矩阵账号 | 高 | 选题、审核、素材、排期、数据复盘都系统化，发布仍走官方后台/合规接口 |

如果你只是个人号，我建议从**半自动版**开始：效率高，风险低，不容易把账号做废。

---

## 二、为什么建议用 Cursor + Claude 组合？

### Cursor 适合做什么

Cursor 更适合当“开发型 AI 助手”：帮你建项目、写脚本、改代码、管理文件、接入数据库/API。Cursor 官方文档里有 Agent 模式，可用于复杂功能、多文件编辑和自动探索；也支持 Rules，把你的项目规范写进 `.cursor/rules`，让 AI 每次生成代码时遵守同一套规则；Cursor 还支持通过 MCP 接入数据库、第三方 API 或本地工具。([docs.cursor.com](https://docs.cursor.com/en/agent/modes?utm_source=openai))

### Claude 适合做什么

Claude 更适合做内容策略、长文案、风格迁移、结构化输出、合规审稿和复盘总结。Anthropic 官方提供 Claude API、Messages API、官方 SDK、批量处理能力和结构化输出能力，适合把 Claude 接入你自己的内容生产系统。([platform.claude.com](https://platform.claude.com/docs/en/api/overview?_bhlid=abb55fd6bb47824afd3d69874f6f713f1fc2882c&utm_source=openai))

### MCP 可以怎么用

MCP 可以理解成“让 AI 连接外部工具的标准接口”。Anthropic 文档说明 Claude 产品和 Messages API 都支持 MCP 场景；Cursor 也支持 MCP 工具接入。因此你可以让 Cursor/Claude 读取本地选题表、品牌文档、素材库、数据表，再自动生成发布包。([docs.anthropic.com](https://docs.anthropic.com/en/docs/mcp?utm_source=openai))

---

## 三、先定义你的“小红书发文 SOP”

建议你先把流程写死，不要一上来就写代码。

### 1. 账号定位表

建立一个 `brand_guide.md`：

```md
# 账号定位

账号名称：XXX  
领域：护肤 / 穿搭 / 旅游 / 家居 / 职场 / AI工具 / 母婴 / 健身  
目标用户：25-35岁一线城市女性 / 小白职场人 / 新手妈妈 / 独立设计师  
内容风格：真实、具体、有个人体验、不端着  
禁用风格：营销号、夸张承诺、假装亲测、无依据种草  
核心人设：懂行但不说教，分享踩坑经验  
```

### 2. 内容栏目表

建立 `content_pillars.md`：

```md
# 内容栏目

## 栏目1：避坑类
例：我不建议新手一上来买XXX，原因有3个

## 栏目2：清单类
例：通勤女生包里真正有用的5件东西

## 栏目3：对比类
例：XX和XX怎么选？我的真实使用感受

## 栏目4：教程类
例：3步搞定XXX，新手也能照着做

## 栏目5：故事类
例：我花了半年才明白的一个消费真相
```

### 3. 合规规则表

建立 `compliance_rules.md`：

```md
# 小红书内容合规自查

1. 不写虚假亲测。
2. 不写无法证明的绝对化承诺。
3. 不写“100%有效”“全网第一”“永久解决”等绝对词。
4. 涉及医疗、保健、金融、法律等内容必须加免责声明。
5. 商业合作、广告、赠品体验要按平台和法律要求披露。
6. 不搬运他人图片、文案、评论。
7. 不诱导用户违规私信、站外交易或刷量。
8. 不做批量低质重复内容。
```

---

## 四、用 Cursor 搭一个“发文工作流项目”

### 1. 项目目录建议

让 Cursor 创建这个目录：

```text
xhs-content-workflow/
├── data/
│   ├── topics.csv
│   ├── posts.csv
│   ├── metrics.csv
│   └── competitors.csv
├── docs/
│   ├── brand_guide.md
│   ├── content_pillars.md
│   ├── compliance_rules.md
│   └── style_examples.md
├── prompts/
│   ├── generate_note.md
│   ├── review_note.md
│   ├── create_cover.md
│   └── analyze_metrics.md
├── output/
│   └── publish_packages/
├── src/
│   ├── generate_note.py
│   ├── review_note.py
│   ├── export_package.py
│   ├── analyze_metrics.py
│   └── utils.py
├── .env
├── requirements.txt
└── README.md
```

### 2. 给 Cursor 的第一条指令

你可以直接在 Cursor 里输入：

```text
请帮我创建一个 Python 项目，用于小红书内容生产工作流。

需求：
1. 从 data/topics.csv 读取选题。
2. 调用 Claude API 生成小红书笔记，包括：
   - 标题候选 5 个
   - 正文
   - 封面文案 3 个
   - 配图建议
   - 话题标签
   - 发布时间建议
   - 合规风险提示
3. 生成结果保存到 output/publish_packages/，每个选题一个 Markdown 文件。
4. 支持人工审核状态：draft / reviewed / published。
5. 不做自动登录小红书，不做 Cookie 操作，不做绕过风控，只生成发布包。
6. 代码要清晰，方便后续接入 Notion、飞书或 Airtable。
```

### 3. 添加 Cursor Rules

在 `.cursor/rules/xhs-workflow.mdc` 写：

```md
---
description: 小红书内容工作流项目规则
alwaysApply: true
---

# 项目规则

1. 本项目只做内容生成、审核、打包、复盘，不做自动登录、Cookie 采集、验证码绕过、批量无人值守发布。
2. 所有生成内容必须经过合规检查。
3. 涉及医疗、金融、法律、母婴、功效类内容，要自动提示风险。
4. 输出内容要真实、具体、像真人经验分享，避免营销号语气。
5. 每篇笔记必须包含：
   - 标题候选
   - 正文
   - 封面文案
   - 配图建议
   - 标签
   - 合规审查
   - 发布建议
6. 代码优先使用 Python，环境变量从 .env 读取。
```

这样 Cursor 之后帮你写代码时，会默认遵守这些约束。

---

## 五、核心数据表怎么设计

### 1. `data/topics.csv`

```csv
id,topic,category,audience,angle,status
001,新手如何选择第一台咖啡机,家居生活,租房女生,避坑,draft
002,通勤包里真正有用的5件东西,职场穿搭,上班族女生,清单,draft
003,我为什么不再盲买网红护肤品,护肤,敏感肌女生,经验,draft
```

### 2. `data/posts.csv`

```csv
id,topic_id,title,body,hashtags,status,publish_time,note_url
001,001,标题示例,正文示例,#咖啡机 #租房生活,reviewed,,
```

### 3. `data/metrics.csv`

```csv
post_id,date,views,likes,saves,comments,shares,follows
001,2026-06-26,1200,80,35,12,5,9
```

---

## 六、Claude 生成笔记的提示词模板

保存为 `prompts/generate_note.md`：

```md
你是一个资深小红书内容策划，请根据以下信息生成一篇适合小红书发布的笔记。

## 账号定位
{brand_guide}

## 内容栏目
{content_pillars}

## 合规规则
{compliance_rules}

## 选题信息
选题：{topic}
分类：{category}
目标用户：{audience}
角度：{angle}

## 输出要求
请输出 JSON，字段如下：

{
  "titles": ["标题1", "标题2", "标题3", "标题4", "标题5"],
  "recommended_title": "推荐标题",
  "cover_texts": ["封面文案1", "封面文案2", "封面文案3"],
  "body": "小红书正文",
  "hashtags": ["标签1", "标签2", "标签3"],
  "image_suggestions": ["图1建议", "图2建议", "图3建议"],
  "publish_time_suggestion": "建议发布时间",
  "compliance_check": {
    "risk_level": "low / medium / high",
    "risks": ["风险1", "风险2"],
    "rewrite_suggestions": ["建议1", "建议2"]
  }
}

## 风格要求
1. 像真实用户分享，不要像广告。
2. 开头要有具体场景或痛点。
3. 多用“我踩过的坑”“真实感受”“适合/不适合谁”。
4. 不要夸大功效。
5. 不要编造亲身经历。
6. 不要写无法验证的数据。
7. 不要使用明显 AI 腔。
```

---

## 七、Claude API 代码示例

### 1. 安装依赖

`requirements.txt`：

```txt
anthropic
python-dotenv
pandas
```

安装：

```bash
pip install -r requirements.txt
```

### 2. `.env`

```env
ANTHROPIC_API_KEY=你的Claude API Key
CLAUDE_MODEL=你当前可用的Claude模型名
```

### 3. `src/generate_note.py`

```python
import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
PROMPTS_DIR = ROOT / "prompts"
OUTPUT_DIR = ROOT / "output" / "publish_packages"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = os.getenv("CLAUDE_MODEL")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_prompt(row):
    template = read_text(PROMPTS_DIR / "generate_note.md")

    return template.format(
        brand_guide=read_text(DOCS_DIR / "brand_guide.md"),
        content_pillars=read_text(DOCS_DIR / "content_pillars.md"),
        compliance_rules=read_text(DOCS_DIR / "compliance_rules.md"),
        topic=row["topic"],
        category=row["category"],
        audience=row["audience"],
        angle=row["angle"],
    )


def call_claude(prompt: str) -> str:
    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system="你是一个小红书内容策略专家和合规审稿人。请严格按用户要求输出 JSON，不要输出多余解释。",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return message.content[0].text


def save_package(row, result_text: str):
    topic_id = row["id"]
    topic = row["topic"]

    output_path = OUTPUT_DIR / f"{topic_id}_{topic}.md"

    content = f"""# 小红书发布包

## 选题
{topic}

## 基础信息
- ID: {topic_id}
- 分类: {row["category"]}
- 目标用户: {row["audience"]}
- 角度: {row["angle"]}

## Claude 输出

```json
{result_text}
```

## 人工审核区

- 审核状态：draft
- 是否需要重写：
- 发布日期：
- 小红书链接：
- 备注：
"""

    output_path.write_text(content, encoding="utf-8")
    print(f"已生成：{output_path}")


def main():
    topics = pd.read_csv(DATA_DIR / "topics.csv")

    drafts = topics[topics["status"] == "draft"]

    for _, row in drafts.iterrows():
        prompt = build_prompt(row)
        result = call_claude(prompt)
        save_package(row, result)


if __name__ == "__main__":
    main()
```

运行：

```bash
python src/generate_note.py
```

---

## 八、加一个“合规审稿”环节

生成之后，最好再让 Claude 单独审一遍，而不是直接用。

### `prompts/review_note.md`

```md
你是小红书内容合规审核员，请检查以下笔记是否存在风险。

## 审核维度
1. 是否夸大功效
2. 是否虚假种草
3. 是否像广告软文
4. 是否有医疗/金融/法律等敏感表述
5. 是否可能侵犯他人版权
6. 是否标题党
7. 是否有诱导违规互动
8. 是否缺少商业合作披露

## 输出格式

{
  "risk_level": "low / medium / high",
  "problems": [],
  "rewrite_advice": [],
  "safe_version": "修改后的安全版本"
}

## 待审核内容
{note}
```

### 审稿标准

你可以规定：

- `low`：可以发布。
- `medium`：人工改完再发。
- `high`：不发，重写。

---

## 九、发布包应该长什么样？

每一篇最终导出成这样的 Markdown：

```md
# 发布包：新手如何选择第一台咖啡机

## 推荐标题
新手买咖啡机前，先看完这5个坑

## 备选标题
1. 第一台咖啡机别乱买，我踩过这些坑
2. 租房党买咖啡机，真的要想清楚这几点
3. 新手咖啡机怎么选？不是越贵越好
4. 买咖啡机前，我希望有人早点告诉我这些
5. 适合新手的咖啡机选择思路

## 封面文案
第一台咖啡机  
别急着买贵的

## 正文
之前我也以为，买咖啡机就是预算越高越好。  
后来用了一段时间才发现，新手真正需要考虑的不是参数有多漂亮，而是这几个问题：

1. 你每天真的会用吗？
2. 你能接受清洗成本吗？
3. 你喜欢美式、拿铁还是意式？
4. 家里有没有足够空间？
5. 后续耗材贵不贵？

如果只是偶尔喝，我反而不建议一开始就上很复杂的机器。  
可以先从更简单的设备开始，确认自己真的有这个习惯，再升级也不迟。

我的建议是：
- 每天喝：可以考虑半自动或全自动
- 偶尔喝：胶囊机/手冲可能更合适
- 想练技术：半自动更有参与感
- 怕麻烦：清洗方便比参数更重要

总之，第一台不用追求一步到位，适合自己的使用频率最重要。

## 话题
#咖啡机 #租房生活 #家居好物 #新手咖啡 #咖啡日常

## 配图建议
1. 封面：咖啡机+大字标题
2. 图2：不同类型咖啡机对比
3. 图3：购买前自查清单
4. 图4：适合/不适合人群
5. 图5：个人总结

## 合规检查
风险等级：低  
注意事项：不要写成品牌硬广；如果有品牌合作，需要披露。
```

---

## 十、封面图工作流

小红书很吃封面。建议封面生产也标准化。

### 1. 封面模板

固定 3 类：

```text
模板 A：大字痛点型
例：第一台咖啡机，别急着买贵的

模板 B：清单型
例：买咖啡机前必看 5 点

模板 C：对比型
例：胶囊机 vs 半自动，新手怎么选？
```

### 2. Claude 生成封面文案提示词

```md
请为以下小红书笔记生成 10 个封面大字标题。

要求：
1. 每个不超过两行。
2. 口语化。
3. 有痛点。
4. 不夸张。
5. 不使用“全网最”“必买”“100%”等绝对词。

笔记主题：{topic}
目标用户：{audience}
正文摘要：{summary}
```

### 3. 图片制作方案

你可以用：

- Canva / 稿定设计：手动套模板。
- Figma：做统一品牌模板。
- Python PIL：批量生成简单封面。
- Midjourney / 即梦 / 可灵 / Stable Diffusion：生成背景图，再手动加字。
- 不建议直接搬运别人的小红书图。

---

## 十一、发布环节怎么做最稳？

### 推荐方式：官方后台 + 人工确认

流程：

```text
打开小红书创作服务平台
  ↓
上传图片/视频
  ↓
复制标题
  ↓
复制正文
  ↓
添加话题
  ↓
检查封面
  ↓
预览
  ↓
发布或预约
```

小红书官方创作服务平台页面明确是“创作发布、数据分析、商业变现”相关的创作者工作台，所以发布环节优先走官方入口。([creator.xiaohongshu.com](https://creator.xiaohongshu.com/?source=official&utm_source=openai))

### 不建议做什么

不建议你让 Cursor 写：

```text
自动登录小红书
读取 Cookie
调用未公开接口
模拟点击批量发布
绕过验证码
多账号批量发相似内容
```

原因很简单：账号风险高、维护成本高、容易触发风控，也不适合长期品牌运营。你真正该自动化的是**选题、文案、审核、封面、排期和复盘**，而不是强行自动点“发布”。

---

## 十二、如果你想做“半自动填充”

可以做一个**本地发布助手**，但只做安全动作：

### 可以做

- 自动复制标题到剪贴板。
- 自动复制正文到剪贴板。
- 打开本地发布包。
- 打开小红书创作服务平台。
- 标记该篇为 `reviewed` 或 `published`。
- 记录发布时间和链接。

### 不建议做

- 自动输入账号密码。
- 自动读取浏览器 Cookie。
- 自动绕过验证码。
- 自动点击发布按钮。
- 自动批量切换账号。

一个简单的本地助手可以这样设计：

```text
python src/export_package.py --id 001
```

输出：

```text
已复制标题到剪贴板
按 Enter 复制正文
按 Enter 复制话题
请手动上传图片并发布
```

---

## 十三、数据复盘工作流

发布后不要只看点赞，要记录完整数据。

### 1. 手动维护 `metrics.csv`

```csv
post_id,date,views,likes,saves,comments,shares,follows
001,2026-06-27,1200,80,35,12,5,9
001,2026-06-29,2300,156,92,28,16,21
```

### 2. 计算核心指标

```text
点赞率 = likes / views
收藏率 = saves / views
评论率 = comments / views
关注转化率 = follows / views
互动率 = (likes + saves + comments + shares) / views
```

### 3. Claude 复盘提示词

```md
你是小红书运营分析师，请根据以下数据复盘内容表现。

## 数据
{metrics}

## 笔记内容
{post}

## 请分析
1. 这篇笔记表现好/差的原因
2. 标题是否有效
3. 封面是否有效
4. 正文结构是否有问题
5. 用户评论可能反映了什么需求
6. 后续可以延展出哪些选题
7. 下次如何优化

请输出：
- 结论
- 问题
- 可复用经验
- 下周选题建议
```

---

## 十四、适合团队的高级版流程

如果你是品牌或团队，可以加审核流。

```text
选题状态：
idea → selected → drafting → reviewed → scheduled → published → analyzed
```

### 角色分工

| 角色 | 负责内容 |
|---|---|
| 运营 | 选题、排期、数据复盘 |
| Claude | 初稿、标题、审稿、复盘 |
| 设计 | 封面和配图 |
| 负责人 | 合规和最终发布 |
| Cursor 系统 | 文件、表格、脚本、自动导出 |

### 审核字段

```csv
id,topic,status,writer,reviewer,risk_level,scheduled_time,published_url
001,咖啡机选择,reviewed,Claude,运营,low,2026-06-27 20:00,
```

---

## 十五、用 Claude 网页版也能跑的简化版

如果你暂时不想写代码，可以这样：

### Step 1：把这几个文档上传给 Claude

- 账号定位
- 爆款案例
- 禁用词/合规规则
- 历史数据
- 选题表

### Step 2：给 Claude 一个总控提示词

```md
你是我的小红书内容运营助手。

我的账号定位如下：


我的内容栏目如下：


请帮我完成：
1. 生成10个选题
2. 每个选题给3个标题
3. 选择最值得发的5个
4. 为第1个选题写完整笔记
5. 生成封面文案
6. 做合规检查
7. 给出发布时间建议

要求：
- 真实口语化
- 不要营销号
- 不要夸大
- 不要编造经历
- 输出适合直接复制到小红书的版本
```

### Step 3：人工发布

复制到小红书创作服务平台或 App 发布。

---

## 十六、最小可行版本：今天就能做

如果你想最快跑起来，按这个来：

### 第 1 步：准备 3 个文件

```text
brand_guide.md
content_pillars.md
topics.csv
```

### 第 2 步：让 Cursor 建项目

使用上面的 Cursor 指令。

### 第 3 步：用 Claude 生成 10 篇发布包

先不追求自动化完美，生成 Markdown 就够。

### 第 4 步：人工筛选 3 篇

重点看：

```text
标题是否像真人？
开头是否有场景？
正文是否具体？
有没有夸张承诺？
封面文案是否一眼能懂？
```

### 第 5 步：官方后台发布

使用小红书官方创作服务平台或 App。

### 第 6 步：48 小时后复盘

把数据填进 `metrics.csv`，让 Claude 总结下一轮选题。

---

## 十七、我建议你的最终系统形态

```text
Cursor 项目
  ├── 选题管理
  ├── Claude 文案生成
  ├── Claude 合规审核
  ├── 封面文案生成
  ├── 发布包导出
  ├── 数据录入
  └── 复盘分析

发布动作
  └── 人工通过小红书官方入口完成
```

一句话总结：

> **让 AI 做“内容生产和决策辅助”，让人做“审核和最终发布”。**  
> 这样效率能提升很多，同时不会把账号暴露在自动化风控风险里。