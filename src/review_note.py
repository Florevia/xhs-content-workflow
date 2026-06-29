from __future__ import annotations

import argparse
from pathlib import Path

from xhs_workflow.review import review_package


def main() -> None:
    parser = argparse.ArgumentParser(description="Review a generated Xiaohongshu package.")
    parser.add_argument("package", type=Path, help="Markdown package path.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output_path = review_package(root, args.package)
    print(f"已生成审核结果：{output_path}")


if __name__ == "__main__":
    main()
