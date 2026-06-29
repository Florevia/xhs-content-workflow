from __future__ import annotations

import argparse
from pathlib import Path

from xhs_workflow.generate import generate_publish_packages


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Xiaohongshu publish packages.")
    parser.add_argument("--status", default="draft", help="Topic status to generate.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    paths = generate_publish_packages(root, status=args.status)
    if not paths:
        print("没有找到需要生成的选题。")
        return

    for path in paths:
        print(f"已生成：{path}")


if __name__ == "__main__":
    main()
