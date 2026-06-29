from __future__ import annotations

import argparse
from pathlib import Path

from xhs_workflow.analysis import analyze_metrics_with_claude, write_metrics_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze manually recorded Xiaohongshu metrics.")
    parser.add_argument("--package", type=Path, help="Package path for Claude analysis.")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    summary_path = write_metrics_summary(root)
    print(f"已生成数据摘要：{summary_path}")

    if args.package:
        analysis_path = analyze_metrics_with_claude(root, args.package)
        print(f"已生成 Claude 复盘：{analysis_path}")


if __name__ == "__main__":
    main()
