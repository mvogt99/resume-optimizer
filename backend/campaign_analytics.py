"""Cross-campaign analytics — engagement analysis across all campaigns."""

import logging
import re
from collections import Counter

from models import get_db

logger = logging.getLogger(__name__)


def get_cross_campaign_analytics(user_id):
    """Compute aggregate analytics across all campaigns for a user."""
    with get_db() as conn:
        campaigns = conn.execute(
            "SELECT id, theme, audience, tone, status, created_at FROM campaigns WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        posts = conn.execute(
            "SELECT cp.campaign_id, cp.content, cp.status, cp.scheduled_date, cp.created_at "
            "FROM campaign_posts cp "
            "JOIN campaigns c ON cp.campaign_id = c.id "
            "WHERE c.user_id = ?",
            (user_id,),
        ).fetchall()

    total_campaigns = len(campaigns)
    total_posts = len(posts)

    # Posts by status
    posts_by_status = Counter(p["status"] for p in posts if p["status"])

    # Average posts per campaign
    avg_posts = total_posts / total_campaigns if total_campaigns else 0

    # Theme and tone distribution
    theme_dist = Counter(c["theme"] for c in campaigns if c["theme"])
    tone_dist = Counter(c["tone"] for c in campaigns if c["tone"])

    # Average character count
    char_counts = [len(p["content"] or "") for p in posts if p["content"]]
    avg_char_count = sum(char_counts) / len(char_counts) if char_counts else 0

    # Top hashtags across all posts
    hashtag_counter = Counter()
    for p in posts:
        content = p["content"] or ""
        hashtags = re.findall(r"#(\w+)", content)
        hashtag_counter.update(hashtags)
    top_hashtags = hashtag_counter.most_common(20)

    # Content calendar (posts grouped by scheduled_date)
    calendar = {}
    for p in posts:
        date = p["scheduled_date"] or "unscheduled"
        if date not in calendar:
            calendar[date] = 0
        calendar[date] += 1

    # Coverage by source — count client/project references in post content
    source_counter = Counter()
    for p in posts:
        content = (p["content"] or "").lower()
        # Simple heuristic: look for known campaign themes as source references
        for c in campaigns:
            if c["theme"] and c["theme"].lower() in content:
                source_counter[c["theme"]] += 1

    return {
        "total_campaigns": total_campaigns,
        "total_posts": total_posts,
        "posts_by_status": dict(posts_by_status),
        "avg_posts_per_campaign": round(avg_posts, 1),
        "theme_distribution": dict(theme_dist),
        "tone_distribution": dict(tone_dist),
        "avg_char_count": round(avg_char_count, 1),
        "top_hashtags": [{"tag": tag, "count": count} for tag, count in top_hashtags],
        "content_calendar": calendar,
        "coverage_by_source": dict(source_counter),
    }


def get_campaign_comparison(user_id):
    """Per-campaign breakdown for comparison."""
    with get_db() as conn:
        campaigns = conn.execute(
            "SELECT id, theme, audience, tone, status, created_at FROM campaigns WHERE user_id = ?",
            (user_id,),
        ).fetchall()

        result = []
        for c in campaigns:
            posts = conn.execute(
                "SELECT content FROM campaign_posts WHERE campaign_id = ?",
                (c["id"],),
            ).fetchall()

            char_counts = [len(p["content"] or "") for p in posts if p["content"]]
            avg_cc = sum(char_counts) / len(char_counts) if char_counts else 0

            result.append(
                {
                    "campaign_id": c["id"],
                    "theme": c["theme"],
                    "audience": c["audience"],
                    "tone": c["tone"],
                    "post_count": len(posts),
                    "avg_char_count": round(avg_cc, 1),
                    "status": c["status"],
                    "created_at": c["created_at"],
                }
            )

    return result
