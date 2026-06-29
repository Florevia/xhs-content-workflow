from __future__ import annotations

import argparse
from pathlib import Path

from xhs_workflow.export import copy_to_clipboard, load_copy_fields, open_creator_platform


COPY_ORDER = (("title", "标题"), ("body", "正文"), ("hashtags", "话题"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy package fields for manual publishing.")
    parser.add_argument("package", type=Path, help="Markdown package path.")
    parser.add_argument("--open-creator", action="store_true", help="Open creator.xiaohongshu.com.")
    args = parser.parse_args()

    fields = load_copy_fields(args.package)
    if args.open_creator:
        open_creator_platform()

    for key, label in COPY_ORDER:
        input(f"按 Enter 复制{label}...")
        value = fields.get(key, "")
        if copy_to_clipboard(value):
            print(f"已复制{label}到剪贴板。")
        else:
            print(f"无法自动复制{label}，内容如下：\n{value}")

    print("请在小红书官方创作服务平台手动上传图片、预览并发布或预约。")


if __name__ == "__main__":
    main()
