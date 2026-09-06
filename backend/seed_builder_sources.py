"""
Seed script to populate builder data sources for testing the Resume Builder workflow.
Populates: client_projects (approved), journey_narratives (approved), extracted_experiences.
All data is derived from the real LinkedIn profile (Mike Vogt).

Usage: cd backend && python seed_builder_sources.py
"""

import contextlib
from models import get_db_connection
from seed_builder_experiences import seed_extracted_experiences
from seed_builder_narratives import seed_journey_narratives
from seed_builder_projects import USER_ID, seed_client_projects


def main():
    # closing() rather than a trailing close(): any exception in the checks or
    # the three seed_* calls used to leave the connection open.
    with contextlib.closing(get_db_connection()) as conn:
        cursor = conn.cursor()

        print("Seeding builder sources...")
        print()

        # Check for existing data to avoid duplicates
        try:
            cursor.execute("SELECT COUNT(*) FROM client_projects WHERE approved = 1")
            existing_projects = cursor.fetchone()[0]
        except Exception:
            existing_projects = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM journey_narratives WHERE approved = 1")
            existing_narratives = cursor.fetchone()[0]
        except Exception:
            existing_narratives = 0

        try:
            cursor.execute("SELECT COUNT(*) FROM extracted_experiences WHERE user_id = ?", (USER_ID,))
            existing_experiences = cursor.fetchone()[0]
        except Exception:
            existing_experiences = 0

        if existing_projects > 0 or existing_narratives > 0 or existing_experiences > 0:
            print(
                f"  Existing data found: {existing_projects} projects, "
                f"{existing_narratives} narratives, {existing_experiences} experiences"
            )
            print("  Clearing existing seed data...")
            cursor.execute("DELETE FROM client_projects WHERE folder_id LIKE 'seed_%'")
            cursor.execute("DELETE FROM journey_narratives WHERE user_id = ?", (USER_ID,))
            try:
                cursor.execute("DELETE FROM extracted_experiences WHERE user_id = ?", (USER_ID,))
                cursor.execute(
                    "DELETE FROM experience_sessions WHERE user_id = ? AND is_finalized = 1",
                    (USER_ID,),
                )
            except Exception:
                pass
            print()

        seed_client_projects(cursor)
        seed_journey_narratives(cursor)
        seed_extracted_experiences(cursor)

        conn.commit()

        print()
        print("Done! All 3 builder sources are now populated.")
        print("  - Client Projects: 4 approved projects (PwC, SPR, NVISIA, PSC Group)")
        print("  - Journey Narratives: 10 narratives (4 STAR, 4 skills, 2 career arcs)")
        print("  - Experience Interviews: 3 experiences (AHEAD, PwC, SPR)")
        print()
        print("Restart the backend and navigate to Resume Builder > Choose Sources.")
        print("All 4 source cards should now be selectable.")


if __name__ == "__main__":
    main()
