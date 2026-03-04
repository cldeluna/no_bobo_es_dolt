# Launch Sites Database — Setup, Update, and Restore Guide
### Using dolt_manage.py with uv and Dolt Revision Control

---

## Table of Contents

1. [File Overview](#1-file-overview)
2. [What is uv?](#2-what-is-uv)
3. [Installing uv](#3-installing-uv)
4. [Setting Up the Project Environment](#4-setting-up-the-project-environment)
5. [dolt_manage.py — Reference](#5-dolt_managepy--reference)
   - [Options](#options)
   - [Modes](#modes)
   - [Auto-Generated Commit Messages](#auto-generated-commit-messages)
   - [CSV Column Format](#csv-column-format)
6. [Walkthrough — Full Sequence](#6-walkthrough--full-sequence)
   - [Step 1 — Initial Load](#step-1--initial-load)
   - [Step 2 — Apply v2 Updates](#step-2--apply-v2-updates)
   - [Step 3 — Apply v3 Acronym Expansions](#step-3--apply-v3-acronym-expansions)
   - [Step 4 — Apply v4 Full Expansions with Abbreviations](#step-4--apply-v4-full-expansions-with-abbreviations)
   - [Step 5 — Simulate and Recover from Accidental Corruption](#step-5--simulate-and-recover-from-accidental-corruption)
7. [Dolt Revision Control — Query Reference](#7-dolt-revision-control--query-reference)
8. [Command Summary](#8-command-summary)
9. [Git Equivalent Commands](#9-Dolt Git Command Equivalents)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. File Overview

| File | Type | Purpose |
|---|---|---|
| `launch_sites_initial.csv` | CSV | 13 seed records — initial world launch sites (Don't load this file if you entered the intial data manually!) |
| `launch_sites_v2.csv` | CSV | 4 updates + 6 new sites — status changes and additions |
| `launch_sites_v3.csv` | CSV | 15 updates + 5 new sites — acronym expansions (first pass) |
| `launch_sites_v4.csv` | CSV | 22 updates + 7 new sites — full names with acronyms in parentheses |
| `launch_sites_v5_accident.csv` | CSV | 13 corrupting updates — simulates a bad bulk overwrite |
| `launch_sites_abandoned.csv` | CSV | 1 new site — abandoned site to test branching workflow |
| `dolt_manage.py` | Python | **Single script** — creates DB/table, loads any CSV, and runs the restore demo |

> **One script handles everything.** The `dolt_manage.py` script works for the initial load, all incremental updates, branching example, and the corruption/restore demo .

---

## 2. What is uv?

**uv** is a modern Python package and project manager — think of it like `pip`, `pyenv`, and `venv` combined into one fast tool. It handles:

- Creating isolated virtual environments (so packages don't conflict between projects)
- Installing Python packages
- Running scripts with dependencies automatically resolved
- Managing different versions of Python

For a deeper dive see [Ultra Valuable uv for Dynamic, On-Demand Python Virtual Environments](https://gratuitous-arp.net/dynamic-on-demand-python-venv-or-virtual-environments/)

> uv is not required — you can use plain `pip` and `python3` if you prefer. Both approaches are shown throughout this guide.

---

## 3. Installing uv

### macOS

```bash
brew install uv
```

Or without Homebrew:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Add uv to your PATH (if the installer doesn't do it automatically):
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Windows

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Verify the installation

```bash
uv --version
```

Expected output: `uv 0.10.x`

---

## 4. Setting Up the Project Environment

All scripts and CSV files should be in the same directory. Create a project folder and copy the files there:

```bash
mkdir ~/dolt-scripts 
cd ~/dolt-scripts
# Clone or download the repo and unzip 
git clone https://github.com/cldeluna/no_bobo_es_dolt.git
# Move into the repository directory
cd no_bobo_es_dolt
# Using `uv run` just to view the --help options will create your python environment
uv run python3 dolt_manage.py --help
```

### Option A — Using uv (Recommended)

uv creates an isolated environment and installs the MySQL driver automatically.

```bash
cd ~/dolt-scripts

# Create a virtual environment
uv venv

# Install the MySQL connector
uv pip install mysql-connector-python

# Add the MySQL connector 
uv add mysql-connector-python

# Activate the environment
# macOS / Linux:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

Once activated, your prompt will show `(.venv)`. All `python3` commands below use the isolated environment.

To deactivate when done:
```bash
deactivate
```

### Option B — Using plain pip

```bash
pip install mysql-connector-python
```

> If you get a permissions error on Linux, use: `pip install --user mysql-connector-python`

### Verify the connector is installed

```bash
python3 -c "import mysql.connector; print('mysql-connector-python OK')"
```

---

## 5. dolt_manage.py — Reference

### Options

```
$ uv run python3 dolt_manage.py --help
usage: dolt_manage.py [-h] [--host HOST] [--port PORT] [--user USER] [--password PASSWORD] [--csv CSV] [--branch BRANCH] [--create-branch] [--zap]
                      [--force] [--message MESSAGE] [--mode {load,restore}] [--no-commit] [--branch-demo] [--dry-run]

Manage the launch_sites Dolt database.

options:
  -h, --help            show this help message and exit
  --host HOST           Dolt server IP or hostname (default: 127.0.0.1)
  --port PORT           Dolt server port (default: 3306)
  --user USER           Database username (default: dbadmin)
  --password PASSWORD   Database password (prompted if omitted)
  --csv CSV             Path to CSV file (default: launch_sites_initial.csv)
  --branch BRANCH       Dolt branch to operate on (default: main)
  --create-branch       Create --branch if it does not exist
  --zap                 DANGER: drop+recreate launch_sites DB (deletes all data and Dolt history)
  --force               Skip interactive confirmation for dangerous operations (use with --zap)
  --message MESSAGE     Override the auto-generated commit message
  --mode {load,restore}
                        Operation mode: load (default) or restore
  --no-commit           [load] Apply rows but skip dolt_commit
  --branch-demo         [load] Run branch/merge demo after committing
  --dry-run             [restore] Show damage without committing it
```

### Modes

**`--mode load`** (default)

Creates the `launch_sites` database and `sites` table if they do not already exist, then applies all rows from the CSV. This is safe to run against a server that already has the database — `CREATE DATABASE IF NOT EXISTS` and `CREATE TABLE IF NOT EXISTS` are used throughout. Rows without an `_action` column are treated as INSERTs. Rows with `_action = UPDATE` are applied as UPDATEs matched on `common_name`. After applying changes, shows `dolt_status`, `dolt_diff`, and commits. Optionally runs the branch/merge demo with `--branch-demo`.

**`--mode restore`**

Demonstration of Dolt's recovery capabilities. Loads the accident CSV, shows the damage in detail, then commits it to simulate an operator who didn't notice the problem before pushing. Rolls back with `CALL dolt_reset('--hard', 'HEAD~1')` and verifies all rows are restored. Add `--dry-run` to see the damage without committing it — nothing is permanently changed in that case.

### Auto-Generated Commit Messages

The commit message is built automatically from the CSV filename and the number of inserts and updates. You never need to specify a message manually unless you want to override the default.

| CSV loaded | Auto-generated commit message |
|---|---|
| `launch_sites_initial.csv` | `launch_sites_initial \| 13 inserts` |
| `launch_sites_v2.csv` | `launch_sites_v2 \| 6 inserts, 4 updates` |
| `launch_sites_v3.csv` | `launch_sites_v3 \| 5 inserts, 15 updates` |
| `launch_sites_v4.csv` | `launch_sites_v4 \| 7 inserts, 22 updates` |
| `launch_sites_v5_accident.csv` | `launch_sites_v5_accident \| 13 corrupting updates — bad bulk overwrite` |
| `launch_sites_abandoned.csv` | 1 new site — abandoned site to test branching workflow |

Override with `--message "your text"` when you want something more descriptive.

### CSV Column Format

Any CSV used with `dolt_manage.py` must have these columns. The `_action` column is optional for initial loads where every row is a new insert.

| Column | Required | Notes |
|---|---|---|
| `common_name` | Yes | Must match an existing row exactly for UPDATE |
| `lat` | Yes | Decimal degrees, e.g. `28.608389` |
| `lon` | Yes | Decimal degrees, e.g. `-80.604333` |
| `country` | Yes | Full country name |
| `mgmt_org` | No | Managing organization — defaults to empty string |
| `site_type` | No | `Orbital`, `Suborbital`, etc. — defaults to `Orbital` |
| `status` | No | `Active`, `Inactive`, `Under Construction` — defaults to `Active` |
| `notes` | No | Free text — defaults to empty string |
| `_action` | No | `INSERT` or `UPDATE` — rows without this column default to `INSERT` |

---

## 6. Walkthrough — Full Sequence

Make sure your Dolt server is running before executing the script:

```bash
cd ~/dolt/dolt-data
dolt sql-server --config config.yml
```

In a separate terminal (local or remote), navigate to your scripts directory:

```bash
cd ~/dolt-scripts
source .venv/bin/activate   # if using traditional python venv
```

---

### Step 1 — Initial Load

Load the 13 seed records, create the database and table, and make the first commit.

```bash
uv run python3 dolt_manage.py --csv launch_sites_initial.csv --host 127.0.0.1 --user dbadmin
```

Auto-generated commit message: `launch_sites_initial | 13 inserts`

With a custom message:
```bash
uv run python3 dolt_manage.py --csv launch_sites_initial.csv --host SERVER_IP --user dbadmin \
  --message "Sprint 1: initial 13 launch site seed records"
```

**What happens:**
- Creates database `launch_sites` if it does not exist
- Creates table `sites` with the full schema
- Inserts 13 rows
- Shows `dolt_status` and `dolt_diff`
- Commits — this is commit #1 in your history

**Verify in your SQL client:**

```sql
USE launch_sites;
SELECT * FROM sites;
SELECT * FROM dolt_log;
```

---

### Step 2 — Apply v2 Updates

4 status/notes updates and 6 new sites. Optionally includes the branch/merge demo.

```bash
uv run python3 dolt_manage.py --csv launch_sites_v2.csv --host 127.0.0.1 --user dbadmin
```

Auto-generated commit message: `launch_sites_v2 | 6 inserts, 4 updates`

With the branch/merge demo:
```bash
uv run python3 dolt_manage.py --csv launch_sites_v2.csv --host SERVER_IP --user dbadmin 
```

**What happens:**
- Updates Baikonur (status → Inactive), Starbase (notes), Plesetsk (org), Jiuquan (notes)
- Inserts 6 new sites including Vostochny, Naro, and Alcantara
- Shows `dolt_status` and `dolt_diff_sites` before committing
- Commits — this is commit #2

---

### Step 3 — Apply v3 Acronym Expansions (First Pass)

Expands abbreviations like `NASA`, `ESA`, `JAXA` to their full names. Adds 5 new sites.

```bash
uv run python3 dolt_manage.py --csv launch_sites_v3.csv --host SERVER_IP --user dbadmin \
   --branch-demo
```

Auto-generated commit message: `launch_sites_v3 | 5 inserts, 15 updates`

**What happens:**
- 15 UPDATEs — `mgmt_org` values rewritten with full organization names
- 5 INSERTs — new sites including Wallops, Xichang, and Andoya
- Commits — this is commit #3
- If `--branch-demo` is set: creates `status-corrections` branch, makes a change on it, merges back to `main`

---

### Step 4 — Apply v4 Full Expansions with Abbreviations in Parentheses

Adds the acronym in parentheses after the full name, e.g. `National Aeronautics and Space Administration (NASA)`. Adds 7 more new sites.

```bash
uv run python3 dolt_manage.py --csv launch_sites_v4.csv --host SERVER_IP --user dbadmin
```

Auto-generated commit message: `launch_sites_v4 | 7 inserts, 22 updates`

**What happens:**
- 22 UPDATEs — all `mgmt_org` values reformatted as `Full Name (ACRONYM)`
- 7 INSERTs — additional sites including Pacific Spaceport Complex and Hainan
- Commits — this is commit #4

**Verify the full table after all four loads:**
```sql
SELECT common_name, country, mgmt_org, status
FROM   sites
ORDER  BY country, common_name;
```

---

### Step 5 — Simulate and Recover from Accidental Corruption

This step deliberately corrupts 13 rows by overwriting them with `UNKNOWN` values and zeroed coordinates — exactly what happens when a bulk UPDATE runs without a WHERE clause. Dolt then recovers the database in a single command.

#### Run the full demo

```bash
uv run python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin \
  --mode restore
```

Auto-generated commit message: `launch_sites_v5_accident | 13 corrupting updates — bad bulk overwrite`

**What the script does, step by step:**

1. Shows the current clean state and commit log
2. Applies the corrupting CSV — 13 rows overwritten with `lat=0, lon=0, country=UNKNOWN`
3. Shows the damage clearly — how many rows are broken and what they look like
4. **Commits the corruption** — simulates an operator who didn't notice before pushing
5. Shows the commit log with the bad commit visible at HEAD
6. Runs `CALL dolt_reset('--hard', 'HEAD~1')` — rolls back one commit
7. Verifies all rows are restored and the bad commit is gone from history
8. Prints the final clean commit log and a recovery command reference

#### Dry run — see the damage without committing

Use `--dry-run` to apply the corruption to the working set but stop before the commit. Nothing is permanently changed:

```bash
uv run python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin \
  --mode restore --dry-run
```

After a dry run, restore the working set manually:
```sql
CALL dolt_reset('--hard');
```

If you want to be a little more destructive:

commit the destruction with a custom commit message!

```python
uv run python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host 127.0.0.1 --user dbadmin --password SecurePass456! --mode load --message "DESTRUCTIVE DEMO: bulk UPDATE without WHERE clause - accidental overwrite of records"
```

Look at the data. Notice the zero and uknown values:    |  0.000000 |    0.000000 | UNKNOWN              | UNKNOWN
```sql
SELECT * FROM sites ORDER BY country, common_name;
```

Look at the commit log and notice the "DESTRUCTIVE DEMO" message.

```sql
SELECT * FROM dolt_log;
```

In this case, we can't go back one commit because that is the one with bad data.  We need to go back to the commit before that.

```sql
CALL dolt_reset('--hard', '<commit_hash>');
```

You should know be on the last good known version of the databse.

---

## 7. Dolt Revision Control — Query Reference

These SQL commands can be run from any connected SQL client after loading data.

### View commit history

```sql
SELECT commit_hash, committer, message, date
FROM   dolt_log
ORDER  BY date DESC;
```

### See what changed in the working set (not yet committed)

```sql
SELECT * FROM dolt_status;
```

### See row-level diff between working set and HEAD

```sql
SELECT diff_type,
       COALESCE(to_common_name, from_common_name) AS common_name,
       from_status,   to_status,
       from_mgmt_org, to_mgmt_org
FROM   dolt_diff_sites
WHERE  to_commit = 'WORKING';
```

### See row-level diff between two specific commits

```sql
-- Get hashes from dolt_log first, then:
SELECT diff_type,
       COALESCE(to_common_name, from_common_name) AS common_name,
       from_mgmt_org, to_mgmt_org
FROM   dolt_diff_sites
WHERE  from_commit = '<older_hash>'
AND    to_commit   = '<newer_hash>';
```

### Restore working set to HEAD (damage NOT yet committed)

```sql
CALL dolt_reset('--hard');
```

### Roll back one commit (damage WAS committed)

```sql
CALL dolt_reset('--hard', 'HEAD~1');
```

### Roll back to any specific commit

```sql
-- Get the hash from dolt_log
CALL dolt_reset('--hard', 'abc1234def56...');
```

### Create and use a branch

```sql
CALL dolt_branch('my-branch');
CALL dolt_checkout('my-branch');
-- make changes and commit on the branch --
CALL dolt_checkout('main');
CALL dolt_merge('my-branch');
CALL dolt_add('-A');
CALL dolt_commit('-m', 'Merged my-branch into main');
```

### Stage and commit manually

```sql
CALL dolt_add('-A');
CALL dolt_commit('-m', 'Your descriptive commit message here');
```

### Check the currently active branch

```sql
SELECT active_branch();
```

---

## 8. Command Summary

### Environment setup

```bash
# Install uv
brew install uv                                    # macOS
curl -LsSf https://astral.sh/uv/install.sh | sh   # Linux

# Create project folder and environment
mkdir ~/dolt-scripts && cd ~/dolt-scripts
uv venv
uv pip install mysql-connector-python
source .venv/bin/activate               # macOS / Linux
.venv\Scripts\Activate.ps1              # Windows PowerShell
```

### Start the Dolt server

```bash
cd ~/dolt/dolt-data
dolt sql-server --config config.yml
```

### Full load sequence — all using dolt_manage.py

```bash
# 1. Initial load — creates DB, table, 13 rows, auto commit message
python3 dolt_manage.py --csv launch_sites_initial.csv --host SERVER_IP --user dbadmin

# 2. v2 — 4 updates, 6 new sites
python3 dolt_manage.py --csv launch_sites_v2.csv --host SERVER_IP --user dbadmin

# 2a. With branch/merge demo
python3 dolt_manage.py --csv launch_sites_v2.csv --host SERVER_IP --user dbadmin \
  --branch-demo

# 3. v3 — 15 org name expansions, 5 new sites
python3 dolt_manage.py --csv launch_sites_v3.csv --host SERVER_IP --user dbadmin

# 4. v4 — 22 Full Name (ACRONYM) reformats, 7 new sites
python3 dolt_manage.py --csv launch_sites_v4.csv --host SERVER_IP --user dbadmin

# 5. Accidental corruption + restore demo
python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin \
  --mode restore

# 5a. Dry run — see damage without committing
python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin \
  --mode restore --dry-run
```

### Common flag combinations

```bash
# Custom branch
python3 dolt_manage.py --csv launch_sites_v4.csv --host SERVER_IP --user dbadmin \
  --branch staging

# Custom commit message
python3 dolt_manage.py --csv launch_sites_v4.csv --host SERVER_IP --user dbadmin \
  --message "Q2 review: Full Name (ACRONYM) format + 7 new sites"

# Apply without committing (inspect first)
python3 dolt_manage.py --csv launch_sites_v3.csv --host SERVER_IP --user dbadmin \
  --no-commit

# Restore demo with custom label for the bad commit
python3 dolt_manage.py --csv launch_sites_v5_accident.csv --host SERVER_IP --user dbadmin \
  --mode restore --message "Demo: bulk UPDATE without WHERE — training session"
```

### Dolt recovery commands (SQL)

```sql
-- Check what is uncommitted
SELECT * FROM dolt_status;

-- Check which branch is active
SELECT active_branch();

-- View commit history
SELECT commit_hash, committer, message, date FROM dolt_log;

-- Restore uncommitted damage (working set → HEAD)
CALL dolt_reset('--hard');

-- Roll back the last commit
CALL dolt_reset('--hard', 'HEAD~1');

-- Roll back to a specific commit
CALL dolt_reset('--hard', '<commit_hash>');
```

### Connect to Dolt from CLI

```bash
# macOS / Linux
mysql -h SERVER_IP -P 3306 -u dbadmin -p

# Verify server is listening — macOS
lsof -nP -iTCP:3306 -sTCP:LISTEN

# Verify server is listening — Linux
ss -tlnp | grep 3306
```

---



## 9. Dolt Git Command Equivalents

Dolt implements Git-style version control entirely through SQL.

Every Git operation you already know has a direct SQL equivalent executed from any MySQL-compatible client or the `dolt sql` shell.

---

## Command Equivalents

| Git Command                  | Dolt SQL Equivalent                                          | Notes                                                        |
| ---------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `git status`                 | `SELECT * FROM dolt_status;`                                 | Shows staged and unstaged changes in the working set         |
| `git add -A`                 | `CALL dolt_add('-A');`                                       | Stages all changed tables                                    |
| `git add <table>`            | `CALL dolt_add('sites');`                                    | Stages a single table                                        |
| `git reset HEAD <table>`     | `CALL dolt_reset('sites');`                                  | Unstages a table (leaves working set intact)                 |
| `git commit -m "msg"`        | `CALL dolt_commit('-m', 'msg');`                             | Commits staged changes with a message                        |
| `git commit -am "msg"`       | `CALL dolt_commit('-Am', 'msg');`                            | Stages all and commits in one step                           |
| `git log`                    | `SELECT * FROM dolt_log;`                                    | Full commit history — hash, author, message, date            |
| `git log --oneline`          | `SELECT commit_hash, message FROM dolt_log;`                 | Compact commit history                                       |
| `git diff`                   | `SELECT * FROM dolt_diff_sites WHERE commit_hash = 'WORKING';` | Row-level diff of working set vs HEAD — one view per table   |
| `git diff HEAD~1 HEAD`       | `SELECT * FROM dolt_diff_sites WHERE from_commit = 'HEAD~1' AND to_commit = 'HEAD';` | Diff between two commits                                     |
| `git diff <hash1> <hash2>`   | `SELECT * FROM dolt_diff_sites WHERE from_commit = '<hash1>' AND to_commit = '<hash2>';` | Diff between any two specific commits                        |
| `git stash`                  | `CALL dolt_stash();`                                         | Saves the working set and reverts to HEAD                    |
| `git stash list`             | `SELECT * FROM dolt_stashes;`                                | Lists all saved stashes                                      |
| `git stash pop`              | `CALL dolt_stash_pop();`                                     | Applies the most recent stash and removes it                 |
| `git stash drop`             | `CALL dolt_stash_drop(0);`                                   | Drops a stash by index without applying it                   |
| `git checkout -- .`          | `CALL dolt_checkout('--', '.');`                             | Discards all unstaged working set changes                    |
| `git reset --hard`           | `CALL dolt_reset('--hard');`                                 | Resets working set and staged changes to HEAD — **does not remove commits** |
| `git reset --hard HEAD~1`    | `CALL dolt_reset('--hard', 'HEAD~1');`                       | Rolls back the last commit — working set reverts to that state |
| `git reset --hard <hash>`    | `CALL dolt_reset('--hard', '<hash>');`                       | Resets to any specific commit by hash                        |
| `git revert <hash>`          | `CALL dolt_revert('<hash>');`                                | Creates a new commit that undoes a prior commit — history preserved |
| `git branch`                 | `SELECT * FROM dolt_branches;`                               | Lists all branches                                           |
| `git branch <name>`          | `CALL dolt_branch('<name>');`                                | Creates a new branch at current HEAD                         |
| `git checkout <branch>`      | `CALL dolt_checkout('<branch>');`                            | Switches to an existing branch                               |
| `git checkout -b <name>`     | `CALL dolt_checkout('-b', '<name>');`                        | Creates and switches to a new branch in one step             |
| `git branch -d <name>`       | `CALL dolt_branch('-d', '<name>');`                          | Deletes a branch                                             |
| `git merge <branch>`         | `CALL dolt_merge('<branch>');`                               | Merges a branch into the current branch                      |
| `git merge --abort`          | `CALL dolt_merge('--abort');`                                | Aborts a merge in progress                                   |
| `git cherry-pick <hash>`     | `CALL dolt_cherry_pick('<hash>');`                           | Applies a single commit from another branch                  |
| `git tag <name>`             | `CALL dolt_tag('<name>');`                                   | Creates a lightweight tag at current HEAD                    |
| `git tag -a <name> -m "msg"` | `CALL dolt_tag('<name>', '-m', 'msg');`                      | Creates an annotated tag with a message                      |
| `git tag`                    | `SELECT * FROM dolt_tags;`                                   | Lists all tags                                               |
| `git show <hash>`            | `SELECT * FROM dolt_log WHERE commit_hash = '<hash>';`       | Shows metadata for a specific commit                         |
| `git blame <file>`           | `SELECT * FROM dolt_blame_sites;`                            | Shows which commit last modified each row — one view per table |
| `git remote add`             | `CALL dolt_remote('add', 'origin', '<url>');`                | Adds a remote (DoltHub or self-hosted)                       |
| `git remote -v`              | `SELECT * FROM dolt_remotes;`                                | Lists configured remotes                                     |
| `git push origin main`       | `CALL dolt_push('origin', 'main');`                          | Pushes commits to a remote                                   |
| `git pull`                   | `CALL dolt_pull('origin');`                                  | Fetches and merges from the default remote                   |
| `git fetch`                  | `CALL dolt_fetch('origin');`                                 | Fetches from remote without merging                          |
| `git clone <url>`            | `dolt clone <url>` *(shell command)*                         | Clones a Dolt database — run in terminal, not SQL            |

---

## Reading a Diff Result

Unlike `git diff` which shows line changes in a text file, `dolt_diff_<table>`
returns **one row per changed database row**, with `from_` and `to_` columns
for every field:

```sql
SELECT diff_type,       -- 'added', 'removed', or 'modified'
       common_name,
       from_status,     -- value BEFORE the change
       to_status,       -- value AFTER the change
       from_mgmt_org,
       to_mgmt_org
FROM   dolt_diff_sites
WHERE  commit_hash = 'WORKING';
```

`diff_type` values:

| diff_type  | Meaning                                            |
| ---------- | -------------------------------------------------- |
| `added`    | Row was inserted                                   |
| `removed`  | Row was deleted                                    |
| `modified` | Row existed before and after — some fields changed |

---

## Typical Workflow

```sql
-- 1. Make changes via INSERT / UPDATE / DELETE

-- 2. Check what changed
SELECT * FROM dolt_status;

-- 3. Review the row-level diff
SELECT diff_type, common_name, from_status, to_status
FROM   dolt_diff_sites
WHERE  commit_hash = 'WORKING';

-- 4. Stage and commit
CALL dolt_add('-A');
CALL dolt_commit('-m', 'Describe what you changed and why');

-- 5. Verify history
SELECT commit_hash, message, date FROM dolt_log;
```

---

## Branch Workflow

```sql
-- Selecte the Database to use for your actions
USE launch_sites;

-- Create (-b) and switch to a new branch
CALL dolt_checkout('-b', 'abandoned');

-- Show active branch
SELECT active_branch();

-- Show branches (just the name)
SELECT name FROM dolt_branches;

-- Show the current DB
SELECT common_name, country FROM sites;

-- Make changes and commit on the branch
# INSERT INTO sites (...) VALUES (...);

# https://www.cia.gov/readingroom/docs/CIA-RDP78T05439A000300300009-0.pdf
INSERT INTO sites (
    common_name,
    lat,
    lon,
    country,
    mgmt_org,
    site_type,
    status,
    notes
) VALUES (
    'Hammaguir Launch Site',
    30.778056,
    -3.055278,
    'Algeria',
    'French Special Weapons Test Centre (CIEES)',
    'Rocket range',
    'Inactive',
    'Former French missile and sounding rocket test range near Hammaguir used for launches including the Diamant orbital rocket from 1947–1967; abandoned after French withdrawal from Algeria under the Évian Accords.'
);

-- Show the updated DB
SELECT common_name, country FROM sites;

-- Go back to the main branch and view the records...notice what is missing?
CALL dolt_checkout('main');

-- Lets go back to the new abandoned branch
CALL dolt_checkout('abandoned');

-- We are going to add (-A) and commit (-m) our chagnes
CALL dolt_add('-A');
CALL dolt_commit('-m', 'Added abandoned Algeria site to branch');

-- Switch back to main and merge
CALL dolt_checkout('main');

-- Without conflicts the dolt_merge will commit
CALL dolt_merge('abandoned');

-- With colflicts you will have clean up to do and you will likely have to commit manually
-- You should not need these two commands with this workflow
CALL dolt_add('-A');
CALL dolt_commit('-m', 'Merge abandoned into main');

-- Lets look at all the branches we have
SELECT * FROM dolt_branches;

-- Delte the abandoned branch since we have merged into main
CALL dolt_branch('-d', 'abandoned');

-- Lets look at all the branches we have
SELECT * FROM dolt_branches;

-- Look at the commits
SELECT commit_hash, message, date FROM dolt_log;

```

---

## Key Differences from Git

| Aspect              | Git             | Dolt                                                         |
| ------------------- | --------------- | ------------------------------------------------------------ |
| What is versioned   | Text files      | Database rows                                                |
| Diff unit           | Lines in a file | Rows in a table                                              |
| Working with data   | Text editor     | SQL (`INSERT`, `UPDATE`, `DELETE`)                           |
| Client              | `git` CLI       | Any MySQL client or `dolt sql` shell                         |
| `git clone`         | Shell command   | Shell command (`dolt clone`) — not SQL                       |
| Autocommit          | N/A             | Set `autocommit: true` in config — SQL changes save immediately but are **not** Dolt-committed until you call `dolt_commit()` |
| Conflict resolution | Edit text files | SQL UPDATE on the conflicting rows in `dolt_conflicts_<table>` |

---

*Dolt SQL function reference: https://docs.dolthub.com/sql-reference/version-control/dolt-sql-procedures*
*Dolt system tables reference: https://docs.dolthub.com/sql-reference/version-control/dolt-system-tables*

---

## 10. Troubleshooting

### "No module named mysql.connector"

The MySQL connector is not installed in the active environment:
```bash
uv pip install mysql-connector-python
# or
pip install mysql-connector-python
```

### "Can't connect to MySQL server"

- Verify Dolt is running: `pgrep -a dolt`
- Verify the correct `--host` is being passed (use the server's actual IP, not `localhost`, for remote connections)
- Verify port 3306 is open: `lsof -nP -iTCP:3306 -sTCP:LISTEN` (macOS) or `ss -tlnp | grep 3306` (Linux)

### "Access denied for user"

- Verify the username and password match what was configured during Dolt server setup
- Verify the user was created with `'%'` as the host wildcard (not `'localhost'`)

### "Table 'launch_sites.sites' doesn't exist"

This should not happen with `dolt_manage.py` — the script always runs `CREATE TABLE IF NOT EXISTS` before any inserts or updates. If you see this error, verify the `USE launch_sites` step completed without error and that the connection is reaching the correct Dolt instance.

### Script committed to the wrong branch

If you forgot `--branch` and committed to the wrong branch, remove the commit from that branch and re-run on the correct one:

```sql
-- Remove the last commit from the wrong branch
CALL dolt_reset('--hard', 'HEAD~1');
```

Then re-run with the correct `--branch`:
```bash
python3 dolt_manage.py --csv launch_sites_v4.csv --host SERVER_IP --user dbadmin \
  --branch correct-branch-name
```

To check which branch is currently active:
```sql
SELECT active_branch();
```

### Script applied corrupting data and I need to recover

If the corruption was **not committed** yet:
```sql
CALL dolt_reset('--hard');
```

If the corruption **was committed**:
```sql
CALL dolt_reset('--hard', 'HEAD~1');
```

If you need to go back further, find the right hash first:
```sql
SELECT commit_hash, message, date FROM dolt_log;
CALL dolt_reset('--hard', '<the_hash_you_want>');
```

If you want to clear the database
```sql
USE launch_sites;
-- Check for duplicates
SELECT common_name, COUNT(*) AS cnt FROM sites GROUP BY common_name HAVING cnt > 1;
-- If duplicates exist, the safest fix is to truncate and reload
TRUNCATE TABLE sites;
```



## 1️⃣ `USE launch_sites;`

This tells the database server:

> “Make `launch_sites` the active database for this session.”

After this command runs, any table references (like `sites`) will be assumed to live inside the `launch_sites` database unless you fully qualify them.

So instead of:

```
SELECT * FROM launch_sites.sites;
```

You can just do:

```
SELECT * FROM sites;
```

------

## 2️⃣ Duplicate Check Query

```
SELECT common_name, COUNT(*) AS cnt
FROM sites
GROUP BY common_name
HAVING cnt > 1;
```

### What it does:

- Groups rows in the `sites` table by `common_name`
- Counts how many rows exist for each name
- Only returns names that appear **more than once**

### In plain English:

> “Show me any site names that appear multiple times.”

Example output:

| common_name    | cnt  |
| -------------- | ---- |
| Cape Canaveral | 2    |
| Vandenberg     | 3    |

This is typically used before adding a **UNIQUE constraint** or cleaning bad data.

## 3️⃣ `TRUNCATE TABLE sites;`

This is the big one.

### What it does:

- **Deletes ALL rows** from the `sites` table
- Resets auto-increment counters
- Is usually faster than `DELETE FROM sites;`
- Cannot be rolled back in many configurations

### It does NOT:

- Drop the table
- Remove indexes
- Remove schema

### It is equivalent to:

> “Empty the table completely.”



## ⚠️ Important Safety Warning

If this is production:

`TRUNCATE TABLE sites;`
 = irreversible data loss unless you have backups.

Since this table is in **Dolt**, you’d actually be safer because you could:

```
dolt checkout <previous-commit>
```

But in standard MySQL? You better have a backup.

---

*Dolt documentation: https://docs.dolthub.com*
*uv documentation: https://docs.astral.sh/uv*
*mysql-connector-python: https://dev.mysql.com/doc/connector-python/en/*
