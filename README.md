# gitlab_audit_export

# 🧰 GitLab + Local Git Audit Log Exporter

## Overview
This Python script extracts and aggregates **Git activity logs** — including **commits**, **branches**, **merges**, and **local user actions** — from both:
- a **GitLab CE (Community Edition)** instance via its REST API, and/or  
- a **local Git repository** directory (e.g. `/path/to/repo`).

It then outputs the results either as:
- a **sortable, interactive HTML report**, or  
- a **CSV file** for data analysis.

The script is ideal for tracking developer activity, auditing project history, or generating time-based summaries.

---

## 🚀 Features

- ✅ Pulls **commits**, **branches**, and **merge requests** from GitLab CE REST API.  
- ✅ Extracts **local user actions** via `git log` and `git reflog`.  
- ✅ Supports **custom date ranges**:
  - “Last *N* months”  
  - Or a specific period (e.g. `24/07/2025` → `02/10/2025`)
- ✅ Exports results to:
  - **Interactive HTML report** (sortable & searchable tables)
  - **CSV file**
- ✅ Works even **offline** (from local repo only).
- ✅ Simple configuration — single script, no complex setup.

---

## 🧩 Requirements

Create a virtual environment and install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

python gitlab_audit_export.py --repo-path /path/to/repo [options]   

## ⚙️ Command-Line Options

| **Argument** | **Description** | **Example** |
|---------------|-----------------|--------------|
| `--repo-path` | Path to the local Git repository. | `/home/user/project` |
| `--gitlab-url` | *(Optional)* Base URL of your GitLab CE instance. | `https://gitlab.example.com` |
| `--gitlab-token` | *(Optional)* GitLab Personal Access Token (required for private projects). | `glpat-12345...` |
| `--project-id` | *(Optional)* GitLab project ID or URL-encoded path. | `mygroup/myrepo` |
| `--months` | Number of months back to retrieve logs. | `--months 3` |
| `--start-date` | Start date for filtering (DD/MM/YYYY). | `--start-date 24/07/2025` |
| `--end-date` | End date for filtering (DD/MM/YYYY). | `--end-date 02/10/2025` |
| `--output` | Output file path (HTML or CSV). | `--output activity_report.html` |
| `--format` | Output format: `html` *(default)* or `csv`. | `--format csv` |

## 📄 Output Formats

| **Format** | **Description** | **Details / Columns** |
|-------------|-----------------|------------------------|
| **HTML report** | Generates an **interactive**, **sortable**, and **searchable** table of all recorded Git and GitLab activity. Each column can be clicked to sort ascending/descending. The report uses embedded JavaScript and CSS for full offline functionality (no internet connection required). | - Sortable and searchable<br>- Local-only (self-contained file)<br>- Best viewed in any modern web browser |
| **CSV report** | Produces a machine-readable file with one row per event (commit, branch, or user action). Ideal for importing into Excel, Power BI, or data analytics tools. | **Columns:**<br>`source`, `action_type`, `user_name`, `user_email`, `timestamp`, `ref`, `commit_sha`, `message`, `url` |

## 🧠 Usage Examples

- **Example 1: ️⃣ Local repo only**
  - **Command**
  		```bash
		python git_activity_logger.py \
		--repo-path /projects/myrepo \
		--months 2 \
		--output report.html
		```
  - **Description**
		Retrieves the last **two months** of commits, branches, and user actions from the **local repository** and generates an **interactive HTML report**. |
- **Example 2:2️⃣ Include GitLab data**
  - **Command**
  		```bash
		python git_activity_logger.py \
		--repo-path /projects/myrepo \
		--gitlab-url https://gitlab.mycompany.com \
		--gitlab-token glpat-abcdef123456 \
		--project-id mygroup/myrepo \
		--start-date 01/07/2025 \
		--end-date 30/09/2025 \
		--format csv \
		--output report.csv
		```
  - **Description**
		Combines **GitLab commits, branches, and merges** with **local user actions** (from `git reflog`) into a single **CSV export**. |
- **Example 2:3️⃣ Offline fallback mode** 
  - **Command**
		*(No GitLab URL or token required)*<br><br>When `--gitlab-url` and `--gitlab-token` are omitted, the script automatically falls back to **local Git commands**: <br><br>- `git log` → commits<br>- `git reflog` → user actions<br>- *(Optional)* `git for-each-ref` → branches (if implemented)	
  - **Description**
		Runs completely **offline**, useful for local-only auditing or repositories without a connected GitLab instance. |

## 🔐 Authentication

| **Scenario** | **Requirement** | **Details** |
|---------------|-----------------|--------------|
| **Public GitLab projects** | `--gitlab-token` **optional** | The script can access public repository data directly from the GitLab REST API without authentication. |
| **Private GitLab repositories** | `--gitlab-token` **required** | You must provide a valid **Personal Access Token** with the following permissions:<br><br>- `read_api`<br>- `read_repository` |
| **Token generation** | — | Tokens can be created in **GitLab → User → Preferences → Access Tokens**. Copy and use the generated token in your command with `--gitlab-token`. |

## 🛡️ Security Best Practices

| **Recommendation** | **Description** |
|---------------------|-----------------|
| **🔑 Keep tokens private** | Never store your `--gitlab-token` in plaintext inside scripts, `.bash_history`, or version control (e.g. `.gitignore` it). |
| **⚙️ Use environment variables** | Instead of passing tokens directly in the command line, export them as environment variables:<br>`export GITLAB_TOKEN="glpat-xxxx"`<br>Then run:<br>`python git_activity_logger.py --gitlab-token $GITLAB_TOKEN ...` |
| **🧾 Limit token scope** | When generating a Personal Access Token, only enable the **minimum required scopes** — typically `read_api` and `read_repository`. |
| **⏳ Rotate tokens regularly** | Periodically revoke and regenerate tokens to reduce the risk of long-term exposure. |
| **💾 Protect local reports** | Generated HTML or CSV reports may contain usernames, commit messages, and timestamps — store them in a secure, access-controlled location. |
| **🔒 Use HTTPS only** | Always interact with GitLab instances via HTTPS to protect credentials and token transmission from interception. |

## 🧩 Example HTML Table (Preview)

Below is a simplified preview of the interactive HTML report generated by the script:

```html
<table id="auditTable">
  <thead>
    <tr>
      <th>source</th>
      <th>action_type</th>
      <th>user_name</th>
      <th>timestamp</th>
      <th>message</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>gitlab_commit</td>
      <td>commit</td>
      <td>Jane Doe</td>
      <td>2025-09-15T14:22:00</td>
      <td>Fix memory leak in pipeline</td>
    </tr>
  </tbody>
</table>
```

## 🗒️ Notes

| **Note** | **Description** |
|-----------|-----------------|
| **💡 Self-contained HTML report** | The generated HTML output is fully standalone — you can open it directly in any browser, and it supports instant **sorting**, **searching**, and **filtering** without requiring an internet connection or any external libraries. |
| **🕒 Time range filtering** | When both `--months` and `--start-date` / `--end-date` are provided, the script prioritizes **explicit date ranges**. If only `--months` is given, it automatically calculates the date range from the current date. |
| **📁 Output format detection** | The script automatically detects the output format from the file extension (e.g., `.html` or `.csv`) if `--format` is not explicitly specified. |
| **🔍 Combined activity view** | The report merges **local Git data** (commits, branches, user reflog actions) with **GitLab events** (commits, merges, branches) into one unified activity timeline. |
| **⚙️ Error handling** | If GitLab API access fails or the network is unreachable, the script automatically falls back to **local Git-only mode** and logs a warning instead of stopping execution. |

 
## Release Notes

v.0.0.1		2025/11/13	First publication <br />