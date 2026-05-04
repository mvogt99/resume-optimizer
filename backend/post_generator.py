"""
LinkedIn post generation for campaigns.
Generates full post drafts from campaign seeds + graph context.
"""

import json
import logging

from llm_helper import call_llm_quality, extract_json
from models import get_db

logger = logging.getLogger(__name__)

LINKEDIN_CHAR_LIMIT = 3000


class PostGenerator:
    """Generate and manage LinkedIn post drafts for a campaign."""

    def generate_campaign_posts(self, campaign_id, user_id, job_id=None):
        """Generate all post drafts from campaign seeds. Returns list of post dicts."""
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return []

        metadata = json.loads(campaign["metadata_json"] or "{}")
        seeds = metadata.get("seeds", [])

        # Also load existing stub posts
        stubs = self._get_posts(campaign_id)
        if stubs and not seeds:
            seeds = [
                {"title": s["title"], "source_refs": json.loads(s["source_refs"] or "[]")}
                for s in stubs
            ]

        if not seeds:
            seeds = [
                {"title": f"Post {i + 1}", "key_points": [], "source_refs": []}
                for i in range(campaign["post_count"] or 3)
            ]

        posts = []
        for i, seed in enumerate(seeds):
            if job_id:
                from batch_jobs import get_batch_manager

                mgr = get_batch_manager()
                if mgr.is_cancelled(job_id):
                    break
                mgr.update_progress(
                    job_id,
                    {
                        "current": i + 1,
                        "total": len(seeds),
                        "title": seed.get("title", ""),
                    },
                )

            post_data = self._generate_single_post(campaign, seed, i, previous_posts=posts)
            self._upsert_post(campaign_id, i, post_data)
            posts.append(post_data)

        # Update campaign post count
        with get_db() as conn:
            conn.execute(
                "UPDATE campaigns SET post_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (len(posts), campaign_id),
            )
            conn.commit()

        return posts

    def regenerate_post(self, post_id, feedback=""):
        """Save current draft to history, regenerate with feedback."""
        post = self._get_post_by_id(post_id)
        if not post:
            return {"error": "Post not found"}

        # Save current to draft history
        history = json.loads(post["draft_history"] or "[]")
        if post["content"]:
            history.append(
                {
                    "content": post["content"],
                    "title": post["title"],
                    "hashtags": post["hashtags"],
                }
            )

        campaign = self._get_campaign(post["campaign_id"])
        if not campaign:
            return {"error": "Campaign not found"}

        seed = {
            "title": post["title"],
            "source_refs": json.loads(post["source_refs"] or "[]"),
        }

        # Load sibling posts so regenerated post avoids repeating their hooks
        sibling_posts = [p for p in self._get_posts(post["campaign_id"]) if p["id"] != post_id]

        post_data = self._generate_single_post(
            campaign,
            seed,
            post["position"],
            feedback=feedback,
            previous_posts=sibling_posts,
        )

        with get_db() as conn:
            conn.execute(
                "UPDATE campaign_posts SET title = ?, content = ?, hashtags = ?, "
                "char_count = ?, source_refs = ?, draft_history = ?, feedback = ?, "
                "status = 'draft', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (
                    post_data.get("title", ""),
                    post_data.get("content", ""),
                    post_data.get("hashtags", ""),
                    post_data.get("char_count", 0),
                    json.dumps(post_data.get("source_refs", [])),
                    json.dumps(history),
                    feedback,
                    post_id,
                ),
            )
            conn.commit()

        post_data["id"] = post_id
        post_data["draft_history"] = history
        return post_data

    def _generate_single_post(self, campaign, seed, position, feedback="", previous_posts=None):
        """Generate a single LinkedIn post draft."""
        source_context = self._get_source_context(seed.get("source_refs", []))

        feedback_text = ""
        if feedback:
            feedback_text = (
                f"\n\nUser feedback on previous draft: {feedback}\nPlease address this feedback."
            )

        prompt = (
            "Write a LinkedIn post for the following campaign.\n\n"
            f"Campaign Theme: {campaign.get('theme', '')}\n"
            f"Target Audience: {campaign.get('audience', '')}\n"
            f"Tone: {campaign.get('tone', 'thought-leader')}\n"
            f"Storyline Arc: {campaign.get('storyline', '')}\n"
            f"Post {position + 1} of {campaign.get('post_count', '?')}\n\n"
            f"Post Title/Topic: {seed.get('title', '')}\n"
        )

        if seed.get("key_points"):
            prompt += "Key points to cover:\n"
            for p in seed["key_points"]:
                prompt += f"- {p}\n"

        if source_context:
            prompt += f"\nReal-world context from knowledge graph:\n{source_context}\n"

        if previous_posts:
            prompt += "\nPrevious posts in this campaign (DO NOT repeat their hooks or openings):\n"
            for j, prev in enumerate(previous_posts):
                opener = prev.get("content", "")[:100]
                prompt += f'  Post {j + 1}: "{opener}..."\n'
            prompt += "IMPORTANT: Use a DIFFERENT opening hook and angle from the posts above.\n"

        prompt += (
            f"{feedback_text}\n\n"
            "Requirements:\n"
            f"- Maximum {LINKEDIN_CHAR_LIMIT} characters (this is a hard LinkedIn limit)\n"
            "- Start with a compelling hook (first 2 lines are visible before 'see more')\n"
            "- If an [Outcome] with a metric is available in the context above, "
            "weave it in as a credible data point — do NOT invent metrics\n"
            "- Use short paragraphs and white space for readability\n"
            "- Include a call-to-action or question at the end\n"
            "- Include 3-5 relevant hashtags at the end\n\n"
            "Return a JSON object with:\n"
            '- "title": post title (for internal reference)\n'
            '- "content": the full LinkedIn post text\n'
            '- "hashtags": comma-separated hashtag string'
        )

        raw = call_llm_quality(prompt, task_type="reasoning", max_tokens=2048)
        parsed = extract_json(raw) if raw else None

        if isinstance(parsed, dict):
            content = parsed.get("content", "")
            # Enforce char limit
            if len(content) > LINKEDIN_CHAR_LIMIT:
                content = content[: LINKEDIN_CHAR_LIMIT - 3] + "..."
            return {
                "title": parsed.get("title", seed.get("title", f"Post {position + 1}")),
                "content": content,
                "hashtags": parsed.get("hashtags", ""),
                "source_refs": seed.get("source_refs", []),
                "char_count": len(content),
                "position": position,
            }

        # Fallback: use raw LLM output as content
        content = raw or f"[Draft for: {seed.get('title', 'Post')}]"
        if len(content) > LINKEDIN_CHAR_LIMIT:
            content = content[: LINKEDIN_CHAR_LIMIT - 3] + "..."
        return {
            "title": seed.get("title", f"Post {position + 1}"),
            "content": content,
            "hashtags": "",
            "source_refs": seed.get("source_refs", []),
            "char_count": len(content),
            "position": position,
        }

    def _get_source_context(self, source_refs):
        """Query ArangoDB for referenced clients/skills/milestones."""
        if not source_refs:
            return ""

        lines = []
        try:
            from arango_client import get_arango_client

            arango = get_arango_client()
            if not arango.is_connected:
                return ""

            for ref in source_refs:
                if not isinstance(ref, dict):
                    continue
                ref_id = ref.get("_id", "")
                ref_type = ref.get("type", "")
                ref_name = ref.get("name", "")

                if ref_id and "/" in ref_id:
                    coll, key = ref_id.split("/", 1)
                    doc = arango.get_vertex(coll, key)
                    if doc:
                        if ref_type == "client":
                            lines.append(
                                f"[Client] {doc.get('client_name', ref_name)}: "
                                f"{doc.get('description', '')[:200]}"
                            )
                        elif ref_type == "skill":
                            lines.append(f"[Skill] {doc.get('name', ref_name)}")
                        elif ref_type == "milestone":
                            lines.append(
                                f"[Milestone] {doc.get('title', ref_name)} "
                                f"({doc.get('event_date', '')})"
                            )
                elif ref_type == "outcome":
                    lines.append(
                        f"[Outcome] {doc.get('title', ref_name)}: "
                        f"{doc.get('description', '')[:200]}"
                    )
                    metric = doc.get("metric_value", "") or doc.get("metric", "")
                    if metric:
                        lines[-1] += f" (Metric: {metric})"
                elif ref_name:
                    lines.append(f"[{ref_type}] {ref_name}")
        except Exception:
            logger.debug("ArangoDB graph context unavailable, using SQLite fallback", exc_info=True)

        # SQLite fallback: if no outcome refs from ArangoDB, load top outcomes
        has_outcome_ref = any("[Outcome]" in line for line in lines)
        if not has_outcome_ref:
            try:
                with get_db() as conn:
                    rows = conn.execute(
                        "SELECT client_name, business_outcomes_json FROM client_projects "
                        "WHERE approved = 1 AND business_outcomes_json IS NOT NULL"
                    ).fetchall()
                for row in rows:
                    try:
                        bo_list = json.loads(row["business_outcomes_json"] or "[]")
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if not isinstance(bo_list, list):
                        continue
                    sorted_bos = sorted(
                        [b for b in bo_list if isinstance(b, dict) and b.get("outcome_title")],
                        key=lambda b: b.get("confidence", 0),
                        reverse=True,
                    )
                    for bo in sorted_bos[:2]:
                        line = f"[Outcome] {bo['outcome_title']}: {bo.get('description', '')[:150]}"
                        metric = bo.get("metric_value", "")
                        if metric:
                            line += f" (Metric: {metric})"
                        line += f" — {row['client_name']}"
                        lines.append(line)
            except Exception:
                logger.debug("SQLite outcome fallback failed", exc_info=True)

        return "\n".join(lines)

    # --- DB helpers ---

    def _get_campaign(self, campaign_id):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM campaigns WHERE id = ?", (campaign_id,)).fetchone()
        return dict(row) if row else None

    def _get_posts(self, campaign_id):
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM campaign_posts WHERE campaign_id = ? ORDER BY position",
                (campaign_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def _get_post_by_id(self, post_id):
        with get_db() as conn:
            row = conn.execute("SELECT * FROM campaign_posts WHERE id = ?", (post_id,)).fetchone()
        return dict(row) if row else None

    def _upsert_post(self, campaign_id, position, post_data):
        """Insert or update a post at a given position."""
        with get_db() as conn:
            # Check if stub exists
            existing = conn.execute(
                "SELECT id FROM campaign_posts WHERE campaign_id = ? AND position = ?",
                (campaign_id, position),
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE campaign_posts SET title = ?, content = ?, hashtags = ?, "
                    "char_count = ?, source_refs = ?, status = 'draft', "
                    "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (
                        post_data.get("title", ""),
                        post_data.get("content", ""),
                        post_data.get("hashtags", ""),
                        post_data.get("char_count", 0),
                        json.dumps(post_data.get("source_refs", [])),
                        existing[0],
                    ),
                )
            else:
                conn.execute(
                    "INSERT INTO campaign_posts "
                    "(campaign_id, position, title, content, hashtags, char_count, "
                    "source_refs, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft')",
                    (
                        campaign_id,
                        position,
                        post_data.get("title", ""),
                        post_data.get("content", ""),
                        post_data.get("hashtags", ""),
                        post_data.get("char_count", 0),
                        json.dumps(post_data.get("source_refs", [])),
                    ),
                )

            conn.commit()
