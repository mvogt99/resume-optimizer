"""
Domain-specific ArangoDB methods for ArangoClient (Phase 9–P2-B).

Defines ArangoClientDomainMixin — inherited by ArangoClient in arango_client.py.
Split from arango_client.py to comply with 500-line file limit.
"""

GRAPH_NAME = "ro_knowledge_graph"


class ArangoClientDomainMixin:
    """Mixin providing Phase 9–P2-B domain methods for ArangoClient."""

    # --- Phase 9 gap fix: graph traversal methods ---

    def get_clients_by_technology(self, tech_name):
        """INBOUND traversal: find client projects using a specific technology."""
        if not self._db:
            return []
        aql = """
            FOR tech IN ro_technologies
                FILTER LOWER(tech.name) == LOWER(@tech_name)
                FOR client IN 1..1 INBOUND tech GRAPH @graph
                    OPTIONS {edgeCollections: ["ro_client_used_tech"]}
                    RETURN client
        """
        return self.query(aql, {"tech_name": tech_name, "graph": GRAPH_NAME})

    def get_clients_by_governance(self, control_name):
        """INBOUND traversal: find client projects requiring a governance control."""
        if not self._db:
            return []
        aql = """
            FOR ctrl IN ro_governance_controls
                FILTER LOWER(ctrl.name) == LOWER(@control_name)
                FOR client IN 1..1 INBOUND ctrl GRAPH @graph
                    OPTIONS {edgeCollections: ["ro_client_required_governance"]}
                    RETURN client
        """
        return self.query(aql, {"control_name": control_name, "graph": GRAPH_NAME})

    def get_technology_summary(self):
        """All technologies with client counts."""
        if not self._db:
            return []
        aql = """
            FOR tech IN ro_technologies
                LET clients = (
                    FOR client IN 1..1 INBOUND tech GRAPH @graph
                        OPTIONS {edgeCollections: ["ro_client_used_tech"]}
                        RETURN client._key
                )
                RETURN {
                    name: tech.name,
                    category: tech.category,
                    client_count: LENGTH(clients)
                }
        """
        return self.query(aql, {"graph": GRAPH_NAME})

    # --- Phase 11: knowledge context for campaign grounding ---

    def get_knowledge_context(self, theme, limit=10):
        """Combined AQL: client projects, skills, milestones matching a theme keyword."""
        if not self._db:
            return {"clients": [], "skills": [], "milestones": []}
        theme_lower = theme.lower()

        clients = self.query(
            """
            FOR doc IN ro_client_projects
                FILTER CONTAINS(LOWER(doc.client_name), @kw)
                    OR CONTAINS(LOWER(doc.description OR ""), @kw)
                LIMIT @lim
                RETURN {name: doc.client_name, _id: doc._id}
            """,
            {"kw": theme_lower, "lim": limit},
        )
        skills = self.query(
            """
            FOR doc IN ro_ai_skills
                FILTER CONTAINS(LOWER(doc.name), @kw)
                LIMIT @lim
                RETURN {name: doc.name, _id: doc._id}
            """,
            {"kw": theme_lower, "lim": limit},
        )
        milestones = self.query(
            """
            FOR doc IN ro_journey_milestones
                FILTER CONTAINS(LOWER(doc.title OR ""), @kw)
                    OR CONTAINS(LOWER(doc.description OR ""), @kw)
                LIMIT @lim
                RETURN {title: doc.title, date: doc.event_date, _id: doc._id}
            """,
            {"kw": theme_lower, "lim": limit},
        )
        return {"clients": clients, "skills": skills, "milestones": milestones}

    # --- Phase 11: campaign coverage analytics ---

    def get_campaign_coverage(self, user_id=None):
        """Analyze what percentage of the knowledge graph is covered by campaigns."""
        empty = {
            "total_clients": 0,
            "covered_clients": 0,
            "total_skills": 0,
            "covered_skills": 0,
            "total_milestones": 0,
            "covered_milestones": 0,
            "overall_coverage_pct": 0.0,
            "by_campaign": [],
        }
        if not self._db:
            return empty

        # Count totals
        total_clients = self.query("RETURN LENGTH(ro_client_projects)")[0]
        total_skills = self.query("RETURN LENGTH(ro_ai_skills)")[0]
        total_milestones = self.query("RETURN LENGTH(ro_journey_milestones)")[0]

        # Count covered (vertices with at least one inbound edge from campaign posts)
        covered_clients = self.query(
            """
            FOR c IN ro_client_projects
                LET refs = (
                    FOR v IN 1..1 INBOUND c GRAPH @graph
                        OPTIONS {edgeCollections: ["ro_post_references_client"]}
                        LIMIT 1
                        RETURN 1
                )
                FILTER LENGTH(refs) > 0
                RETURN 1
            """,
            {"graph": GRAPH_NAME},
        )
        covered_skills = self.query(
            """
            FOR s IN ro_ai_skills
                LET refs = (
                    FOR v IN 1..1 INBOUND s GRAPH @graph
                        OPTIONS {edgeCollections: ["ro_post_references_skill"]}
                        LIMIT 1
                        RETURN 1
                )
                FILTER LENGTH(refs) > 0
                RETURN 1
            """,
            {"graph": GRAPH_NAME},
        )
        covered_milestones = self.query(
            """
            FOR m IN ro_journey_milestones
                LET refs = (
                    FOR v IN 1..1 INBOUND m GRAPH @graph
                        OPTIONS {edgeCollections: ["ro_post_references_milestone"]}
                        LIMIT 1
                        RETURN 1
                )
                FILTER LENGTH(refs) > 0
                RETURN 1
            """,
            {"graph": GRAPH_NAME},
        )

        # Per-campaign breakdown
        by_campaign = self.query(
            """
            FOR camp IN ro_campaigns
                LET posts = (
                    FOR p IN 1..1 OUTBOUND camp GRAPH @graph
                        OPTIONS {edgeCollections: ["ro_campaign_contains_post"]}
                        LET ref_count = LENGTH(
                            FOR t IN 1..1 OUTBOUND p GRAPH @graph
                                OPTIONS {edgeCollections: [
                                    "ro_post_references_client",
                                    "ro_post_references_skill",
                                    "ro_post_references_milestone"
                                ]}
                                RETURN 1
                        )
                        FILTER ref_count > 0
                        RETURN 1
                )
                RETURN {
                    campaign_id: camp._id,
                    theme: camp.theme,
                    covered_count: LENGTH(posts)
                }
            """,
            {"graph": GRAPH_NAME},
        )

        total = total_clients + total_skills + total_milestones
        covered = len(covered_clients) + len(covered_skills) + len(covered_milestones)
        pct = round((covered / total * 100), 1) if total > 0 else 0.0

        return {
            "total_clients": total_clients,
            "covered_clients": len(covered_clients),
            "total_skills": total_skills,
            "covered_skills": len(covered_skills),
            "total_milestones": total_milestones,
            "covered_milestones": len(covered_milestones),
            "overall_coverage_pct": pct,
            "by_campaign": by_campaign,
        }

    # --- Phase 11: campaign graph writer ---

    def write_campaign_to_graph(self, campaign, posts):
        """Upsert campaign + posts + edges to source references."""
        if not self._db:
            return False

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

            # Campaign -> Post edge
            self.upsert_edge("ro_campaign_contains_post", campaign_vid, post_vid)

            # Link post to source references
            for ref in post.get("source_refs", []):
                self._link_post_to_source(post_vid, ref)

        return True

    def _link_post_to_source(self, post_vid, ref):
        """Route a source reference to the correct edge collection."""
        if not isinstance(ref, dict):
            return
        ref_type = ref.get("type", "")
        ref_id = ref.get("_id", "")
        if not ref_id:
            return

        edge_map = {
            "client": "ro_post_references_client",
            "skill": "ro_post_references_skill",
            "milestone": "ro_post_references_milestone",
            "outcome": "ro_post_references_outcome",
        }
        edge_coll = edge_map.get(ref_type)
        if edge_coll:
            self.upsert_edge(edge_coll, post_vid, ref_id)

    # --- Phase 14: Deep Profile graph methods ---

    def write_deep_profile_to_graph(self, profile):
        """Write deep profile to ArangoDB with edges to skills and outcomes."""
        if not self._db:
            return False

        summary = profile.get("professional_summary", "")[:200]
        profile_vid = self.upsert_vertex(
            "ro_deep_profiles",
            {
                "summary": summary,
                "trajectory": profile.get("career_arc", {}).get("trajectory", ""),
                "years_total": profile.get("career_arc", {}).get("years_total", 0),
                "updated_at": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
            },
            key_source="deep_profile_primary",
        )

        # Link to skills
        for tech in profile.get("technology_mastery", []):
            name = tech.get("name", "")
            if not name:
                continue
            skill_vid = self.upsert_vertex("ro_ai_skills", {"name": name}, key_source=name.lower())
            self.upsert_edge(
                "ro_profile_demonstrates_skill",
                profile_vid,
                skill_vid,
                {
                    "proficiency": tech.get("proficiency", ""),
                    "evidence_count": len(tech.get("evidence", [])),
                    "endorsement_count": tech.get("endorsement_count", 0),
                },
            )

        # Link to business outcomes
        for impact in profile.get("business_impacts", []):
            title = impact.get("title", "")
            if not title:
                continue
            outcome_vid = self.upsert_vertex(
                "ro_business_outcomes",
                {
                    "title": title,
                    "context": impact.get("context", ""),
                    "scope": impact.get("scope", ""),
                },
                key_source=title.lower(),
            )
            self.upsert_edge(
                "ro_profile_achieved_outcome",
                profile_vid,
                outcome_vid,
                {"star_bullet": impact.get("star_bullet", "")},
            )

        return True

    # CT-4: Query methods for agent context injection
    def query_projects_by_user(self, user_id: str, limit: int = 3):
        """Fetch user's client projects with quantified outcomes."""
        if not self._db:
            return []
        try:
            cursor = self._db.aql.execute(
                """
                FOR proj IN ro_client_projects
                  FILTER proj.user_id == @uid
                  LIMIT @lim
                  RETURN {name: proj.name, outcomes: proj.outcomes}
                """,
                bind_vars={"uid": user_id, "lim": limit},
            )
            return list(cursor) if cursor else []
        except Exception:
            return []

    def query_journey_milestones(self, user_id: str, limit: int = 5):
        """Fetch user's career milestones with impact."""
        if not self._db:
            return []
        try:
            cursor = self._db.aql.execute(
                """
                FOR ms IN ro_journey_milestones
                  FILTER ms.user_id == @uid
                  LIMIT @lim
                  RETURN {event: ms.event, date: ms.date, impact: ms.impact}
                """,
                bind_vars={"uid": user_id, "lim": limit},
            )
            return list(cursor) if cursor else []
        except Exception:
            return []

    def query_business_outcomes(self, user_id: str, limit: int = 4):
        """Fetch user's quantified business outcomes."""
        if not self._db:
            return []
        try:
            cursor = self._db.aql.execute(
                """
                FOR outcome IN ro_business_outcomes
                  FILTER outcome.user_id == @uid
                  LIMIT @lim
                  RETURN {description: outcome.description, metrics: outcome.metrics}
                """,
                bind_vars={"uid": user_id, "lim": limit},
            )
            return list(cursor) if cursor else []
        except Exception:
            return []

    def query_skills_inventory(self, user_id: str, limit: int = 5):
        """Fetch user's skills with adoption dates."""
        if not self._db:
            return []
        try:
            cursor = self._db.aql.execute(
                """
                FOR skill IN ro_skills
                  FILTER skill.user_id == @uid
                  LIMIT @lim
                  RETURN {skill: skill.name, adopted_date: skill.adopted_date, projects: skill.projects_count}
                """,
                bind_vars={"uid": user_id, "lim": limit},
            )
            return list(cursor) if cursor else []
        except Exception:
            return []
