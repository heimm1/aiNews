"""LLM processing: filter, summarize, translate raw items into curated daily digest."""

import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一位资深的AI日报主编。你的任务是：

1. 从提供的原始AI资讯和GitHub项目中，筛选出最有价值的 10-18 条内容
2. 英文内容翻译成中文，保留技术术语的准确性
3. 每条新闻写2-4句深度摘要（不是简单复述标题，而是解释它的意义和影响）
4. GitHub项目用一句话说清楚它解决什么问题、为什么值得关注
5. 按重要性排序（最重要的排前面）

输出必须是严格的JSON格式，不要包含任何其他文字：

{
  "news": [
    {
      "title": "中文标题（英文翻译过来）",
      "summary": "2-4句深度解读",
      "url": "原文链接",
      "source": "来源名称"
    }
  ],
  "github_projects": [
    {
      "title": "owner/repo名",
      "summary": "一句话描述",
      "url": "GitHub链接",
      "stars": 12345
    }
  ]
}

注意事项：
- 去重：同样的新闻不同来源只保留最有价值的那一条
- 不要选纯推广、纯广告内容
- 优先选对AI从业者有实际价值的内容：新模型发布、重要论文、工具框架更新、行业趋势分析
- GitHub项目优先选近期热门、实用性强的"""


def build_prompt(raw_items):
    """Build the user prompt with raw collected items."""
    lines = ["以下是今天采集到的原始AI资讯和GitHub项目：\n"]
    for i, item in enumerate(raw_items, 1):
        item_type = "新闻" if item["item_type"] == "news" else "GitHub项目"
        stars_info = f" (⭐{item.get('stars', 0)})" if item.get("stars") else ""
        lines.append(
            f"[{i}] [{item_type}] {item['title']}{stars_info}\n"
            f"    摘要: {item['summary'][:300]}\n"
            f"    链接: {item['url']}\n"
            f"    来源: {item['source']}\n"
        )

    lines.append("\n请筛选最有价值的 10-18 条内容，输出为JSON格式。")
    return "\n".join(lines)


def parse_llm_response(text):
    """Parse Claude's JSON response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)

    try:
        data = json.loads(text)
        return {
            "news": data.get("news", []),
            "github_projects": data.get("github_projects", []),
        }
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM JSON response")
        return {"news": [], "github_projects": []}


def process_items(raw_items, model="claude-sonnet-4-6"):
    """Send raw items to Claude for curation. Returns structured dict with news + github_projects."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        return _fallback_items(raw_items)

    user_prompt = build_prompt(raw_items)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = ""
        for block in response.content:
            if block.type == "text":
                text += block.text

        return parse_llm_response(text)

    except Exception as e:
        logger.error(f"LLM processing failed: {e}")
        return _fallback_items(raw_items)


def _fallback_items(raw_items):
    """When LLM fails, return raw items as-is."""
    news_items = [it for it in raw_items if it["item_type"] == "news"]
    github_items = [it for it in raw_items if it["item_type"] == "github"]
    return {
        "news": [{"title": it["title"], "summary": it["summary"], "url": it["url"], "source": it["source"]}
                 for it in news_items[:10]],
        "github_projects": [{"title": it["title"], "summary": it["summary"], "url": it["url"], "stars": it.get("stars", 0)}
                            for it in github_items[:8]],
    }
