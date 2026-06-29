from __future__ import annotations

import argparse
import json
from pathlib import Path

from xhs_workflow.automation import ReviewRejected, auto_publish_package
from xhs_workflow.claude_client import load_env_file
from xhs_workflow.generate import generate_publish_packages


CONFIRM_TEXT = "publish"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate, review, image-generate, and publish Xiaohongshu notes.")
    parser.add_argument("--package", type=Path, help="Existing machine-readable package JSON path.")
    parser.add_argument("--status", default="draft", help="Topic status to generate when --package is omitted.")
    parser.add_argument("--yes", action="store_true", help="Skip review prompt and publish automatically.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    load_env_file(root / ".env")
    package_paths = [args.package] if args.package else _generate_package_json_paths(root, args.status)
    if not package_paths:
        print("没有找到需要自动发布的选题或发布包。")
        return

    for package_path in package_paths:
        approved = args.yes or confirm_package(package_path)
        try:
            result = auto_publish_package(package_path, approved=approved)
        except ReviewRejected:
            print(f"已跳过发布：{package_path}")
            continue
        print(f"发布完成：{json.dumps(result, ensure_ascii=False)}")


def confirm_package(package_path: Path) -> bool:
    package = json.loads(package_path.read_text(encoding="utf-8"))
    hashtags = " ".join(f"#{tag.lstrip('#')}" for tag in package.get("hashtags", []))
    risk_level = package.get("compliance_check", {}).get("risk_level", "unknown")

    print("\n即将发布：")
    print(f"标题：{package.get('recommended_title', '')}")
    print(f"正文：\n{package.get('body', '')}")
    print(f"话题：{hashtags}")
    print(f"合规风险：{risk_level}")
    print(f"图片提示词数量：{len(package.get('image_prompts', []))}")
    answer = input(f"审核通过请输入 {CONFIRM_TEXT}，其他任意输入跳过：").strip()
    return answer == CONFIRM_TEXT


def _generate_package_json_paths(root: Path, status: str) -> list[Path]:
    markdown_paths = generate_publish_packages(root, status=status)
    return [path.with_suffix(".json") for path in markdown_paths]


if __name__ == "__main__":
    main()
