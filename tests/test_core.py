import csv
import json
import tempfile
import unittest
from pathlib import Path

from xhs_workflow.automation import ReviewRejected, auto_publish_package
from xhs_workflow.claude_client import extract_json_object
from xhs_workflow.draft_package import DraftValidationError, create_package_from_draft
from xhs_workflow.generate import build_generation_prompt, finalize_generation_result
from xhs_workflow.image_prompt_profiles import (
    build_image_prompts,
    resolve_image_profile_name,
)
from xhs_workflow.images import build_gemini_command, write_gemini_prompts
from xhs_workflow.metrics import calculate_rates, summarize_metrics
from xhs_workflow.packages import (
    PublishPackage,
    extract_package_fields,
    write_publish_package,
)
from xhs_workflow.publish import (
    build_publish_command,
    prepare_publish_files,
    update_publish_status,
)
from xhs_workflow.prompts import render_prompt
from xhs_workflow.topics import load_topics


class PromptTests(unittest.TestCase):
    def test_checked_in_generate_template_includes_visual_planner_rules(self):
        template_path = Path(__file__).resolve().parents[1] / "prompts" / "generate_note.md"
        template = template_path.read_text(encoding="utf-8")

        self.assertIn("你是一位专业的小红书视觉内容策划师", template)
        self.assertIn("封面图（第1张）", template)
        self.assertIn("右下角水印：“小美科普”", template)

    def test_render_prompt_replaces_named_placeholders_without_touching_json_braces(self):
        template = """账号：{brand_guide}
输出 JSON:
{
  "titles": ["标题1"],
  "topic": "{topic}"
}
"""

        rendered = render_prompt(
            template,
            {
                "brand_guide": "真实、具体",
                "topic": "新手如何选择第一台咖啡机",
            },
        )

        self.assertIn("账号：真实、具体", rendered)
        self.assertIn('"titles": ["标题1"]', rendered)
        self.assertIn('"topic": "新手如何选择第一台咖啡机"', rendered)

    def test_build_generation_prompt_combines_docs_and_topic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "prompts").mkdir()
            (root / "docs" / "brand_guide.md").write_text("账号定位", encoding="utf-8")
            (root / "docs" / "content_pillars.md").write_text("内容栏目", encoding="utf-8")
            (root / "docs" / "compliance_rules.md").write_text("合规规则", encoding="utf-8")
            (root / "prompts" / "generate_note.md").write_text(
                "品牌：{brand_guide}\n栏目：{content_pillars}\n规则：{compliance_rules}\n选题：{topic}",
                encoding="utf-8",
            )

            prompt = build_generation_prompt(
                root,
                {
                    "topic": "咖啡机选择",
                    "category": "家居生活",
                    "audience": "租房女生",
                    "angle": "避坑",
                },
            )

        self.assertIn("品牌：账号定位", prompt)
        self.assertIn("栏目：内容栏目", prompt)
        self.assertIn("规则：合规规则", prompt)
        self.assertIn("选题：咖啡机选择", prompt)

    def test_build_generation_prompt_requests_profile_instead_of_final_image_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "prompts").mkdir()
            (root / "docs" / "brand_guide.md").write_text("账号定位", encoding="utf-8")
            (root / "docs" / "content_pillars.md").write_text("内容栏目", encoding="utf-8")
            (root / "docs" / "compliance_rules.md").write_text("合规规则", encoding="utf-8")
            (root / "prompts" / "generate_note.md").write_text(
                '字段：image_profile image_suggestions image_prompts\n选题：{topic}',
                encoding="utf-8",
            )

            prompt = build_generation_prompt(
                root,
                {
                    "topic": "咖啡机选择",
                    "category": "家居生活",
                    "audience": "租房女生",
                    "angle": "避坑",
                },
            )

        self.assertIn("image_profile", prompt)
        self.assertIn("image_suggestions", prompt)
        self.assertIn("image_prompts", prompt)

    def test_extract_json_object_accepts_markdown_wrapped_json(self):
        payload = """这里是结果：
```json
{
  "recommended_title": "第一台咖啡机别乱买",
  "hashtags": ["咖啡机"]
}
```
"""

        result = extract_json_object(payload)

        self.assertEqual(result["recommended_title"], "第一台咖啡机别乱买")
        self.assertEqual(result["hashtags"], ["咖啡机"])


class TopicTests(unittest.TestCase):
    def test_load_topics_returns_only_draft_rows_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "topics.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=["id", "topic", "category", "audience", "angle", "status"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "id": "001",
                        "topic": "咖啡机选择",
                        "category": "家居生活",
                        "audience": "租房女生",
                        "angle": "避坑",
                        "status": "draft",
                    }
                )
                writer.writerow(
                    {
                        "id": "002",
                        "topic": "通勤包清单",
                        "category": "职场穿搭",
                        "audience": "上班族女生",
                        "angle": "清单",
                        "status": "reviewed",
                    }
                )

            topics = load_topics(path)

        self.assertEqual([topic.id for topic in topics], ["001"])


class PackageTests(unittest.TestCase):
    def test_write_publish_package_creates_human_review_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            package = PublishPackage(
                topic_id="001",
                topic="新手如何选择第一台咖啡机",
                category="家居生活",
                audience="租房女生",
                angle="避坑",
                titles=["第一台咖啡机别乱买", "买咖啡机前先看这5点"],
                recommended_title="第一台咖啡机别乱买",
                cover_texts=["第一台咖啡机\n别急着买贵的"],
                body="之前我也以为预算越高越好。\n后来发现使用频率更重要。",
                hashtags=["咖啡机", "租房生活", "新手咖啡"],
                image_suggestions=["封面：咖啡机+大字标题", "图2：类型对比"],
                image_profile="decision_checklist",
                image_prompts=["竖版封面，咖啡机和大字标题", "咖啡机类型对比信息图"],
                image_paths=[],
                publish_time_suggestion="工作日 20:00-22:00",
                compliance_check={
                    "risk_level": "low",
                    "risks": [],
                    "rewrite_suggestions": [],
                },
                raw={"recommended_title": "第一台咖啡机别乱买"},
            )

            markdown_path = write_publish_package(package, output_dir)
            json_path = markdown_path.with_suffix(".json")

            markdown = markdown_path.read_text(encoding="utf-8")
            data = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertEqual(markdown_path.name, "001_新手如何选择第一台咖啡机.md")
        self.assertIn("## 推荐标题\n第一台咖啡机别乱买", markdown)
        self.assertIn("## 人工审核区", markdown)
        self.assertIn("- 审核状态：draft", markdown)
        self.assertEqual(data["recommended_title"], "第一台咖啡机别乱买")
        self.assertEqual(data["publish_status"], "draft")
        self.assertEqual(data["image_prompts"], ["竖版封面，咖啡机和大字标题", "咖啡机类型对比信息图"])

    def test_extract_package_fields_returns_copy_ready_content(self):
        markdown = """# 发布包：咖啡机选择

## 推荐标题
第一台咖啡机别乱买

## 正文
之前我也以为预算越高越好。

## 话题
#咖啡机 #租房生活

## 人工审核区
- 审核状态：reviewed
"""

        fields = extract_package_fields(markdown)

        self.assertEqual(fields["title"], "第一台咖啡机别乱买")
        self.assertEqual(fields["body"], "之前我也以为预算越高越好。")
        self.assertEqual(fields["hashtags"], "#咖啡机 #租房生活")


class DraftPackageTests(unittest.TestCase):
    def test_build_image_prompts_renders_all_requested_slides_with_closing_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "fallback_profile": "planner_profile",
                        "global_quality_rules": {
                            "base_requirements": ["小红书风格信息图", "竖版（3:4）"],
                            "negative_constraints": ["右下角水印：“小美科普”"],
                        },
                        "profiles": [
                            {
                                "name": "planner_profile",
                                "match": {},
                                "cover_template": "封面图：{image_suggestion}",
                                "content_templates": [
                                    "内容图：{image_suggestion}"
                                ],
                                "closing_template": "结尾图：{image_suggestion}",
                                "default_image_suggestions": ["默认封面", "默认内容", "默认结尾"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            prompts = build_image_prompts(
                config_path=config_path,
                topic="复杂主题",
                category="未知分类",
                audience="陌生用户",
                angle="深度分析",
                recommended_title="复杂标题",
                cover_texts=["复杂封面"],
                body="正文",
                image_suggestions=["封面钩子", "观点一", "观点二", "观点三", "结尾行动号召"],
            )

        self.assertEqual(len(prompts), 5)
        self.assertIn("封面图：封面钩子", prompts[0])
        self.assertIn("内容图：观点一", prompts[1])
        self.assertIn("内容图：观点三", prompts[3])
        self.assertIn("结尾图：结尾行动号召", prompts[4])

    def test_default_image_prompts_include_cartoon_handdrawn_watermark_constraints(self):
        prompts = build_image_prompts(
            topic="全球市值前五十的公司",
            category="投资",
            audience="理财新手",
            angle="社会趋势",
            recommended_title="市值前50藏着趋势",
            cover_texts=["全球市值前50\n藏着哪些趋势？"],
            body="正文",
            image_suggestions=[
                "封面图：全球市值前50与趋势感",
                "信息图：五大板块拆解",
                "清单图：普通人最该看的三个问题",
                "结尾图：不是荐股而是看趋势",
            ],
        )

        self.assertIn("卡通风格", prompts[0])
        self.assertIn("手绘风格文字", prompts[0])
        self.assertIn("右下角水印：“小美科普”", prompts[-1])

    def test_build_image_prompts_selects_profile_by_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "fallback_profile": "fallback_profile",
                        "global_quality_rules": {
                            "base_requirements": ["小红书竖版 3:4", "中文清晰", "留白充足"],
                            "negative_constraints": ["不要英文乱码"],
                        },
                        "profiles": [
                            {
                                "name": "business_infographic",
                                "match": {"categories": ["投资"]},
                                "cover_template": "封面图：{recommended_title}",
                                "content_templates": ["内容图：{image_suggestion}"],
                                "closing_template": "结尾图：{image_suggestion}",
                                "default_image_suggestions": ["行业分布"],
                            },
                            {
                                "name": "fallback_profile",
                                "match": {},
                                "cover_template": "默认封面：{recommended_title}",
                                "content_templates": ["默认内容图：{image_suggestion}"],
                                "closing_template": "默认结尾图：{image_suggestion}",
                                "default_image_suggestions": ["默认建议"],
                            },
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            profile_name = resolve_image_profile_name(
                config_path,
                category="投资",
                audience="理财新手",
                angle="趋势",
            )
            prompts = build_image_prompts(
                config_path=config_path,
                topic="全球市值前五十的公司",
                category="投资",
                audience="理财新手",
                angle="趋势",
                recommended_title="市值前50藏着趋势",
                cover_texts=["全球市值前50\n藏着哪些趋势？"],
                body="正文",
                image_suggestions=["封面钩子", "五大板块拆解"],
            )

        self.assertEqual(profile_name, "business_infographic")
        self.assertEqual(len(prompts), 2)
        self.assertIn("封面图：市值前50藏着趋势", prompts[0])
        self.assertIn("小红书竖版 3:4", prompts[0])
        self.assertIn("不要英文乱码", prompts[1])

    def test_build_image_prompts_uses_fallback_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "fallback_profile": "fallback_profile",
                        "global_quality_rules": {
                            "base_requirements": ["小红书竖版 3:4"],
                            "negative_constraints": [],
                        },
                        "profiles": [
                            {
                                "name": "fallback_profile",
                                "match": {},
                                "cover_template": "默认封面：{recommended_title}",
                                "content_templates": ["默认内容图：{image_suggestion}"],
                                "closing_template": "默认结尾图：{image_suggestion}",
                                "default_image_suggestions": ["默认封面建议", "默认结尾建议"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            prompts = build_image_prompts(
                config_path=config_path,
                topic="陌生主题",
                category="未知分类",
                audience="陌生用户",
                angle="陌生角度",
                recommended_title="陌生标题",
                cover_texts=[],
                body="正文",
                image_suggestions=[],
            )

        self.assertEqual(prompts[0], "默认封面：陌生标题，小红书竖版 3:4")
        self.assertEqual(prompts[1], "默认结尾图：默认结尾建议，小红书竖版 3:4")

    def test_create_package_from_draft_writes_standard_package_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path = root / "draft.json"
            output_dir = root / "output"
            draft_path.write_text(
                json.dumps(
                    {
                        "topic_id": "manual-001",
                        "topic": "新手如何选择第一台咖啡机",
                        "category": "家居生活",
                        "audience": "租房女生",
                        "angle": "避坑",
                        "titles": ["第一台咖啡机别乱买"],
                        "recommended_title": "第一台咖啡机别乱买",
                        "cover_texts": ["第一台咖啡机\n别急着买贵的"],
                        "body": "正文第一段\n\n正文第二段",
                        "hashtags": ["咖啡机", "租房生活"],
                        "image_prompts": ["封面图提示词", "内容图提示词"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            markdown_path = create_package_from_draft(draft_path, output_dir)
            data = json.loads(markdown_path.with_suffix(".json").read_text(encoding="utf-8"))

        self.assertEqual(markdown_path.name, "manual-001_新手如何选择第一台咖啡机.md")
        self.assertEqual(data["recommended_title"], "第一台咖啡机别乱买")
        self.assertEqual(data["image_prompts"], ["封面图提示词", "内容图提示词"])
        self.assertEqual(data["publish_status"], "draft")

    def test_create_package_from_draft_generates_image_prompts_from_profile_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path = root / "draft.json"
            config_path = root / "profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "fallback_profile": "decision_checklist",
                        "global_quality_rules": {
                            "base_requirements": ["小红书竖版 3:4", "中文清晰"],
                            "negative_constraints": ["不要平台水印"],
                        },
                        "profiles": [
                            {
                                "name": "decision_checklist",
                                "match": {"angles": ["避坑"]},
                                "cover_template": "封面图：{recommended_title}",
                                "content_templates": [
                                    "内容图1：{image_suggestion}",
                                    "内容图2：{image_suggestion}",
                                ],
                                "closing_template": "结尾图：{image_suggestion}",
                                "default_image_suggestions": ["封面钩子", "选择维度", "避坑提醒"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            draft_path.write_text(
                json.dumps(
                    {
                        "topic_id": "manual-002",
                        "topic": "新手如何选择第一台咖啡机",
                        "category": "家居生活",
                        "audience": "租房女生",
                        "angle": "避坑",
                        "recommended_title": "第一台咖啡机别乱买",
                        "body": "正文",
                        "hashtags": ["咖啡机"],
                        "image_suggestions": ["封面钩子", "类型对比", "购买建议"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            markdown_path = create_package_from_draft(
                draft_path,
                root / "output",
                config_path=config_path,
            )
            data = json.loads(markdown_path.with_suffix(".json").read_text(encoding="utf-8"))

        self.assertEqual(data["image_profile"], "decision_checklist")
        self.assertEqual(len(data["image_prompts"]), 3)
        self.assertIn("封面图：第一台咖啡机别乱买", data["image_prompts"][0])
        self.assertIn("不要平台水印", data["image_prompts"][1])

    def test_create_package_from_draft_preserves_existing_image_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft_path = root / "draft.json"
            config_path = root / "profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "fallback_profile": "decision_checklist",
                        "global_quality_rules": {
                            "base_requirements": ["小红书竖版 3:4"],
                            "negative_constraints": [],
                        },
                        "profiles": [
                            {
                                "name": "decision_checklist",
                                "match": {},
                                "cover_template": "封面图：{recommended_title}",
                                "content_templates": ["内容图：{image_suggestion}"],
                                "default_image_suggestions": ["默认建议"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            draft_path.write_text(
                json.dumps(
                    {
                        "recommended_title": "标题",
                        "body": "正文",
                        "hashtags": ["标签"],
                        "image_prompts": ["手写封面", "手写内容"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            markdown_path = create_package_from_draft(
                draft_path,
                root / "output",
                config_path=config_path,
            )
            data = json.loads(markdown_path.with_suffix(".json").read_text(encoding="utf-8"))

        self.assertEqual(data["image_prompts"], ["手写封面", "手写内容"])
        self.assertEqual(data.get("image_profile", ""), "")

    def test_create_package_from_draft_requires_image_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft_path = Path(tmp) / "draft.json"
            draft_path.write_text(
                json.dumps(
                    {
                        "recommended_title": "标题",
                        "body": "正文",
                        "hashtags": ["标签"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(DraftValidationError):
                create_package_from_draft(draft_path, Path(tmp) / "output")


class GenerationResultTests(unittest.TestCase):
    def test_finalize_generation_result_builds_image_prompts_from_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "image_prompt_profiles.json").write_text(
                json.dumps(
                    {
                        "fallback_profile": "business_infographic",
                        "global_quality_rules": {
                            "base_requirements": ["小红书竖版 3:4"],
                            "negative_constraints": ["不要英文乱码"],
                        },
                        "profiles": [
                            {
                                "name": "business_infographic",
                                "match": {"categories": ["投资"]},
                                "cover_template": "封面图：{recommended_title}",
                                "content_templates": ["内容图：{image_suggestion}"],
                                "closing_template": "结尾图：{image_suggestion}",
                                "default_image_suggestions": ["默认建议"],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = finalize_generation_result(
                root,
                {
                    "id": "001",
                    "topic": "全球市值前五十的公司",
                    "category": "投资",
                    "audience": "理财用户",
                    "angle": "趋势",
                },
                {
                    "recommended_title": "市值前50藏着趋势",
                    "cover_texts": ["全球市值前50\n藏着哪些趋势？"],
                    "body": "正文",
                    "hashtags": ["投资学习"],
                    "image_profile": "business_infographic",
                    "image_suggestions": ["封面钩子", "五大板块拆解", "总结收尾"],
                },
            )

        self.assertEqual(result["image_profile"], "business_infographic")
        self.assertEqual(len(result["image_prompts"]), 3)
        self.assertIn("封面图：市值前50藏着趋势", result["image_prompts"][0])

    def test_finalize_generation_result_preserves_existing_image_prompts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            result = finalize_generation_result(
                root,
                {
                    "id": "001",
                    "topic": "全球市值前五十的公司",
                    "category": "投资",
                    "audience": "理财用户",
                    "angle": "趋势",
                },
                {
                    "recommended_title": "市值前50藏着趋势",
                    "cover_texts": ["全球市值前50\n藏着哪些趋势？"],
                    "body": "正文",
                    "hashtags": ["投资学习"],
                    "image_prompts": ["手写封面", "手写内容"],
                    "image_suggestions": ["五大板块拆解"],
                },
            )

        self.assertEqual(result["image_prompts"], ["手写封面", "手写内容"])


class ImageAutomationTests(unittest.TestCase):
    def test_write_gemini_prompts_uses_existing_script_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "prompts.json"
            output_path = write_gemini_prompts(
                ["封面图提示词", "内容图提示词"],
                path,
            )
            data = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            data,
            [
                {"index": 1, "type": "封面图", "prompt": "封面图提示词"},
                {"index": 2, "type": "内容图", "prompt": "内容图提示词"},
            ],
        )

    def test_build_gemini_command_uses_absolute_prompt_path(self):
        command = build_gemini_command(
            Path("/tmp/prompts.json"),
            script_path=Path("/opt/gemini_automation.py"),
        )

        self.assertEqual(
            command,
            ["python3", "/opt/gemini_automation.py", "--prompts", "/tmp/prompts.json"],
        )


class PublishAutomationTests(unittest.TestCase):
    def test_prepare_publish_files_writes_title_and_content_with_hashtags(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = {
                "recommended_title": "第一台咖啡机别乱买",
                "body": "正文第一段\n\n正文第二段",
                "hashtags": ["咖啡机", "租房生活"],
            }

            title_file, content_file = prepare_publish_files(package, Path(tmp))

            title = title_file.read_text(encoding="utf-8")
            content = content_file.read_text(encoding="utf-8")

        self.assertEqual(title, "第一台咖啡机别乱买")
        self.assertEqual(content, "正文第一段\n\n正文第二段\n\n#咖啡机 #租房生活")

    def test_build_publish_command_uses_xhs_cli_publish(self):
        command = build_publish_command(
            Path("/tmp/title.txt"),
            Path("/tmp/content.txt"),
            [Path("/tmp/image_1.jpg"), Path("/tmp/image_2.jpg")],
            cli_path=Path("/opt/xhs/cli.py"),
        )

        self.assertEqual(
            command,
            [
                "python3",
                "/opt/xhs/cli.py",
                "publish",
                "--title-file",
                "/tmp/title.txt",
                "--content-file",
                "/tmp/content.txt",
                "--images",
                "/tmp/image_1.jpg",
                "/tmp/image_2.jpg",
            ],
        )

    def test_update_publish_status_records_success_without_losing_package_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            package_path.write_text(
                json.dumps(
                    {
                        "recommended_title": "第一台咖啡机别乱买",
                        "publish_status": "draft",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            update_publish_status(
                package_path,
                status="published",
                note_url="https://www.xiaohongshu.com/explore/abc",
            )
            data = json.loads(package_path.read_text(encoding="utf-8"))

        self.assertEqual(data["recommended_title"], "第一台咖啡机别乱买")
        self.assertEqual(data["publish_status"], "published")
        self.assertEqual(data["note_url"], "https://www.xiaohongshu.com/explore/abc")


class AutoPublishFlowTests(unittest.TestCase):
    def test_auto_publish_package_stops_when_review_is_not_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            package_path.write_text(
                json.dumps(
                    {
                        "recommended_title": "第一台咖啡机别乱买",
                        "body": "正文",
                        "hashtags": ["咖啡机"],
                        "image_prompts": ["图片提示词"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            calls: list[str] = []

            with self.assertRaises(ReviewRejected):
                auto_publish_package(
                    package_path,
                    approved=False,
                    image_generator=lambda prompts: calls.append("images") or [],
                    publisher=lambda path, images: calls.append("publish") or {},
                )

        self.assertEqual(calls, [])

    def test_auto_publish_package_generates_images_then_publishes_when_approved(self):
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            package_path.write_text(
                json.dumps(
                    {
                        "recommended_title": "第一台咖啡机别乱买",
                        "body": "正文",
                        "hashtags": ["咖啡机"],
                        "image_prompts": ["图片提示词"],
                        "publish_status": "draft",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = auto_publish_package(
                package_path,
                approved=True,
                image_generator=lambda prompts: [Path("/tmp/image_1.jpg")],
                publisher=lambda path, images: {"success": True, "images": [str(image) for image in images]},
            )
            data = json.loads(package_path.read_text(encoding="utf-8"))

        self.assertEqual(result["success"], True)
        self.assertEqual(data["image_paths"], ["/tmp/image_1.jpg"])


class MetricsTests(unittest.TestCase):
    def test_calculate_rates_handles_zero_views(self):
        rates = calculate_rates(
            {
                "views": "0",
                "likes": "10",
                "saves": "5",
                "comments": "2",
                "shares": "1",
                "follows": "1",
            }
        )

        self.assertEqual(rates["like_rate"], 0.0)
        self.assertEqual(rates["engagement_rate"], 0.0)

    def test_summarize_metrics_groups_rows_by_post_id(self):
        summary = summarize_metrics(
            [
                {
                    "post_id": "001",
                    "date": "2026-06-27",
                    "views": "100",
                    "likes": "10",
                    "saves": "5",
                    "comments": "2",
                    "shares": "1",
                    "follows": "1",
                },
                {
                    "post_id": "001",
                    "date": "2026-06-29",
                    "views": "200",
                    "likes": "30",
                    "saves": "20",
                    "comments": "6",
                    "shares": "4",
                    "follows": "3",
                },
            ]
        )

        self.assertEqual(summary["001"]["latest"]["views"], 200)
        self.assertEqual(summary["001"]["totals"]["views"], 300)
        self.assertAlmostEqual(summary["001"]["latest_rates"]["engagement_rate"], 0.3)


if __name__ == "__main__":
    unittest.main()
