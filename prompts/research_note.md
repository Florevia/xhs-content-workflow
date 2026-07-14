# 选题联网调研

你必须使用 web_search **必须联网搜索** 公开资料，再输出结构化 research_brief。
**禁止编造**未检索到的事实、数据、日期、官方口径或外部观点。

## 选题
- 选题：{topic}
- 分类：{category}
- 目标用户：{audience}
- 角度：{angle}
- 今日日期：{today}

## 检索要求
1. 优先覆盖：官方公告/监管口径、权威新闻、经济/产业论坛公开讨论、有代表性的分析观点（推特/社交媒体可作观点来源，需改写且不挂真实账号 ID）。
2. 目标至少收集 3 条 facts 与 2 条 viewpoints；不足时写入 gaps，不要凑假信息。
3. 每条事实/观点尽量带 source_name 与可公开访问的 source_url。
4. 金融相关内容在 risk_notes 中提示：不构成投资建议、避免个股推荐与收益承诺。

## 输出
只输出 JSON，字段如下：

{
  "query_summary": "本次检索意图一句话",
  "as_of": "YYYY-MM-DD",
  "facts": [
    {
      "claim": "可核对的事实锚点",
      "source_name": "来源名",
      "source_url": "https://...",
      "confidence": "high | medium | low"
    }
  ],
  "viewpoints": [
    {
      "summary": "外部代表性判断（改写，不挂真实账号）",
      "stance": "bullish | bearish | neutral | mixed",
      "source_name": "来源类型",
      "source_url": "https://...",
      "confidence": "high | medium | low"
    }
  ],
  "gaps": ["没搜到或不确定的点"],
  "risk_notes": ["合规提醒"]
}
