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


def _byte_len(text):
    return len(text.encode("utf-8"))


def _byte_truncate(text, max_bytes):
    """Truncate text to fit within max_bytes at a valid UTF-8 character boundary."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    # Walk back past continuation bytes (10xxxxxx = 0x80-0xBF) to find
    # the last complete character start, avoiding garbled text.
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]
    return truncated.decode("utf-8")


def split_message(text, max_bytes=4096):
    """Split message by WeCom byte limit (4096 UTF-8 bytes), at paragraph boundaries."""
    if _byte_len(text) <= max_bytes:
        return [text]

    parts = []
    paragraphs = text.split("\n\n")

    cont_prefix = "（续）\n"
    cont_prefix_bytes = _byte_len(cont_prefix)

    current = ""
    for para in paragraphs:
        if current:
            combined = current + "\n\n" + para
            if _byte_len(combined) <= max_bytes:
                current = combined
                continue
            # Current paragraph would push us over — save current part and start new
            parts.append(current)
            current = ""

        if _byte_len(para) <= max_bytes:
            current = para
        else:
            # Single paragraph exceeds limit — split by bytes
            while _byte_len(para) > max_bytes:
                chunk = _byte_truncate(para, max_bytes)
                parts.append(chunk)
                para = para[len(chunk):]
                if para:
                    prefix_bytes = max_bytes - cont_prefix_bytes
                    prefix = _byte_truncate(para, prefix_bytes)
                    parts.append(cont_prefix + prefix)
                    para = para[len(prefix):]
                else:
                    break
            if para:
                current = para

    if current:
        parts.append(current)

    # Add part indicators if multiple parts
    if len(parts) > 1:
        for i in range(len(parts)):
            indicator = f"（Part {i+1}/{len(parts)}）\n\n"
            indicator_bytes = _byte_len(indicator)
            available = max_bytes - indicator_bytes
            if _byte_len(parts[i]) <= available:
                parts[i] = indicator + parts[i]
            elif available > 0:
                parts[i] = indicator + _byte_truncate(parts[i], available)
            else:
                parts[i] = indicator

    return parts
