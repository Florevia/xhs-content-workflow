from __future__ import annotations

import argparse
from pathlib import Path

from xhs_workflow.draft_package import DraftValidationError, create_package_from_draft


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a publish package from a local JSON draft without LLM API.")
    parser.add_argument("draft", type=Path, help="Local JSON draft path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/publish_packages"),
        help="Directory for generated publish package files.",
    )
    args = parser.parse_args()

    try:
        markdown_path = create_package_from_draft(args.draft, args.output_dir)
    except DraftValidationError as error:
        raise SystemExit(f"草稿格式错误：{error}") from error

    print(f"已生成发布包：{markdown_path}")
    print(f"自动发布命令：PYTHONPATH=src python3 src/auto_publish.py --package {markdown_path.with_suffix('.json')}")


if __name__ == "__main__":
    main()
