import re
import pandas as pd

def is_test_file(filename):
    return \
    bool(re.search(r'test/|tests/|src/test/|src/tests/', filename)) or \
    bool(re.search(r'.*[Tt]est\.java$|^[Tt]est\w+\.java$', filename))

def is_prod_file(filename):
    return bool(re.search(r'/src/|/main/|/lib/', filename))

def to_commit_df(repo_json):
    repo_name = repo_json.get("name", "unknown")
    main_branch = repo_json.get("main_branch")
    commits = repo_json.get("commits", {})  # dict: hash -> commit_data

    rows = []
    for h, c in commits.items():
        branches = c.get("branches", [])
        rows.append({
            "repo": repo_name,
            "main_branch": main_branch,
            "hash": c.get("hash", h),
            "timestamp": c.get("timestamp"),
            "author": c.get("author"),
            "is_merge": bool(c.get("is_merge")),
            "branches": branches,
            "on_main": (main_branch in branches) if main_branch else False,
            "num_lines_changed": c.get("num_lines_changed"),
            "num_files_changed": c.get("num_files_changed"),
            "modified_files": c.get("modified_files", []),
        })

    df = pd.DataFrame(rows)
    df["dt"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["year"] = df["dt"].dt.year
    return df

def classify_commits(df):
    test_counts = []
    code_counts = []
    unknown_java_counts = []
    commit_types = []

    for _, row in df.iterrows():
        t = 0
        c = 0
        u = 0

        for mf in (row["modified_files"] or []):
            path = mf.get("new_path") or mf.get("old_path") or mf.get("filename")
            p = path

            # your mined data only saved .java files, but keep it safe anyway
            if not p.endswith(".java"):
                continue

            if is_test_file(p):
                t += 1
            elif is_prod_file(p):
                c += 1
            else:
                # java file but not in src/java or test/ (tools, examples, etc.)
                u += 1
                # choose ONE of these behaviours:
                # 1) treat unknown java as code (uncomment next line)
                c += 1

        if t > 0 and c == 0:
            ct = "test_only"
        elif c > 0 and t == 0:
            ct = "code_only"
        elif c > 0 and t > 0:
            ct = "mixed"
        else:
            ct = "none"

        test_counts.append(t)
        code_counts.append(c)
        unknown_java_counts.append(u)
        commit_types.append(ct)

    return test_counts, code_counts, unknown_java_counts, commit_types