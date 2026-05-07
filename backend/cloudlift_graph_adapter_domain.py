"""DynamoDB graph adapter — domain methods (thin shim, cloudlift.bridge pattern).

Provides DynamoDBGraphAdapterDomainMixin — inherited by DynamoDBGraphAdapter
in cloudlift_graph_adapter.py (mirrors ArangoClientDomainMixin pattern).

RO-specific domain schema layer. AQL query logic lives in cloudlift IGraphDatabase;
these are RO business domain methods that operate on RO's graph schema.
All domain methods have the same signature as their ArangoClientDomainMixin
counterparts so call sites need no changes after the get_graph_client() swap.
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class DynamoDBGraphAdapterDomainMixin:
    """Domain methods for DynamoDBGraphAdapter (all ArangoClientDomainMixin equivalents)."""

    # provided by DynamoDBGraphAdapter:
    def _scan_collection(self, collection: str) -> list: ...
    def _query_by_user_id(self, collection: str, user_id: Any, limit: int | None = None) -> list: ...
    def _count_collection(self, collection: str) -> int: ...
    def _edge_exists(self, to_id: str, edge_collection: str) -> bool: ...
    def _query_gsi(self, index: str, pk_name: str, pk_val: str, sk_name: str | None = None,
                   sk_val: str | None = None, limit: int | None = None, count_only: bool = False): ...
    def _get_vertex_by_id(self, vertex_id: str) -> dict | None: ...
    def upsert_vertex(self, collection: str, data: dict, key_source: str | None = None) -> str: ...
    def upsert_edge(self, collection: str, from_id: str, to_id: str, data: dict | None = None) -> str: ...

    # ── Phase 9 traversals ────────────────────────────────────────────────────

    def get_clients_by_technology(self, tech_name: str) -> list[dict]:
        techs = self._scan_collection("ro_technologies")
        tech = next((t for t in techs if (t.get("name") or "").lower() == tech_name.lower()), None)
        if not tech:
            return []
        edges = self._query_gsi("gsi3-to-edge", "to_id", tech["_id"],
                                "edge_collection", "ro_client_used_tech")
        return [v for e in edges for v in [self._get_vertex_by_id(e["from_id"])] if v]

    def get_clients_by_governance(self, control_name: str) -> list[dict]:
        ctrls = self._scan_collection("ro_governance_controls")
        ctrl = next((c for c in ctrls if (c.get("name") or "").lower() == control_name.lower()), None)
        if not ctrl:
            return []
        edges = self._query_gsi("gsi3-to-edge", "to_id", ctrl["_id"],
                                "edge_collection", "ro_client_required_governance")
        return [v for e in edges for v in [self._get_vertex_by_id(e["from_id"])] if v]

    def get_technology_summary(self) -> list[dict]:
        techs = self._scan_collection("ro_technologies")
        result = []
        for tech in techs:
            count = self._query_gsi("gsi3-to-edge", "to_id", tech["_id"],
                                    "edge_collection", "ro_client_used_tech",
                                    count_only=True)
            result.append({
                "name": tech.get("name", ""),
                "category": tech.get("category", ""),
                "client_count": count,
            })
        return result

    # ── Phase 11 knowledge context ────────────────────────────────────────────

    def get_knowledge_context(self, theme: str, limit: int = 10) -> dict:
        if os.environ.get("CLOUDLIFT_ENV", "local") == "aws":
            try:
                from cloudlift_search_adapter import keyword_search_knowledge_context  # noqa: PLC0415
                return keyword_search_knowledge_context(theme, limit)
            except Exception as exc:
                logger.warning("[graph_domain] OpenSearch keyword search failed: %s", exc)
        return {"clients": [], "skills": [], "milestones": []}

    # ── Phase 11 campaign coverage ────────────────────────────────────────────

    def get_campaign_coverage(self, user_id: Any = None) -> dict:
        empty = {
            "total_clients": 0, "covered_clients": 0,
            "total_skills": 0, "covered_skills": 0,
            "total_milestones": 0, "covered_milestones": 0,
            "overall_coverage_pct": 0.0, "by_campaign": [],
        }
        try:
            total_clients = self._count_collection("ro_client_projects")
            total_skills = self._count_collection("ro_ai_skills")
            total_milestones = self._count_collection("ro_journey_milestones")

            covered_clients = sum(
                1 for c in self._scan_collection("ro_client_projects")
                if self._edge_exists(c["_id"], "ro_post_references_client")
            )
            covered_skills = sum(
                1 for s in self._scan_collection("ro_ai_skills")
                if self._edge_exists(s["_id"], "ro_post_references_skill")
            )
            covered_milestones = sum(
                1 for m in self._scan_collection("ro_journey_milestones")
                if self._edge_exists(m["_id"], "ro_post_references_milestone")
            )

            campaigns = self._scan_collection("ro_campaigns")
            by_campaign = []
            for camp in campaigns:
                posts = self._query_gsi("gsi2-from-edge", "from_id", camp["_id"],
                                        "edge_collection", "ro_campaign_contains_post")
                covered = sum(
                    1 for e in posts
                    if (self._edge_exists(e["to_id"], "ro_post_references_client") or
                        self._edge_exists(e["to_id"], "ro_post_references_skill") or
                        self._edge_exists(e["to_id"], "ro_post_references_milestone"))
                )
                by_campaign.append({
                    "campaign_id": camp["_id"],
                    "theme": camp.get("theme", ""),
                    "covered_count": covered,
                })

            total = total_clients + total_skills + total_milestones
            covered = covered_clients + covered_skills + covered_milestones
            pct = round(covered / total * 100, 1) if total > 0 else 0.0
            return {
                "total_clients": total_clients, "covered_clients": covered_clients,
                "total_skills": total_skills, "covered_skills": covered_skills,
                "total_milestones": total_milestones, "covered_milestones": covered_milestones,
                "overall_coverage_pct": pct, "by_campaign": by_campaign,
            }
        except Exception as exc:
            logger.warning("[graph_domain] get_campaign_coverage failed: %s", exc)
            return empty

    # ── Phase 11 campaign writer ──────────────────────────────────────────────

    def write_campaign_to_graph(self, campaign: dict, posts: list) -> bool:
        try:
            campaign_vid = self.upsert_vertex(
                "ro_campaigns",
                {
                    "theme": campaign.get("theme", ""),
                    "audience": campaign.get("audience", ""),
                    "tone": campaign.get("tone", ""),
                    "status": campaign.get("status", "draft"),
                    "post_count": len(posts),
                },
                key_source=f"campaign-{campaign.get('id', campaign.get('theme', ''))}",
            )
            for post in posts:
                post_vid = self.upsert_vertex(
                    "ro_campaign_posts",
                    {
                        "title": post.get("title", ""),
                        "content": post.get("content", "")[:500],
                        "hashtags": post.get("hashtags", ""),
                        "position": post.get("position", 0),
                    },
                    key_source=f"post-{campaign_vid}-{post.get('position', 0)}",
                )
                self.upsert_edge("ro_campaign_contains_post", campaign_vid, post_vid)
                for ref in post.get("source_refs", []):
                    self._link_post_to_source(post_vid, ref)
            return True
        except Exception as exc:
            logger.error("[graph_domain] write_campaign_to_graph failed: %s", exc)
            return False

    def _link_post_to_source(self, post_vid: str, ref: dict) -> None:
        if not isinstance(ref, dict):
            return
        edge_map = {
            "client": "ro_post_references_client",
            "skill": "ro_post_references_skill",
            "milestone": "ro_post_references_milestone",
            "outcome": "ro_post_references_outcome",
        }
        edge_coll = edge_map.get(ref.get("type", ""))
        ref_id = ref.get("_id", "")
        if edge_coll and ref_id:
            self.upsert_edge(edge_coll, post_vid, ref_id)

    # ── Phase 14 deep profile ─────────────────────────────────────────────────

    def write_deep_profile_to_graph(self, profile: dict) -> bool:
        try:
            profile_vid = self.upsert_vertex(
                "ro_deep_profiles",
                {
                    "summary": profile.get("professional_summary", "")[:200],
                    "trajectory": profile.get("career_arc", {}).get("trajectory", ""),
                    "years_total": profile.get("career_arc", {}).get("years_total", 0),
                    "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                },
                key_source="deep_profile_primary",
            )
            for tech in profile.get("technology_mastery", []):
                name = tech.get("name", "")
                if not name:
                    continue
                skill_vid = self.upsert_vertex("ro_ai_skills", {"name": name},
                                               key_source=name.lower())
                self.upsert_edge(
                    "ro_profile_demonstrates_skill", profile_vid, skill_vid,
                    {"proficiency": tech.get("proficiency", ""),
                     "evidence_count": len(tech.get("evidence", [])),
                     "endorsement_count": tech.get("endorsement_count", 0)},
                )
            for impact in profile.get("business_impacts", []):
                title = impact.get("title", "")
                if not title:
                    continue
                outcome_vid = self.upsert_vertex(
                    "ro_business_outcomes",
                    {"title": title, "context": impact.get("context", ""),
                     "scope": impact.get("scope", "")},
                    key_source=title.lower(),
                )
                self.upsert_edge(
                    "ro_profile_achieved_outcome", profile_vid, outcome_vid,
                    {"star_bullet": impact.get("star_bullet", "")},
                )
            return True
        except Exception as exc:
            logger.error("[graph_domain] write_deep_profile_to_graph failed: %s", exc)
            return False

    # ── CT-4 context queries ──────────────────────────────────────────────────

    def query_projects_by_user(self, user_id: str, limit: int = 3) -> list[dict]:
        try:
            items = self._query_by_user_id("ro_client_projects", user_id, limit=limit)
            return [{"name": i.get("name", i.get("client_name", "")),
                     "outcomes": i.get("outcomes", [])} for i in items]
        except Exception:
            return []

    def query_journey_milestones(self, user_id: str, limit: int = 5) -> list[dict]:
        try:
            items = self._query_by_user_id("ro_journey_milestones", user_id, limit=limit)
            return [{"event": i.get("title", ""), "date": i.get("date", ""),
                     "impact": i.get("description", "")} for i in items]
        except Exception:
            return []

    def query_business_outcomes(self, user_id: str, limit: int = 4) -> list[dict]:
        try:
            items = self._query_by_user_id("ro_business_outcomes", user_id, limit=limit)
            return [{"description": i.get("title", i.get("description", "")),
                     "metrics": i.get("metrics", [])} for i in items]
        except Exception:
            return []

    def query_skills_inventory(self, user_id: str, limit: int = 5) -> list[dict]:
        try:
            items = self._query_by_user_id("ro_skills", user_id, limit=limit)
            return [{"skill": i.get("name", ""), "adopted_date": i.get("first_seen", ""),
                     "projects": i.get("projects_count", 0)} for i in items]
        except Exception:
            return []
