"""Format curated items into WeCom-compatible Markdown."""

from datetime import datetime


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def format_report(curated, report_date=None):
    """Format curated items into a Markdown daily report string."""
    if report_date is None:
        report_date = datetime.now()

    date_str = report_date.strftime("%Y-%m-%d")
    weekday = WEEKDAYS[report_date.weekday()]

    lines = [
        f"🤖 AI 日报 | {date_str} {weekday}",
        "━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # News section
    news_items = curated.get("news", [])
    lines.append(f"📰 AI 行业动态（{len(news_items)}条）")
    lines.append("")
    if news_items:
        for i, item in enumerate(news_items, 1):
            lines.append(f"{number_emoji(i)} **{item['title']}**")
            lines.append(f"   📝 {item['summary']}")
            lines.append(f"   🔗 来源：{item['source']} | [阅读原文]({item['url']})")
            lines.append("")
    else:
        lines.append("   今日暂无重要AI新闻")
        lines.append("")

    # GitHub section
    lines.append("━━━━━━━━━━━━━━━━━━")
    lines.append("")
    github_items = curated.get("github_projects", [])
    lines.append(f"🔥 GitHub 热门 AI 项目（{len(github_items)}条）")
    lines.append("")
    if github_items:
        for i, item in enumerate(github_items, 1):
            stars = item.get("stars", 0)
            title = item.get("title", "")
            if stars:
                lines.append(f"{number_emoji(i)} **{title}** ⭐{stars:,}")
            else:
                lines.append(f"{number_emoji(i)} **{title}**")
            lines.append(f"   📝 {item['summary']}")
            lines.append(f"   🔗 [GitHub]({item['url']})")
            lines.append("")
    else:
        lines.append("   今日暂无热门AI项目")
        lines.append("")

    return "\n".join(lines)


def number_emoji(n):
    """Convert number to emoji number (1-10)."""
    emojis = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    if n <= 10:
        return emojis[n]
    return f"{n}."


def split_message(text, max_chars=4096):
    """Split a long message into parts, trying to break at section boundaries."""
    if len(text) <= max_chars:
        return [text]

    parts = []
    paragraphs = text.split("\n\n")
    current = ""

    cont_prefix = "（续）\n"
    cont_prefix_len = len(cont_prefix)

    for para in paragraphs:
        if current:
            candidate = current + "\n\n" + para
            if len(candidate) <= max_chars:
                current = candidate
                continue
            parts.append(current)

        # Start a new part with this paragraph
        if len(para) <= max_chars:
            current = para
        else:
            # Split long paragraph: first chunk at max_chars
            parts.append(para[:max_chars])
            remaining = para[max_chars:]
            while remaining:
                chunk_size = max_chars - cont_prefix_len
                chunk = remaining[:chunk_size]
                remaining = remaining[chunk_size:]
                if chunk:
                    parts.append(cont_prefix + chunk)
            current = ""

    if current:
        parts.append(current)

    # Add part indicators if multiple parts
    if len(parts) > 1:
        for i in range(len(parts)):
            indicator = f"（Part {i+1}/{len(parts)}）\n\n"
            available = max_chars - len(indicator)
            if available >= len(parts[i]):
                parts[i] = indicator + parts[i]
            elif available > 0:
                parts[i] = indicator + parts[i][:available]
            else:
                parts[i] = indicator

    return parts
