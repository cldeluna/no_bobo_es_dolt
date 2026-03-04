#!/usr/bin/python -tt
# Project: no_bobo_es_dolt
# Filename: dolt_manage.py
# claudiadeluna
# PyCharm

from __future__ import absolute_import, division, print_function

__author__ = "Claudia de Luna (claudia@indigowire.net)"
__version__ = ": 1.0 $"
__date__ = "3/1/26"
__copyright__ = "Copyright (c) 2023 Claudia"
__license__ = "Python"

import argparse
import csv
import getpass
import os
import sys

try:
    import mysql.connector
except ImportError:
    print("ERROR: mysql-connector-python is not installed.")
    print("       pip install mysql-connector-python")
    print("       uv pip install mysql-connector-python")
    sys.exit(1)


# ── SQL constants ─────────────────────────────────────────────────────────────

CREATE_DB_SQL = "CREATE DATABASE IF NOT EXISTS launch_sites;"
USE_DB_SQL    = "USE launch_sites;"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS sites (
    idx          INT           NOT NULL AUTO_INCREMENT,
    common_name  VARCHAR(100)  NOT NULL,
    lat          DECIMAL(9,6)  NOT NULL,
    lon          DECIMAL(9,6)  NOT NULL,
    country      VARCHAR(100)  NOT NULL,
    mgmt_org     VARCHAR(255),
    site_type    VARCHAR(50),
    status       VARCHAR(30)   DEFAULT 'Active',
    notes        TEXT,
    PRIMARY KEY (idx)
);
"""

INSERT_SQL = """
INSERT INTO sites (common_name, lat, lon, country, mgmt_org, site_type, status, notes)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
"""

UPDATE_SQL = """
UPDATE sites
SET lat = %s, lon = %s, country = %s, mgmt_org = %s,
    site_type = %s, status = %s, notes = %s
WHERE common_name = %s;
"""

DOLT_STATUS_SQL = "SELECT * FROM dolt_status;"
DOLT_ADD_SQL    = "CALL dolt_add('-A');"
DOLT_COMMIT_SQL = "CALL dolt_commit('-m', %s);"
DOLT_LOG_SQL    = "SELECT commit_hash, committer, message, date FROM dolt_log LIMIT 10;"
DOLT_RESET_SQL  = "CALL dolt_reset('--hard', 'HEAD~1');"
CHECKOUT_SQL    = "CALL dolt_checkout(%s);"

DOLT_DIFF_SQL = """
SELECT diff_type,
       COALESCE(to_common_name, from_common_name) AS common_name,
       from_status,   to_status,
       from_mgmt_org, to_mgmt_org
FROM   dolt_diff_sites
WHERE  to_commit = 'WORKING';
"""

DAMAGE_CHECK_SQL = """
SELECT common_name, lat, lon, country, status, notes
FROM   sites
WHERE  country = 'UNKNOWN' OR lat = 0.0
ORDER  BY common_name;
"""

DAMAGE_COUNT_SQL = """
SELECT COUNT(*) FROM sites WHERE country = 'UNKNOWN';
"""

VERIFY_RESTORE_SQL = """
SELECT common_name, lat, lon, country, status
FROM   sites
WHERE  lat != 0.0
ORDER  BY country, common_name
LIMIT  10;
"""

STILL_CORRUPTED_SQL = """
SELECT COUNT(*) FROM sites WHERE country = 'UNKNOWN';
"""

TOTAL_COUNT_SQL = "SELECT COUNT(*) FROM sites;"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def section(title, width=65):
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def run(cursor, sql, params=None, label=None):
    """Execute SQL, drain result set, print status line, return rows."""
    try:
        cursor.execute(sql, params or ())
        try:
            rows = cursor.fetchall()
        except Exception:
            rows = []
        tag = label or sql.strip().split("\n")[0].strip()[:60]
        print(f"  OK  {tag}")
        return rows
    except mysql.connector.Error as e:
        print(f"  FAIL  — {e}")
        raise


def get_active_branch(cursor):
    """Return the currently checked-out Dolt branch name."""
    cursor.execute("SELECT active_branch();")
    row = cursor.fetchone()
    try:
        cursor.fetchall()
    except Exception:
        pass
    return row[0] if row else "unknown"


def branch_exists(cursor, branch):
    """Return True if the given branch name exists in dolt_branches."""
    cursor.execute("SELECT COUNT(*) FROM dolt_branches WHERE name = %s;", (branch,))
    row = cursor.fetchone()
    try:
        cursor.fetchall()
    except Exception:
        pass
    return bool(row and row[0])


def check_and_set_branch(cursor, branch, create_if_missing=False):
    """Ensure we are on the correct branch, checking out if necessary."""
    current = get_active_branch(cursor)
    print(f"  Active branch : '{current}'")
    if current == branch:
        print(f"  Target branch : '{branch}' ✓  (no checkout needed)\n")
        return

    if not branch_exists(cursor, branch):
        if create_if_missing:
            print(f"  Branch '{branch}' does not exist — creating it ...")
            run(cursor, "CALL dolt_checkout('-b', %s);", params=(branch,),
                label=f"dolt_checkout('-b', '{branch}')")
        else:
            print(f"  ERROR: Branch '{branch}' does not exist.")
            print("         Dolt interpreted it as a table checkout and failed.")
            print("         To create it, run one of:")
            print(f"           CALL dolt_branch('{branch}');")
            print(f"           CALL dolt_checkout('-b', '{branch}');")
            print("         Or rerun this script with --create-branch")
            sys.exit(1)

    print(f"  Switching to  : '{branch}' ...")
    run(cursor, CHECKOUT_SQL, params=(branch,),
        label=f"dolt_checkout('{branch}')")
    active = get_active_branch(cursor)
    if active != branch:
        print(f"  ERROR: Expected '{branch}' but landed on '{active}'.")
        print(f"         Check available branches:  SELECT * FROM dolt_branches;")
        sys.exit(1)
    print(f"  Confirmed on  : '{active}'\n")


def print_table(rows, columns):
    """Render query results as a plain-text table."""
    if not rows:
        print("    (no rows)")
        return
    widths = [
        max(len(str(c)), max((len(str(r[i])) for r in rows), default=0))
        for i, c in enumerate(columns)
    ]
    header  = "  | ".join(f"{c:<{w}}" for c, w in zip(columns, widths))
    divider = "-+-".join("-" * w for w in widths)
    print(f"  {header}")
    print(f"  {divider}")
    for row in rows:
        print("  " + "  | ".join(f"{str(v):<{w}}" for v, w in zip(row, widths)))
    print()


def connect(host, port, user, password):
    print(f"  Connecting to {user}@{host}:{port} ...")
    try:
        conn = mysql.connector.connect(
            host=host, port=port, user=user, password=password
        )
        print("  Connected.\n")
        return conn
    except mysql.connector.Error as e:
        print(f"  ERROR: {e}")
        sys.exit(1)


# ── CSV loading ───────────────────────────────────────────────────────────────

def load_csv(path):
    """
    Parse a CSV into (inserts, updates, csv_stem).

    Each element of inserts/updates is an 8-tuple:
        (common_name, lat, lon, country, mgmt_org, site_type, status, notes)

    Rows with '_action' = UPDATE go to updates; everything else goes to inserts.
    If the '_action' column is absent every row is an insert.
    """
    inserts, updates = [], []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                action = row.get("_action", "INSERT").strip().upper()
                data = (
                    row["common_name"],
                    float(row["lat"]),
                    float(row["lon"]),
                    row["country"],
                    row.get("mgmt_org", ""),
                    row.get("site_type", "Orbital"),
                    row.get("status", "Active"),
                    row.get("notes", ""),
                )
                if action == "UPDATE":
                    updates.append(data)
                else:
                    inserts.append(data)
    except FileNotFoundError:
        print(f"  ERROR: File not found: {path}")
        sys.exit(1)
    except KeyError as e:
        print(f"  ERROR: Missing required column: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"  ERROR: Bad numeric value in CSV: {e}")
        sys.exit(1)

    csv_stem = os.path.splitext(os.path.basename(path))[0]
    return inserts, updates, csv_stem


def build_commit_message(csv_stem, inserts, updates, override=None):
    """
    Auto-generate a commit message from filename + row counts.
    Format:  <csv_stem> | <N> inserts, <M> updates
    Example: launch_sites_v3 | 5 inserts, 15 updates
    """
    if override:
        return override
    parts = []
    if inserts:
        parts.append(f"{len(inserts)} insert{'s' if len(inserts) != 1 else ''}")
    if updates:
        parts.append(f"{len(updates)} update{'s' if len(updates) != 1 else ''}")
    return f"{csv_stem} | {', '.join(parts) or 'no changes'}"


# ── Mode: load ────────────────────────────────────────────────────────────────

def mode_load(args, cursor):
    """
    Create DB/table if needed, apply INSERTs and UPDATEs, show diff, commit.
    Optionally run the branch/merge demo.
    """

    # 1. Read CSV
    section("1. Reading CSV")
    print(f"  File   : {args.csv}")
    inserts, updates, csv_stem = load_csv(args.csv)
    print(f"  INSERTs: {len(inserts)}")
    print(f"  UPDATEs: {len(updates)}")
    print(f"  Total  : {len(inserts) + len(updates)}")

    if len(inserts) + len(updates) == 0:
        print("\n  Nothing to do — CSV contains no rows.")
        return

    # 2. Set up DB and table
    section("2. Database Setup")
    run(cursor, CREATE_DB_SQL,    label="CREATE DATABASE IF NOT EXISTS launch_sites")
    run(cursor, USE_DB_SQL,       label="USE launch_sites")
    run(cursor, CREATE_TABLE_SQL, label="CREATE TABLE IF NOT EXISTS sites")
    print(f"\n  Verifying branch '{args.branch}' ...")
    check_and_set_branch(cursor, args.branch, create_if_missing=args.create_branch)

    # 3. Apply UPDATEs
    if updates:
        section(f"3. Applying {len(updates)} UPDATE(s)")
        for row in updates:
            name   = row[0]
            params = (row[1], row[2], row[3], row[4], row[5], row[6], row[7], name)
            run(cursor, UPDATE_SQL, params=params, label=f"UPDATE  ({name[:55]})")
    else:
        section("3. Updates")
        print("  (no UPDATE rows in this CSV)")

    # 4. Apply INSERTs
    if inserts:
        section(f"4. Applying {len(inserts)} INSERT(s)")
        for row in inserts:
            run(cursor, INSERT_SQL, params=row, label=f"INSERT  ({row[0][:55]})")
    else:
        section("4. Inserts")
        print("  (no INSERT rows in this CSV)")

    # 5. Dolt status
    section("5. Dolt Status — Uncommitted Changes")
    print("  SQL: SELECT * FROM dolt_status;\n")
    status_rows = run(cursor, DOLT_STATUS_SQL, label="dolt_status")
    print_table(status_rows, ["table_name", "staged", "status"])

    # 6. Dolt diff
    section("6. Dolt Diff — Row-Level Changes vs Last Commit")
    print("  SQL: SELECT diff_type, common_name, from_status, to_status, ...")
    print("       FROM dolt_diff_sites WHERE to_commit = 'WORKING';\n")
    try:
        diff_rows = run(cursor, DOLT_DIFF_SQL, label="dolt_diff_sites")
        print_table(diff_rows, ["diff_type", "common_name",
                                "from_status", "to_status",
                                "from_mgmt_org", "to_mgmt_org"])
    except mysql.connector.Error:
        print("  (diff not available — no prior commit exists yet)")

    # 7. Commit
    section("7. Committing")
    if args.no_commit:
        print("  --no-commit flag set — skipping dolt_commit.")
        return

    commit_msg = build_commit_message(csv_stem, inserts, updates, args.message)
    print(f"  Message: '{commit_msg}'\n")
    run(cursor, DOLT_ADD_SQL,    label="dolt_add('-A')")
    run(cursor, DOLT_COMMIT_SQL, params=(commit_msg,), label="dolt_commit")

    # 8. Commit log
    section("8. Dolt Log — Recent Commits")
    print("  SQL: SELECT commit_hash, committer, message, date FROM dolt_log LIMIT 10;\n")
    log_rows = run(cursor, DOLT_LOG_SQL, label="dolt_log")
    print_table(log_rows, ["commit_hash", "committer", "message", "date"])

    # 9. Optional branch demo
    if args.branch_demo:
        _branch_demo(cursor, args.branch)

    # Done
    section("Done")
    print(f"  CSV     : {args.csv}")
    print(f"  Branch  : {args.branch}")
    print(f"  Commit  : {commit_msg}")
    print()
    print("  Verification queries:")
    print("    SELECT * FROM sites ORDER BY country, common_name;")
    print("    SELECT commit_hash, message, date FROM dolt_log;")
    print("    SELECT diff_type, COALESCE(to_common_name, from_common_name),")
    print("           from_status, to_status FROM dolt_diff_sites")
    print("    WHERE  from_commit = hashof('HEAD~1') AND to_commit = hashof('HEAD');")


# ── Mode: restore ─────────────────────────────────────────────────────────────

def mode_restore(args, cursor):
    """
    Demonstrate Dolt recovery:
      1. Show current state
      2. Apply corrupting CSV and show damage
      3. Commit the corruption (unless --dry-run)
      4. Roll back with dolt_reset('--hard', 'HEAD~1')
      5. Verify the restore
    """
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║    Dolt Revision Control — Accidental Update & Restore Demo  ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    if args.dry_run:
        print("\n  ⚠  DRY RUN — damage will be shown but NOT committed\n")

    run(cursor, USE_DB_SQL, label="USE launch_sites")
    print(f"\n  Verifying branch '{args.branch}' ...")
    check_and_set_branch(cursor, args.branch, create_if_missing=args.create_branch)

    # Step 1: Clean state before the accident
    section("STEP 1: Current State Before the Accident")
    total = run(cursor, TOTAL_COUNT_SQL, label="COUNT total rows")
    print(f"\n  Rows in sites table: {total[0][0]}\n")
    log_rows = run(cursor, DOLT_LOG_SQL, label="dolt_log — last 10 commits")
    print()
    print_table(log_rows, ["commit_hash", "committer", "message", "date"])

    # Step 2: Load and apply corrupting CSV
    section("STEP 2: Applying Corrupting CSV (Simulated Bad Bulk Update)")
    print(f"  File: {args.csv}\n")
    _, updates, csv_stem = load_csv(args.csv)

    if not updates:
        print("  ERROR: The accident CSV contains no UPDATE rows.")
        print("         The restore demo requires a CSV with _action = UPDATE rows.")
        sys.exit(1)

    print(f"  {len(updates)} rows to corrupt ...\n")
    for row in updates:
        name   = row[0]
        params = (row[1], row[2], row[3], row[4], row[5], row[6], row[7], name)
        run(cursor, UPDATE_SQL, params=params, label=f"CORRUPT  ({name[:52]})")

    # Step 3: Show damage
    section("STEP 3: Damage Assessment")
    count_rows = run(cursor, DAMAGE_COUNT_SQL, label="COUNT corrupted rows")
    total_rows = run(cursor, TOTAL_COUNT_SQL,  label="COUNT total rows")
    corrupted  = count_rows[0][0]
    total      = total_rows[0][0]
    print(f"\n  ⚠  {corrupted} of {total} rows are corrupted!\n")
    damaged = run(cursor, DAMAGE_CHECK_SQL, label="SELECT corrupted rows")
    print()
    print_table(damaged, ["common_name", "lat", "lon", "country", "status", "notes"])

    # Dry run exits here
    if args.dry_run:
        section("DRY RUN — Stopping Before Commit")
        print("  Damage applied to working set but NOT committed.")
        print("  Nothing is permanently changed.")
        print("  To undo the working-set changes manually:\n")
        print("    CALL dolt_reset('--hard');")
        print("    -- resets working set to HEAD, no commit hash needed\n")
        return

    # Step 4: Commit the corruption
    section("STEP 4: Committing the Corruption  ← This Is the Mistake")
    print("  Simulating an operator who committed without checking the data...\n")
    default_msg = f"{csv_stem} | {len(updates)} corrupting updates — bad bulk overwrite"
    commit_msg  = args.message if args.message else default_msg
    print(f"  Commit message: '{commit_msg}'\n")
    run(cursor, DOLT_ADD_SQL,    label="dolt_add('-A')")
    run(cursor, DOLT_COMMIT_SQL, params=(commit_msg,), label="dolt_commit — bad commit")
    print()
    print("  The bad data is now committed. In a traditional database this")
    print("  would mean the good data is gone. In Dolt, it is one command away.\n")
    log_rows = run(cursor, DOLT_LOG_SQL, label="dolt_log — bad commit now at HEAD")
    print()
    print_table(log_rows, ["commit_hash", "committer", "message", "date"])

    # Step 5: Restore
    section("STEP 5: Restoring to Last Good Commit  ← The Recovery")
    print("  Running:  CALL dolt_reset('--hard', 'HEAD~1');\n")
    print("  HEAD~1 = one commit before current HEAD — the last known-good state.\n")
    run(cursor, DOLT_RESET_SQL, label="dolt_reset('--hard', 'HEAD~1')")

    # Step 6: Verify
    section("STEP 6: Verifying the Restore")
    still_bad = run(cursor, STILL_CORRUPTED_SQL, label="COUNT remaining corrupted rows")
    remaining = still_bad[0][0]
    total_after = run(cursor, TOTAL_COUNT_SQL, label="COUNT total rows after restore")
    print(f"\n  Corrupted rows remaining : {remaining}")
    print(f"  Total rows in table      : {total_after[0][0]}\n")

    if remaining == 0:
        print("  ✓  All rows restored successfully!\n")
    else:
        print("  ✗  Some rows still show corruption — check dolt_log.\n")

    verified = run(cursor, VERIFY_RESTORE_SQL, label="SELECT sample of restored rows")
    print()
    print_table(verified, ["common_name", "lat", "lon", "country", "status"])

    log_rows = run(cursor, DOLT_LOG_SQL, label="dolt_log — bad commit removed from history")
    print()
    print_table(log_rows, ["commit_hash", "committer", "message", "date"])

    # Done
    section("STEP 7: Complete")
    print("  Database restored to its last good state.")
    print()
    print("  Key recovery commands:")
    print()
    print("    CALL dolt_reset('--hard');")
    print("      └─ Undo uncommitted damage (working set → HEAD)")
    print()
    print("    CALL dolt_reset('--hard', 'HEAD~1');")
    print("      └─ Roll back the most recent commit")
    print()
    print("    CALL dolt_reset('--hard', '<commit_hash>');")
    print("      └─ Reset to any specific commit — hash from dolt_log")
    print()
    print("    SELECT * FROM dolt_log;")
    print("      └─ View full commit history with hashes")


# ── Mode: zap ─────────────────────────────────────────────────────────────────

def mode_zap(args, cursor):
    """Drop and recreate the `launch_sites` database.

    This is a destructive operation intended to completely reset the project
    state.

    What it deletes (in `launch_sites`):
      - All table data (e.g., `launch_sites.sites`)
      - All Dolt history for that database (commits / branches / tags)

    What it does NOT delete:
      - Server users / grants (e.g., `dbadmin` in `mysql.user`)
      - Other databases on the server

    Safety:
      - By default the user must type the exact string `ZAP` to proceed.
      - `--force` skips the interactive confirmation (use with care).
    """
    section("ZAP — Delete launch_sites Database (Data + Dolt History)")
    print("  This will permanently remove:")
    print("    - All rows in launch_sites.sites")
    print("    - All commits / branches / tags for the launch_sites database")
    print()

    if not args.force:
        confirm = input("  Type ZAP to continue: ").strip()
        if confirm != "ZAP":
            print("\n  Aborted — no changes made.")
            return

    run(cursor, "DROP DATABASE IF EXISTS launch_sites;",
        label="DROP DATABASE IF EXISTS launch_sites")
    run(cursor, CREATE_DB_SQL, label="CREATE DATABASE IF NOT EXISTS launch_sites")
    run(cursor, USE_DB_SQL, label="USE launch_sites")
    run(cursor, CREATE_TABLE_SQL, label="CREATE TABLE IF NOT EXISTS sites")

    section("ZAP Complete")
    print("  Database launch_sites has been recreated with a fresh history.")
    print("  Next steps:")
    print("    SELECT active_branch();")
    print("    SELECT * FROM dolt_log;")


# ── Branch demo (shared) ──────────────────────────────────────────────────────

def _branch_demo(cursor, base_branch):
    """Create a demo branch, commit a change, merge back to base_branch."""
    section("Branch Demo — Make a Change on a Branch, Then Merge")
    demo_branch = "status-corrections"

    # Clean up if branch already exists from a prior run
    cursor.execute(
        f"SELECT COUNT(*) FROM dolt_branches WHERE name = '{demo_branch}';"
    )
    (exists,) = cursor.fetchone()
    try:
        cursor.fetchall()
    except Exception:
        pass

    if exists:
        print(f"  Branch '{demo_branch}' already exists — removing for clean demo ...")
        run(cursor, f"CALL dolt_branch('-d', '{demo_branch}');",
            label=f"dolt_branch('-d', '{demo_branch}')")

    print(f"\n  Creating branch '{demo_branch}' ...")
    run(cursor, f"CALL dolt_branch('{demo_branch}');",
        label=f"dolt_branch('{demo_branch}')")

    print(f"\n  Checking out '{demo_branch}' ...")
    run(cursor, CHECKOUT_SQL, params=(demo_branch,),
        label=f"dolt_checkout('{demo_branch}')")

    print("\n  Updating Vandenberg SLC-6 status → 'Under Review' on the branch ...")
    run(cursor,
        "UPDATE sites SET status = 'Under Review' WHERE common_name = 'Vandenberg SFB SLC-6';",
        label="UPDATE Vandenberg SFB SLC-6 status")

    print("\n  Committing on the branch ...")
    run(cursor, DOLT_ADD_SQL, label="dolt_add('-A')")
    run(cursor, DOLT_COMMIT_SQL,
        params=(f"{demo_branch} | mark Vandenberg SLC-6 as Under Review",),
        label=f"dolt_commit on '{demo_branch}'")

    print(f"\n  Switching back to '{base_branch}' ...")
    run(cursor, CHECKOUT_SQL, params=(base_branch,),
        label=f"dolt_checkout('{base_branch}')")

    print(f"\n  Merging '{demo_branch}' into '{base_branch}' ...")
    run(cursor, f"CALL dolt_merge('{demo_branch}');",
        label=f"dolt_merge('{demo_branch}')")

    # Fast-forward merges don't leave anything to commit
    status_rows = run(cursor, DOLT_STATUS_SQL, label="dolt_status after merge")
    if status_rows:
        print("  Staged changes found — committing the merge ...")
        run(cursor, DOLT_ADD_SQL, label="dolt_add('-A')")
        run(cursor, DOLT_COMMIT_SQL,
            params=(f"Merge '{demo_branch}' into '{base_branch}'",),
            label="dolt_commit — merge")
    else:
        print("  Fast-forward merge complete — no separate merge commit needed.")

    print("\n  Commit log after merge:")
    rows = run(cursor, DOLT_LOG_SQL, label="dolt_log")
    print_table(rows, ["commit_hash", "committer", "message", "date"])


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    """
    dolt_manage.py
    --------------
    Single script for all launch sites database operations against a running
    Dolt SQL server.

    Modes
    -----
      load    (default)
              Creates the database and table if they do not exist, then applies
              all rows from the CSV.  Rows without an '_action' column are treated
              as INSERTs.  Rows with '_action' = UPDATE are applied as UPDATEs
              matched on common_name.
              Commit message is auto-generated from the filename and row counts;
              override with --message.

      restore
              Demonstration of Dolt revision-control recovery.
              Loads a corrupting CSV (all UPDATEs), shows the damage, commits it
              (simulating an operator who didn't notice), then rolls back with
              CALL dolt_reset('--hard', 'HEAD~1') and verifies the restore.
              Add --dry-run to see the damage without committing.

    Usage
    -----
      python3 dolt_manage.py --csv launch_sites_initial.csv --host SERVER_IP --user dbadmin
      python3 dolt_manage.py --csv launch_sites_v3.csv      --host SERVER_IP --user dbadmin
      python3 dolt_manage.py --csv launch_sites_v4.csv      --host SERVER_IP --user dbadmin --branch staging
      python3 dolt_manage.py --csv launch_sites_v2.csv      --host SERVER_IP --user dbadmin --branch-demo
      python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin --mode restore
      python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin --mode restore --dry-run

    Options
    -------
      --host        Dolt server IP or hostname         (default: 127.0.0.1)
      --port        Dolt server port                   (default: 3306)
      --user        Database username                  (default: dbadmin)
      --password    Database password                  (prompted if omitted)
      --csv         Path to the CSV file               (default: launch_sites_initial.csv)
      --branch      Dolt branch to operate on          (default: main)
      --message     Override the auto-generated commit message
      --mode        load | restore                     (default: load)
      --no-commit   Apply changes but skip dolt_commit (load mode only)
      --branch-demo Run the branch/merge demo          (load mode only)
      --dry-run     Show damage without committing     (restore mode only)
    """

    # Warn about flags used in wrong mode
    if args.mode == "restore" and args.no_commit:
        print("  Note: --no-commit is ignored in restore mode.")
    if args.mode == "restore" and args.branch_demo:
        print("  Note: --branch-demo is ignored in restore mode.")
    if args.mode == "load" and args.dry_run:
        print("  Note: --dry-run is ignored in load mode.")

    password = args.password or getpass.getpass(f"Password for {args.user}: ")

    conn   = connect(args.host, args.port, args.user, password)
    cursor = conn.cursor()

    try:
        if args.zap:
            mode_zap(args, cursor)
            return
        if args.mode == "load":
            mode_load(args, cursor)
        else:
            mode_restore(args, cursor)
    finally:
        cursor.close()
        conn.close()


# Standard call to the main() function.
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog="dolt_manage.py",
        description="Manage the launch_sites Dolt database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--host",        default="127.0.0.1",
                        help="Dolt server IP or hostname (default: 127.0.0.1)")
    parser.add_argument("--port",        default=3306, type=int,
                        help="Dolt server port (default: 3306)")
    parser.add_argument("--user",        default="dbadmin",
                        help="Database username (default: dbadmin)")
    parser.add_argument("--password",    default=None,
                        help="Database password (prompted if omitted)")
    parser.add_argument("--csv",         default="launch_sites_initial.csv",
                        help="Path to CSV file (default: launch_sites_initial.csv)")
    parser.add_argument("--branch",      default="main",
                        help="Dolt branch to operate on (default: main)")
    parser.add_argument("--create-branch", action="store_true",
                        help="Create --branch if it does not exist")
    parser.add_argument("--zap", action="store_true",
                        help="DANGER: drop+recreate launch_sites DB (deletes all data and Dolt history)")
    parser.add_argument("--force", action="store_true",
                        help="Skip interactive confirmation for dangerous operations (use with --zap)")
    parser.add_argument("--message",     default=None,
                        help="Override the auto-generated commit message")
    parser.add_argument("--mode",        default="load",
                        choices=["load", "restore"],
                        help="Operation mode: load (default) or restore")
    parser.add_argument("--no-commit",   action="store_true",
                        help="[load] Apply rows but skip dolt_commit")
    parser.add_argument("--branch-demo", action="store_true",
                        help="[load] Run branch/merge demo after committing")
    parser.add_argument("--dry-run",     action="store_true",
                        help="[restore] Show damage without committing it")
    args = parser.parse_args()
    main()
