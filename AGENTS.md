# AGENTS.md

> 本文件是本仓库（`xhs-content-workflow`）的项目说明书，适用于所有 Agent（Cursor / Claude Code / Codex 等）。
> 本文件与 `.cursor/rules/xhs-workflow.mdc` 保持同步。修改任意一份规则时，请同步更新另一份。

## 0. 项目是什么

一个小红书内容生产与"半自动"发布工作流：从选题/本地草稿生成结构化发布包（标题、正文、封面文案、图片提示词、合规审查），经人工审核后调用 ChatGPT 生图脚本自动生图，再调用本机已有的小红书自动化 CLI 一步发布。**本项目本身不做自动登录、不读取 Cookie、不绕过验证码、不做批量无人值守发布**——发布动作永远经过人工审核确认（或显式 `--yes`），并且只通过既有 CLI 执行。

核心流程见 `README.md` 中的 mermaid 流程图与 `docs/xhs-auto-publish-flow.drawio`。

---

## 1. 项目结构

```text
workflow/
├── AGENTS.md                      # 本文件：项目说明书（唯一规则源）
├── CLAUDE.md                      # 指向 AGENTS.md，不单独维护规则
├── README.md                      # 使用说明、初始化步骤、命令示例
├── .env.example / .env            # 环境变量模板 / 本地真实密钥（.env 已 gitignore，不得提交）
├── requirements.txt                # Python 依赖（当前仅 anthropic，标准库优先）
├── .cursor/rules/xhs-workflow.mdc  # Cursor 规则文件，与本文件保持同步
│
├── config/
│   └── image_prompt_profiles.json # 图片提示词模板配置（global_quality_rules / profiles / fallback_profile）
│
├── data/                          # 选题与复盘数据表（CSV，可编辑）
│   ├── topics.csv                 # 选题池，status=draft 的行会被生成
│   ├── posts.csv
│   ├── metrics.csv                # 发布后手动维护的数据复盘表
│   └── competitors.csv
│
├── docs/                          # 账号定位 / 栏目 / 合规 / 风格文档，会被拼进生成 Prompt
│   ├── brand_guide.md
│   ├── content_pillars.md
│   ├── compliance_rules.md        # 合规自查清单，新增合规规则改这里
│   ├── style_examples.md
│   └── xhs-auto-publish-flow.drawio
│
├── prompts/                       # Claude 提示词模板（Jinja 风格 {占位符}，见 prompts.py）
│   ├── generate_note.md           # ⚠️ 有单测断言固定关键字符串，改动需同步改 tests
│   ├── review_note.md
│   ├── create_cover.md
│   ├── analyze_metrics.md
│   └── image_profiles/*.md        # 各图片 Profile 的说明文档（非代码消费，供人阅读维护）
│
├── drafts/                        # 无 API 模式下手写的草稿 JSON（输入，可编辑/新增）
│
├── output/
│   ├── publish_packages/*.{md,json}  # 生成的发布包（已 gitignore，运行时产物，不要手改）
│   └── published_images/             # 按 MM-DD/发布包名 存放的生图（已 gitignore）
│
├── archive/                       # 已完成发布的一批产物的最终归档（见第 8 节归档规则）
│   └── YYYY-MM-DD_标题/
│       ├── content.json / title.txt / content.txt
│       ├── image_prompts_batch.json
│       └── images/
│
├── src/
│   ├── generate_note.py           # CLI：Claude API 批量生成发布包
│   ├── review_note.py             # CLI：单独跑合规审核
│   ├── create_package.py          # CLI：无 API 模式，从 drafts/*.json 生成发布包
│   ├── export_package.py          # CLI：导出/复制发布包内容（标题、正文剪贴板等）
│   ├── auto_publish.py            # CLI：生成/读取发布包 → 人工审核 → 生图 → 发布 一条龙
│   ├── analyze_metrics.py         # CLI：数据复盘（本地统计 + 可选 Claude 深度复盘）
│   └── xhs_workflow/              # 核心逻辑包（所有业务逻辑都应该在这里，CLI 只做参数解析和编排）
│       ├── topics.py              # 读取 data/topics.csv
│       ├── prompts.py             # 模板渲染（render_prompt / read_text）
│       ├── claude_client.py       # Anthropic API 封装 + .env 加载 + JSON 提取
│       ├── generate.py            # 组装生成 Prompt、调用 Claude、落地生成结果
│       ├── research.py            # 生成前 Claude web search → research_brief
│       ├── image_prompt_profiles.py # 图片模板匹配与 prompt 拼装（config/image_prompt_profiles.json 消费者）
│       ├── images.py              # 生图批次拆分、调用外部 chatgpt_automation.py、结果校验
│       ├── draft_package.py       # 无 API 模式：草稿 JSON 校验 + 转发布包
│       ├── packages.py            # PublishPackage 数据结构、Markdown/JSON 读写
│       ├── publish.py             # 拼装并调用外部小红书 CLI 发布命令、状态回写
│       ├── automation.py          # auto_publish_package：审核 → 生图 → 发布 的编排与风险拦截
│       ├── analysis.py            # 复盘相关逻辑
│       ├── export.py              # 导出逻辑
│       ├── metrics.py             # metrics.csv 统计（点赞率/互动率等）
│       └── review.py              # 合规审核相关逻辑
│
└── tests/
    └── test_core.py               # 唯一单测文件，unittest，覆盖 xhs_workflow 全部核心模块
```

### 关键外部依赖（不在本仓库内，但被本项目硬编码引用）

以下路径不属于本仓库，但代码和测试里写死了绝对路径，修改前必须确认它们存在且接口未变：

- `/Users/lilin/.claude/skills/xiaohongshu-skills/scripts/cli.py`：小红书发布 CLI（`publish.py` 调用）。
- `/Users/lilin/.claude/skills/lilin-rednote/scripts/chatgpt_automation.py`：ChatGPT 自动生图脚本（`images.py` 调用）。**`tests/test_core.py` 里的 `ImageAutomationTests` 会直接 `importlib` 加载这个外部文件**（例如 `test_chatgpt_automation_defaults_to_scoheart_google_account`、`test_generate_batch_waits_longer_and_does_not_restart_session_after_send`），断言其中的 `GOOGLE_ACCOUNT_NAME`、`USE_GOOGLE_ACCOUNT_CHOOSER`、`ChatGPTAutomator.generate_batch` 等符号。如果这个外部脚本被改动或不存在，`PYTHONPATH=src python3 -m unittest discover -s tests` 会直接报错/失败，这不代表本仓库代码有问题，需要先确认外部脚本路径和实现是否变化。

---

## 2. 哪些文件可以改，哪些不能

### 可以自由修改

- `src/xhs_workflow/**/*.py`、`src/*.py`：核心逻辑与 CLI，主战场。
- `tests/test_core.py`：新增/修改功能必须同步改。
- `docs/*.md`：账号定位、栏目、合规规则、风格示例——改了会直接影响生成结果，改动需过一遍第 4 节合规检查。
- `prompts/*.md`：Prompt 模板。**改 `prompts/generate_note.md` 前先看 `tests/test_core.py::PromptTests.test_checked_in_generate_template_includes_visual_planner_rules`**，里面断言了一批必须存在的固定字符串（如"必须竖版 3:4""1000 字""不要任何水印或品牌标识"等）。如果业务上确实要改这些约束，必须同步改测试断言，不能只改模板。
- `config/image_prompt_profiles.json`：图片模板配置，新增/调整 profile 时要保证 `fallback_profile` 始终指向一个存在的 profile。
- `data/*.csv`、`drafts/*.json`：业务数据/草稿输入。
- `README.md`、`.env.example`：新增配置项/命令时同步更新。
- `AGENTS.md` / `.cursor/rules/xhs-workflow.mdc` / `CLAUDE.md`：规则文档，改动必须两处同步（见第 7 节）。

### 只能通过脚本生成，禁止手改/手删（除清理临时文件外）

- `output/publish_packages/*.md` / `*.json`：由 `create_package.py` / `generate_note.py` / `auto_publish.py` 生成，已 gitignore。需要改内容应该改草稿/Prompt/脚本重新生成，而不是手改产物 JSON（`publish_status`、`note_url` 等字段由 `publish.py::update_publish_status` 统一回写）。
- `output/published_images/`：生图产物目录，已 gitignore，不要手工塞图片进去。
- `archive/<日期_标题>/`：一旦某批内容归档完成，其内容视为最终交付物，不应再手改；如需重新生成，应该在新的一次运行中产生新的归档目录，不要覆盖旧归档。

### 禁止修改 / 修改前必须格外谨慎

- 外部路径（见第 1 节"关键外部依赖"）：`/Users/lilin/.claude/skills/xiaohongshu-skills/scripts/cli.py` 与 `/Users/lilin/.claude/skills/lilin-rednote/scripts/chatgpt_automation.py`。这两个文件不属于本仓库，不要在本项目的开发任务里顺手修改它们；如果确实需要改动，必须先明确这是跨项目改动，并重新跑一遍 `tests/test_core.py::ImageAutomationTests`。
- `.env`：包含真实密钥，不能提交到 git，也不要把里面的值写死进代码或测试。
- 任何"自动登录 / 读取 Cookie / 绕过验证码 / 批量无人值守发布"相关的代码——这是本项目的红线（见第 6 节业务规则第 1 条），不允许新增此类实现，即使用户临时要求，也应提示风险并拒绝。
- `tests/__pycache__/`：构建产物，不要提交、不要手动编辑。

---

## 3. 修改规则

1. **改动前先跑测试**：`PYTHONPATH=src python3 -m unittest discover -s tests -v`，确认当前基线是绿的，再开始改。
2. **核心逻辑必须放进 `src/xhs_workflow/`，CLI 脚本只做编排**：`src/*.py` 里的 `main()` 应该只解析参数、调用 `xhs_workflow` 里的函数、打印结果，不要把业务逻辑写在 CLI 脚本里（参考 `auto_publish.py` 的写法：参数解析 → 调用 `automation.auto_publish_package` → 打印）。
3. **I/O 与纯逻辑分离**：涉及网络请求（Claude API）、子进程调用（`subprocess.run` 调 CLI/生图脚本）、文件读写的函数，尽量保持薄一层，把可测试的纯逻辑（拼 prompt、拼 command、算指标、校验草稿）拆成独立函数，方便用 `unittest.mock.patch` 打桩测试（参考 `images.py::build_chatgpt_command` / `generate_images` 的拆分方式）。
4. **错误类型要显式、语义化**：新增校验失败场景时，优先复用或新增专用异常类（如 `DraftValidationError`、`ReviewRejected`、`ClaudeConfigError`），不要用裸 `Exception` 或字符串判断错误类型。
5. **风险拦截逻辑集中在 `automation.py`**：任何"高风险内容不能自动发布""未审核不能无人值守发布"之类的门禁规则，改在 `auto_publish_package` 里，不要分散到 CLI 脚本或 `publish.py` 里各写一份。
6. **模板/配置类改动要考虑向后兼容**：`config/image_prompt_profiles.json` 和 `prompts/*.md` 是被代码解析的"半结构化数据"，新增字段要给默认值/兜底逻辑，不能假设所有旧草稿/旧配置都有新字段。
7. **涉及路径的代码统一用 `pathlib.Path`**，不要用字符串拼路径；涉及外部命令统一构造成 `list[str]` 传给 `subprocess.run(..., check=False)` 并显式处理非零退出码（参考 `publish.py::publish_package`）。
8. **业务规则变更（第 6 节 1-8 条）需要谨慎**：那是产品/合规红线，不是普通代码规范，改动前确认是用户/仓库所有者明确要求，而不是顺手"优化"。

---

## 4. 新增功能要补什么测试

本项目只有一个测试文件 `tests/test_core.py`，用 `unittest`，按模块分 `TestCase`（如 `PromptTests`、`TopicTests`、`PackageTests`、`DraftPackageTests`、`GenerationResultTests`、`ImageAutomationTests`、`PublishAutomationTests`、`MetricsTests`、`AutoPublishFlowTests`）。新增功能时：

1. **优先归类到已有 `TestCase`**；只有新增一个新模块时才新建 `TestCase` 类。
2. **纯函数**（模板渲染、prompt 拼装、CSV 解析、指标计算、command 拼装）：直接写输入输出断言，不需要 mock。
3. **涉及文件系统**（读写发布包、草稿、图片目录）：必须用 `tempfile.TemporaryDirectory()`，不要读写仓库里的真实 `output/` / `drafts/` / `archive/` 目录，也不要在测试里依赖当前工作目录状态。
4. **涉及外部进程/网络**（`subprocess.run` 调小红书 CLI / ChatGPT 生图脚本、Anthropic API）：必须用 `unittest.mock.patch` 打桩（参考 `test_generate_images_runs_chatgpt_script_with_batch_file_and_env` 用 `patch("xhs_workflow.images.subprocess.run", ...)`），**测试里永远不能真的调用外部小红书 CLI、真的生图、真的发布、真的打 Claude API**。
5. **新增/修改合规或审核门禁逻辑**（如新增一种"高风险自动拒绝"的场景）：必须在 `AutoPublishFlowTests` 里补对应的正向（正常通过）和负向（被 `ReviewRejected` 拦截）用例。
6. **新增图片 Profile 或改 `image_prompt_profiles.json` 结构**：在 `DraftPackageTests` / `GenerationResultTests` 里补测试，覆盖：命中 profile、走 fallback、保留用户手写 `image_prompts` 不被覆盖 三种路径。
7. **改 `prompts/generate_note.md` 里对生成结果有硬约束的内容**（字数、比例、水印禁令等）：同步更新 `PromptTests.test_checked_in_generate_template_includes_visual_planner_rules` 里的断言字符串。
8. **改动会影响外部 `chatgpt_automation.py` 契约的行为**（如批次大小、等待时长、Google 账号选择逻辑）：确认 `ImageAutomationTests` 里对应用例仍然成立，必要时同步修改外部脚本和测试。
9. 新增测试后，不需要额外的测试框架/依赖（不要引入 pytest、coverage 等），保持标准库 `unittest`，与 `requirements.txt` 保持最小化一致。

---

## 5. 改完后必须跑哪些命令

```bash
# 1. 单测（必须，改完任何 .py / prompts / config 都要跑一遍）
PYTHONPATH=src python3 -m unittest discover -s tests -v

# 2. 语法/导入自检（改了哪个文件就至少 compile 一下，避免低级语法错误）
python3 -m py_compile src/xhs_workflow/*.py src/*.py

# 3. 如果改动涉及"无 API 模式"生成发布包，端到端跑一次真实草稿验证（不要用仓库外的真实 drafts）
PYTHONPATH=src python3 src/create_package.py drafts/<某个草稿>.json

# 4. 如果改动涉及数据复盘逻辑
PYTHONPATH=src python3 src/analyze_metrics.py
```

**不要在日常改动验证时跑以下命令**（会触发真实外部副作用，只能在明确要发布/生图时、且已完成人工审核后才允许执行）：

```bash
PYTHONPATH=src python3 src/auto_publish.py            # 会真实调用生图 + 发布 CLI
PYTHONPATH=src python3 src/auto_publish.py --package ...
PYTHONPATH=src python3 src/generate_note.py            # 会真实消耗 ANTHROPIC_API_KEY 额度
```

本项目当前没有配置 lint/type-check 工具（无 `ruff`/`flake8`/`mypy` 配置，`requirements.txt` 只有 `anthropic`）。**不要擅自引入新的 lint/格式化工具或改变依赖管理方式**；如确需引入，先跟仓库所有者确认，并同步更新 `requirements.txt` 和本节命令列表。

---

## 6. 代码风格

以 `src/xhs_workflow/` 现有代码为准，风格特征：

- 每个模块顶部第一行是 `from __future__ import annotations`。
- 类型注解使用现代写法：`list[str]`、`dict[str, Any]`、`Path | None`，不用 `typing.List`/`typing.Optional`。
- 公共函数/类都有一行中文或英文 docstring，说明这个函数做什么（本仓库混用中英文 docstring，风格上以"一句话说明用途"为准，不写参数级 docstring）。
- 函数命名用动词开头、`snake_case`：`build_xxx`（纯构造）、`resolve_xxx`（查找/决策）、`write_xxx`（落盘）、`update_xxx`（原地修改状态）、`validate_xxx`（校验并可能抛异常）。私有辅助函数以 `_` 前缀（如 `_get`、`_as_list`、`_strip_markdown_fence`）。
- 数据结构优先用 `dataclass`（参考 `packages.py::PublishPackage`），不要用裸 `dict` 在多个函数间传递结构化的业务对象。
- 异常类继承自合适的内建异常（如 `class DraftValidationError(ValueError)`、`class ReviewRejected(RuntimeError)`），类名语义清晰，放在使用它的模块里。
- 面向用户的字符串（CLI 输出、prompt 模板、错误提示）一律用中文，符合小红书内容工作流的中文业务场景；变量名、函数名、注释用英文/中文均可，但同一文件内保持一致，不要中英文变量名混杂。
- 常量大写下划线（如 `DEFAULT_MODEL`、`DEFAULT_XHS_CLI_PATH`、`CONFIRM_TEXT`），写在模块顶部。
- 不写"翻译代码"式的废话注释；只在解释"为什么"（如非显而易见的等待时长、外部脚本的隐藏依赖关系）时才加注释（参考 `.env.example` 里关于 `XHS_SKILLS_SCRIPTS_DIR` 的注释）。
- 缩进 4 空格，字符串优先双引号，与现有代码保持一致。
- Python 版本以 `X | None`、`match`-free 的写法为准（未见 `match` 语句使用），无需兼容 Python 3.9 以下。

---

## 7. 文档同步规则

- 本文件（`AGENTS.md`）是规则唯一权威来源；`.cursor/rules/xhs-workflow.mdc` 必须与本文件保持内容一致（尤其是第 8 节业务规则）。
- `CLAUDE.md` 不维护规则本体，只指向本文件，不需要跟着重复修改业务规则细节。
- 修改任意一份规则文件时，必须同步修改另一份，禁止两份出现矛盾或其中一份过期。

---

## 8. 小红书内容工作流业务规则

1. 本项目支持内容审核后自动发布；发布必须通过 `/Users/lilin/.claude/skills/xiaohongshu-skills/scripts/cli.py`，不做自动登录、Cookie 采集、验证码绕过、批量无人值守发布。
2. 所有生成内容必须经过合规检查。
3. 涉及医疗、金融、法律、母婴、功效类内容，要自动提示风险。金融内容（银行、证券、基金、新股/打新等）额外禁止：在无资质情况下提供个股分析、收益承诺或冒充专业人士；推广非法集资、传销活动；发布违规借贷/高利贷信息或讲解具体加杠杆操作参数。该红线适用于笔记、评论、用户资料等所有发布场景，详细检查项见 `docs/compliance_rules.md` 第 11 条。
4. 输出内容要真实、具体、像真人经验分享，避免营销号语气。
5. 每篇笔记必须包含：
   - 标题候选
   - 正文
   - 封面文案
   - 配图建议
   - 图片生成提示词
   - 标签
   - 合规审查
   - 发布建议
6. 代码优先使用 Python 标准库；环境变量从 `.env` 读取。
7. **产物归档规则**：每次生成一篇小红书图文内容后，必须在项目根目录的 `archive/` 文件夹（`/Users/lilin/code/lin/workflow/archive/`）下创建一个「日期+标题」命名的子文件夹，格式为 `YYYY-MM-DD_标题`（标题需去除 `？`"`"等文件系统不安全字符），并将本次生成的全部产物集中存放于该子文件夹内，不得散落在 `drafts/`、`/Users/lilin/code/lin/resource/` 等临时目录，也不得直接放在项目根目录下：
   - `content.json`：本次生成的完整结构化内容（标题候选、正文、标签、image_prompts、合规审查等）
   - `title.txt` / `content.txt`：实际用于发布的标题和正文文件
   - `image_prompts_batch.json`：本次图片生成使用的提示词批次文件
   - `images/`：最终发布顺序的图片，按发布顺序编号命名（如 `01_cover.png`、`02_reason1.png` …）

   发布完成后应立即清理 `/Users/lilin/code/lin/resource/`、`drafts/` 中对应的临时/散落文件，确保同一批产物只保留在该归档文件夹中一份。
8. **错误自我修复规则**：每次流程执行过程中出现报错、失败或产出不符合规则的情况，必须按以下步骤处理，不得跳过：
   - **定位原因**：排查并明确导致错误的根本原因（如脚本参数错误、依赖缺失、路径不对、合规审查遗漏、发布接口调用方式错误等），禁止只做"绕过式"修复。
   - **修复问题**：先修复本次任务中的实际问题，确保当前流程能够正常跑通。
   - **验证**：修复后重新执行一次相关步骤（或等效的最小验证），确认问题已解决，再继续后续流程。
9. **联网调研规则**：通过 API 生成笔记（`generate_note.py` / `generate_publish_packages`）前，必须先用 Claude web search 产出 `research_brief`（事实锚点 + 外部观点），并写入发布包 / 归档的 `content.json`；内容图规划须吸收 brief，禁止空洞框架金句。无 API 草稿路径可选手写 `research_brief`，缺失时在合规中标注「未联网核验」。仅当显式设置 `XHS_SKIP_RESEARCH=1` 时可跳过检索。

## 示例归档结构

```
workflow/
└── archive/
    └── 2026-07-06_AI全线跌5个真相看懂/
        ├── content.json
        ├── title.txt
        ├── content.txt
        ├── image_prompts_batch.json
        └── images/
            ├── 01_cover.png
            ├── 02_reason1.png
            ├── 03_reason2.png
            ├── 04_reason3.png
            ├── 05_reason4-5.png
            └── 06_summary.png
```
