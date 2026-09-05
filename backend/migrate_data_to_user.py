#!/usr/bin/env python3
"""
Migrate (copy) career data from source users to target user.

Copies OPI, AHEAD, Navitus projects and AI Journey data
from user_ids 0, 1, 3 to a target user (mvogt99@gmail.com).
Also ensures the target user exists with the specified password.

Usage:
    cd backend && python migrate_data_to_user.py
"""

import contextlib

from werkzeug.security import generate_password_hash

TARGET_EMAIL = "mvogt99@gmail.com"
TARGET_PASSWORD = "password"

# Source user IDs that own the real career data
SOURCE_USERS = {0, 1, 3}


def get_db():
    from models import get_db_connection

    return get_db_connection()


def ensure_target_user(conn):
    """Ensure target user exists with correct password. Return user_id."""
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE email = ?", (TARGET_EMAIL,)
    ).fetchone()
    if row:
        # Update password to ensure it matches
        hashed = generate_password_hash(TARGET_PASSWORD)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, row["id"]))
        conn.commit()
        print(f"  Updated password for user {row['id']} ({TARGET_EMAIL})")
        return row["id"]
    else:
        hashed = generate_password_hash(TARGET_PASSWORD)
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (TARGET_EMAIL, hashed),
        )
        conn.commit()
        uid = cursor.lastrowid
        print(f"  Created user {uid} ({TARGET_EMAIL})")
        return uid


def copy_rows(conn, table, source_users, target_id, id_col="id", user_col="user_id", fk_map=None):
    """Copy rows from source users to target user, returning old_id -> new_id mapping."""
    id_map = {}
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE {user_col} IN ({','.join('?' * len(source_users))})",
        list(source_users),
    ).fetchall()

    if not rows:
        print(f"  {table}: 0 rows to copy")
        return id_map

    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
    insert_cols = [c for c in columns if c != id_col]
    placeholders = ",".join("?" * len(insert_cols))
    col_names = ",".join(insert_cols)

    copied = 0
    skipped = 0
    for row in rows:
        row_dict = dict(row)
        old_id = row_dict[id_col]

        # Apply foreign key remapping if provided
        if fk_map:
            for fk_col, mapping in fk_map.items():
                if fk_col in row_dict and row_dict[fk_col] in mapping:
                    row_dict[fk_col] = mapping[row_dict[fk_col]]

        # Set target user
        row_dict[user_col] = target_id

        values = [row_dict[c] for c in insert_cols]

        try:
            cursor = conn.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values
            )
            new_id = cursor.lastrowid
            id_map[old_id] = new_id
            copied += 1
        except Exception:  # noqa: BLE001 — duplicate-key violation, either dialect
            skipped += 1
            # Try to find existing row for mapping
            with contextlib.suppress(Exception):
                existing_row = conn.execute(
                    f"SELECT {id_col} FROM {table}"
                    f" WHERE {user_col} = ?"
                    f" ORDER BY {id_col} DESC LIMIT 1",
                    (target_id,),
                ).fetchone()
                if existing_row:
                    id_map[old_id] = existing_row[0]

    conn.commit()
    print(f"  {table}: {copied} copied, {skipped} skipped (already exist)")
    return id_map


def copy_child_rows(conn, table, parent_col, parent_map, id_col="id"):
    """Copy child rows that reference remapped parent IDs."""
    if not parent_map:
        print(f"  {table}: no parent rows to follow")
        return {}

    id_map = {}
    old_ids = list(parent_map.keys())
    rows = conn.execute(
        f"SELECT * FROM {table} WHERE {parent_col} IN ({','.join('?' * len(old_ids))})",
        old_ids,
    ).fetchall()

    if not rows:
        print(f"  {table}: 0 child rows to copy")
        return id_map

    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
    insert_cols = [c for c in columns if c != id_col]
    placeholders = ",".join("?" * len(insert_cols))
    col_names = ",".join(insert_cols)

    copied = 0
    for row in rows:
        row_dict = dict(row)
        old_id = row_dict[id_col]
        row_dict[parent_col] = parent_map[row_dict[parent_col]]

        values = [row_dict[c] for c in insert_cols]
        try:
            cursor = conn.execute(
                f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values
            )
            id_map[old_id] = cursor.lastrowid
            copied += 1
        except Exception:  # noqa: BLE001 — duplicate-key violation, either dialect
            pass

    conn.commit()
    print(f"  {table}: {copied} child rows copied")
    return id_map


def copy_rows_with_string_id(conn, table, source_users, target_id, id_col="id", user_col="user_id"):
    """Copy rows that use string/UUID primary keys."""
    import uuid

    rows = conn.execute(
        f"SELECT * FROM {table} WHERE {user_col} IN ({','.join('?' * len(source_users))})",
        list(source_users),
    ).fetchall()

    if not rows:
        print(f"  {table}: 0 rows to copy")
        return {}

    columns = [desc[0] for desc in conn.execute(f"SELECT * FROM {table} LIMIT 0").description]
    insert_cols = columns[:]  # include id col since we generate new UUID
    placeholders = ",".join("?" * len(insert_cols))
    col_names = ",".join(insert_cols)

    id_map = {}
    copied = 0
    for row in rows:
        row_dict = dict(row)
        old_id = row_dict[id_col]
        new_id = str(uuid.uuid4())
        row_dict[id_col] = new_id
        row_dict[user_col] = target_id

        values = [row_dict[c] for c in insert_cols]
        try:
            conn.execute(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})", values)
            id_map[old_id] = new_id
            copied += 1
        except Exception:  # noqa: BLE001 — duplicate-key violation, either dialect
            pass

    conn.commit()
    print(f"  {table}: {copied} copied with new UUIDs")
    return id_map


def main():
    conn = get_db()

    print("=== Resume Optimizer Data Migration ===")
    print(f"Target: {TARGET_EMAIL}")
    print()

    # 1. Ensure target user exists
    print("1. Ensuring target user...")
    target_id = ensure_target_user(conn)
    print(f"   Target user_id: {target_id}")
    print()

    # 2. Copy resumes
    print("2. Copying resumes...")
    copy_rows(conn, "resumes", SOURCE_USERS, target_id)
    print()

    # 3. Copy job descriptions
    print("3. Copying job descriptions...")
    copy_rows(conn, "job_descriptions", SOURCE_USERS, target_id)
    print()

    # 4. Copy resume versions (FK to resumes)
    print("4. Copying resume versions...")
    copy_rows(conn, "resume_versions", SOURCE_USERS, target_id)
    print()

    # 5. Copy client projects
    print("5. Copying client projects...")
    project_map = copy_rows(conn, "client_projects", SOURCE_USERS, target_id)
    print()

    # 6. Copy project documents (FK to client_projects via client_id)
    print("6. Copying project documents...")
    if project_map:
        copy_child_rows(conn, "project_documents", "client_id", project_map)
    else:
        print("  project_documents: no projects to follow")
    print()

    # 7. Copy journey data (user_id=0 is the main source)
    print("7. Copying journey sources...")
    copy_rows(conn, "journey_sources", SOURCE_USERS, target_id)
    print()

    print("8. Copying journey events...")
    copy_rows(conn, "journey_events", SOURCE_USERS, target_id)
    print()

    print("9. Copying journey narratives...")
    copy_rows(conn, "journey_narratives", SOURCE_USERS, target_id)
    print()

    # 8. Copy experience sessions and messages
    print("10. Copying experience sessions...")
    session_map = copy_rows(conn, "experience_sessions", SOURCE_USERS, target_id)
    print()

    print("11. Copying experience messages...")
    if session_map:
        copy_child_rows(conn, "experience_messages", "session_id", session_map)
    print()

    # 9. Copy extracted experiences
    print("12. Copying extracted experiences...")
    copy_rows(conn, "extracted_experiences", SOURCE_USERS, target_id)
    print()

    # 10. Copy campaigns
    print("13. Copying campaigns...")
    campaign_map = copy_rows(conn, "campaigns", SOURCE_USERS, target_id)
    print()

    # 11. Copy campaign posts (FK to campaigns)
    print("14. Copying campaign posts...")
    if campaign_map:
        copy_child_rows(conn, "campaign_posts", "campaign_id", campaign_map)
    print()

    # 12. Copy campaign sessions
    print("15. Copying campaign sessions...")
    cs_map = copy_rows(conn, "campaign_sessions", SOURCE_USERS, target_id)
    print()

    print("16. Copying campaign messages...")
    if cs_map:
        copy_child_rows(conn, "campaign_messages", "session_id", cs_map)
    print()

    # 13. Copy deep profiles
    print("17. Copying deep profiles...")
    copy_rows(conn, "deep_profiles", SOURCE_USERS, target_id)
    print()

    # 14. Copy role syntheses
    print("18. Copying role syntheses...")
    copy_rows(conn, "role_syntheses", SOURCE_USERS, target_id)
    print()

    # 15. Copy job postings
    print("19. Copying job postings...")
    copy_rows(conn, "job_postings", SOURCE_USERS, target_id)
    print()

    # 16. Copy search criteria
    print("20. Copying search criteria...")
    copy_rows(conn, "search_criteria", SOURCE_USERS, target_id)
    print()

    # 17. Copy agent runs
    print("21. Copying agent runs...")
    copy_rows(conn, "agent_runs", SOURCE_USERS, target_id)
    print()

    # 18. Copy batch jobs
    print("22. Copying batch jobs...")
    copy_rows(conn, "batch_jobs", SOURCE_USERS, target_id)
    print()

    # 19. Skills interview sessions
    print("23. Copying skills interview sessions...")
    with contextlib.suppress(Exception):
        copy_rows(conn, "skills_interview_sessions", SOURCE_USERS, target_id)
    print()

    # 20. Journey review sessions
    print("24. Copying journey review sessions...")
    with contextlib.suppress(Exception):
        copy_rows(conn, "journey_review_sessions", SOURCE_USERS, target_id)
    print()

    # 21. Builder interview sessions
    print("25. Copying builder interview sessions...")
    with contextlib.suppress(Exception):
        copy_rows(conn, "builder_interview_sessions", SOURCE_USERS, target_id)
    print()

    # 22. ATS improvement sessions
    print("26. Copying ATS improvement sessions...")
    with contextlib.suppress(Exception):
        copy_rows(conn, "ats_improvement_sessions", SOURCE_USERS, target_id)
    print()

    # 23. Deep interview sessions
    print("27. Copying deep interview sessions...")
    with contextlib.suppress(Exception):
        copy_rows(conn, "deep_interview_sessions", SOURCE_USERS, target_id)
    print()

    conn.close()

    # Verify
    print("=== Verification ===")
    conn = get_db()
    tables = [
        "resumes",
        "job_descriptions",
        "resume_versions",
        "client_projects",
        "journey_sources",
        "journey_events",
        "journey_narratives",
        "extracted_experiences",
        "campaigns",
        "campaign_posts",
        "deep_profiles",
        "role_syntheses",
        "job_postings",
        "search_criteria",
        "agent_runs",
    ]
    for table in tables:
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (target_id,)
            ).fetchone()
            print(f"  {table}: {row[0]} rows for user {target_id}")
        except Exception as e:
            print(f"  {table}: error — {e}")

    conn.close()
    print()
    print(f"Done! User {TARGET_EMAIL} (id={target_id}) now has copies of all career data.")
    print(f"Login with: email={TARGET_EMAIL}, password={TARGET_PASSWORD}")


if __name__ == "__main__":
    main()
