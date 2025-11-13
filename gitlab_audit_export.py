#!/usr/bin/env python3

__description__ = 'gitlab_audit_export.py: GitLab free or Community Edition audit log exporter.'
__author__ = 'BlueJay00'
__version__ = '0.1'
__date__ = '2025/11/13'



"""
History:
  2025/10/20: start v0.0.01
  2025/10/22: continue v0.0.05
  2025/10/25: made HTML output interactive v0.0.2
  2025/10/26: added option for time range filtering v0.0.3
  2025/11/12: bug fixes v0.0.4
  2025/11/13: first publication v0.1

Done:
- Transform HTML output into interactive making sortable and searchable only with JS.
- Added option to choose the number of months to go back in the logs or filter through a time range

Todo:
Map local commit SHAs to branches (by checking branch contains, or git branch --contains <sha>).
Fetch pipeline or comment events (/pipelines or /projects/:id/events) depending on what may need to be audited.
Enrich MR data with approvals and merge times, or get note/comment history (/merge_requests/:id/notes).
Export to JSON or more advanced HTML (with filtering).
Running on many repos or many projects by wrapping the script in a loop (or adapt to multi-project) to allow to work across multiple projects.


Notes:
1) Permissions — the GitLab token needs the appropriate scope (API access) and project visibility to read commits, merges, branches and events.
Use a token created for a user with read/maintainer access to the project for best results.

2) Project Identification — give either the numeric project ID or the path 'group/subgroup/project' to the option '--project'.
The script will try to resolve a path to an ID anyway.

3) Reflog — reflog is local-only (per repository) and shows local operations (checkout, merge, pull, reset, etc.).
It’s only available on the machine that holds that repo and depends on the user's git config and reflog expiration settings.

4) Pagination — this script uses the 'per_page=100' option and follows GitLab's 'X-Next-Page' header to fetch pages.

5) Timestamps — this script tries to normalize timestamps using 'python-dateutil' library, if available.
It can be installed with 'pip install python-dateutil' for nicer ISO timestamps.

6) API + Local combintation — this script is meant to combine Remote data (GitLab), meaning commits, branches, merges, user actions;
and Local data (repo), meaning commit logs ('git log') and reflog actions ('git reflog').
This is because GitLab’s API already provides complete branch info.

"""

import argparse
import csv
import html
import os
import subprocess
import sys
import time
from urllib.parse import quote_plus
from datetime import datetime, timedelta

import requests

try:
    from dateutil import parser as dtparser
except Exception:
    dtparser = None

# ---------------------------
# Helper: Date normalization and filtering
# ---------------------------

def normalize_date(s):
    if not s:
        return ''
    if isinstance(s, datetime):
        return s.isoformat()
    if dtparser:
        try:
            return dtparser.parse(s).isoformat()
        except Exception:
            return s
    return s

def parse_date_any(s):
    if not s:
        return None
    s = s.replace('/', '-')
    if dtparser:
        try:
            return dtparser.parse(s, dayfirst=True)
        except Exception:
            return None
    # fallback: try ISO
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def within_range(ts, start=None, end=None):
    if not ts:
        return False if (start or end) else True
    try:
        dt = parse_date_any(ts)
    except Exception:
        return False
    if start and dt < start:
        return False
    if end and dt > end:
        return False
    return True

# ---------------------------
# Code to fetch data from GitLab API client
# ---------------------------
class GitLabClient:
    def __init__(self, base_url, private_token, verify_ssl=True):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({"PRIVATE-TOKEN": private_token})
        self.verify = verify_ssl

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        params = params or {}
        params.setdefault('per_page', 100)
        all_items = []
        while True:
            r = self.session.get(url, params=params, verify=self.verify)
            if not r.ok:
                raise RuntimeError(f"GitLab API error {r.status_code}: {r.text}")
            data = r.json()
            if isinstance(data, dict):
                return data
            all_items.extend(data)
            next_page = r.headers.get('X-Next-Page') or ''
            if not next_page:
                break
            params['page'] = next_page
            time.sleep(0.1)
        return all_items

    def get_project_by_path(self, project_path):
        return self._get(f"/api/v4/projects/{quote_plus(project_path)}")

    def list_commits(self, proj):
        return self._get(f"/api/v4/projects/{quote_plus(str(proj))}/repository/commits")

    def list_branches(self, proj):
        return self._get(f"/api/v4/projects/{quote_plus(str(proj))}/repository/branches")

    def list_merge_requests(self, proj):
        return self._get(f"/api/v4/projects/{quote_plus(str(proj))}/merge_requests", params={'state': 'all'})

# ---------------------------
# Run local git helpers (commands that can be used without any remote connection or API, directly on /path/to/repo/.git) with git
# ---------------------------
def run_git(repo_path, args):
    out = subprocess.check_output(['git'] + args, cwd=repo_path, text=True, stderr=subprocess.DEVNULL)
    return out

# ---------------------------
# Run 'git log' to get the full commit history (authors, messages, dates, merges, etc.)
# ---------------------------
def parse_git_log(repo_path):
    fmt = "%H|%an|%ae|%ad|%s"
    out = run_git(repo_path, ['log', '--all', f'--pretty=format:{fmt}', '--date=iso'])
    rows = []
    for line in out.splitlines():
        p = line.split('|', 4)
        if len(p) < 5:
            continue
        sha, an, ae, ad, msg = p
        rows.append({
            "source": "local_commit",
            "action_type": "commit",
            "user_name": an,
            "user_email": ae,
            "timestamp": ad,
            "ref": "",
            "commit_sha": sha,
            "message": msg,
            "url": ""
        })
    return rows

# ---------------------------
# Run 'git reflog' to local reference changes (local operations like commits, merges, resets, etc.)
# ---------------------------
def parse_reflog(repo_path):
    out = run_git(repo_path, ['reflog', '--date=iso'])
    rows = []
    for line in out.splitlines():
        parts = line.split(' ', 1)
        sha = parts[0]
        msg = parts[1] if len(parts) > 1 else ''
        rows.append({
            "source": "local_reflog",
            "action_type": "reflog",
            "user_name": "",
            "user_email": "",
            "timestamp": "",  # git reflog output doesn't easily include timestamp unless formatted
            "ref": "",
            "commit_sha": sha,
            "message": msg,
            "url": ""
        })
    return rows

# ---------------------------
# HTML Writer (interactive)
# ---------------------------
def write_interactive_html(rows, out_file):
    # Collect fieldnames
    keys = []
    for r in rows:
        for k in r.keys():
            if k not in keys:
                keys.append(k)

    with open(out_file, 'w', encoding='utf-8') as fh:
        fh.write("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>GitLab Audit Export</title>
<style>
body{font-family:Arial,Helvetica,sans-serif;margin:20px;}
table{border-collapse:collapse;width:100%;}
th,td{border:1px solid #ddd;padding:6px;}
th{background:#f2f2f2;cursor:pointer;}
tr:nth-child(even){background:#fafafa;}
input{margin-bottom:10px;padding:6px;width:300px;}
</style>
</head><body>
<h2>GitLab Audit Export (Interactive)</h2>
<input type="text" id="searchBox" placeholder="Search...">
<table id="auditTable">
<thead><tr>""")
        for k in keys:
            fh.write(f"<th>{html.escape(k)}</th>")
        fh.write("</tr></thead><tbody>")
        for r in rows:
            fh.write("<tr>")
            for k in keys:
                v = r.get(k, '')
                fh.write(f"<td>{html.escape(str(v))}</td>")
            fh.write("</tr>")
        fh.write("""</tbody></table>
<script>
// Simple sort + search
const table=document.getElementById('auditTable');
const headers=table.querySelectorAll('th');
headers.forEach((th,idx)=>{
  th.addEventListener('click',()=>{
    const rows=[...table.tBodies[0].rows];
    const asc=th.asc=!th.asc;
    rows.sort((a,b)=>{
      const av=a.cells[idx].innerText.trim().toLowerCase();
      const bv=b.cells[idx].innerText.trim().toLowerCase();
      return av.localeCompare(bv)*(asc?1:-1);
    });
    rows.forEach(r=>table.tBodies[0].appendChild(r));
  });
});
document.getElementById('searchBox').addEventListener('input',function(){
  const q=this.value.toLowerCase();
  [...table.tBodies[0].rows].forEach(r=>{
    r.style.display=[...r.cells].some(c=>c.innerText.toLowerCase().includes(q))?'':'none';
  });
});
</script>
</body></html>""")
    print(f"Wrote interactive HTML: {out_file} ({len(rows)} rows)")

# ---------------------------
# Main data collection logic of the script
# ---------------------------
def collect_data(args):
    rows = []
    start_date, end_date = None, None
    if args.months_back:
        start_date = datetime.now() - timedelta(days=30*args.months_back)
    if args.date_range:
        start_date = parse_date_any(args.date_range[0])
        end_date = parse_date_any(args.date_range[1])

    client = None
    if args.gitlab_url and args.private_token:
        client = GitLabClient(args.gitlab_url, args.private_token, verify_ssl=not args.insecure)
        try:
            proj = client.get_project_by_path(args.project)
            proj_id = proj['id']
        except Exception as e:
            print(f"Failed to resolve project path, using given id: {e}")
            proj_id = args.project
        # For commits
        try:
            commits = client.list_commits(proj_id)
            for c in commits:
                ts = normalize_date(c.get('created_at') or c.get('committed_date'))
                if not within_range(ts, start_date, end_date): 
                    continue
                rows.append({
                    "source": "gitlab_commit",
                    "action_type": "commit",
                    "user_name": c.get('author_name'),
                    "user_email": c.get('author_email'),
                    "timestamp": ts,
                    "ref": "",
                    "commit_sha": c.get('id'),
                    "message": c.get('message','').replace('\n',' '),
                    "url": c.get('web_url','')
                })
        except Exception as e:
            print(f"GitLab commits fetch error: {e}")
        # For branches
        try:
            branches = client.list_branches(proj_id)
            for b in branches:
                commit = b.get('commit',{})
                ts = normalize_date(commit.get('committed_date'))
                if not within_range(ts, start_date, end_date):
                    continue
                rows.append({
                    "source": "gitlab_branch",
                    "action_type": "branch",
                    "user_name": "",
                    "user_email": "",
                    "timestamp": ts,
                    "ref": b.get('name'),
                    "commit_sha": commit.get('id'),
                    "message": commit.get('message',''),
                    "url": b.get('web_url','')
                })
        except Exception as e:
            print(f"GitLab branches fetch error: {e}")
        # For merges & requests
        try:
            mrs = client.list_merge_requests(proj_id)
            for m in mrs:
                ts = normalize_date(m.get('updated_at'))
                if not within_range(ts, start_date, end_date):
                    continue
                rows.append({
                    "source": "gitlab_merge_request",
                    "action_type": f"merge_request_{m.get('state')}",
                    "user_name": (m.get('author') or {}).get('name'),
                    "user_email": "",
                    "timestamp": ts,
                    "ref": f"{m.get('source_branch')}->{m.get('target_branch')}",
                    "commit_sha": m.get('sha',''),
                    "message": m.get('title',''),
                    "url": m.get('web_url','')
                })
        except Exception as e:
            print(f"GitLab merge requests fetch error: {e}")

    # Add local repo option
    if args.repo_path:
        try:
            for entry in parse_git_log(args.repo_path):
                ts = entry.get('timestamp')
                if not within_range(ts, start_date, end_date):
                    continue
                rows.append(entry)
        except Exception as e:
            print(f"Local git log error: {e}")
        try:
            for entry in parse_reflog(args.repo_path):
                ts = entry.get('timestamp')
                if not within_range(ts, start_date, end_date):
                    continue
                rows.append(entry)
        except Exception as e:
            print(f"Local reflog error: {e}")

    return rows

# ---------------------------
# CSV writer
# ---------------------------
def write_csv(rows, path):
    if not rows:
        print("No data to write.")
        return
    keys = sorted(set(k for r in rows for k in r.keys()))
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k,'') for k in keys})
    print(f"Wrote {len(rows)} rows to CSV: {path}")

# ---------------------------
# CLI options
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Export GitLab or local repo audit trail actions to CSV or interactive HTML.")
    p.add_argument("--gitlab-url", help="Base GitLab URL (e.g. https://gitlab.example.com)")
    p.add_argument("--private-token", help="GitLab private token")
    p.add_argument("--project", required=True, help="GitLab project path or id")
    p.add_argument("--repo-path", required=True, help="Local repo path (e.g. /path/to/repo)")
    p.add_argument("--output-format", choices=["csv","html"], default="html")
    p.add_argument("--output-file", default="audit_output.html")
    p.add_argument("--months-back", type=int, help="Only include data newer than N months")
    p.add_argument("--date-range", nargs=2, metavar=('FROM','TO'), help="Filter by explicit date range (e.g. 2025-07-24 2025-10-02)")
    p.add_argument("--insecure", action='store_true', help="Disable SSL verify")
    return p.parse_args()

# ---------------------------
# Main function
# ---------------------------
def main():
    args = parse_args()
    rows = collect_data(args)
    if not rows:
        print("No matching data found.")
        sys.exit(0)
    if args.output_format == "csv":
        write_csv(rows, args.output_file)
    else:
        write_interactive_html(rows, args.output_file)

if __name__ == "__main__":
    main()
