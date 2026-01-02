import pandas as pd
import json
import re
import os
from datetime import datetime
from typing import Dict, List, Optional, Set
import matplotlib.pyplot as plt

pd.set_option('display.max_columns', None)

def is_test_file(filename):
    return bool(re.search(r'[Tt]est\.java$|[Tt]est\w+\.java$', filename))

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

data = []
#Load all mined repos into dataframes
for file in os.listdir("data"):
    with open(f'data/{file}', 'r', encoding="utf-8") as f:
        repo_data = json.load(f)

    df = to_commit_df(repo_data)
    data.append(df)
    print(file+" total commits loaded:", len(df))

for i, df in enumerate(data):
    test_counts, code_counts, unknown_java_counts, commit_types = classify_commits(df)

    df["test_file_mods"] = test_counts
    df["code_file_mods"] = code_counts
    df["unknown_java_file_mods"] = unknown_java_counts
    df["commit_type"] = commit_types

    df_main = df[(df["on_main"]) & (~df["is_merge"]) & (df["commit_type"] != "none")]

    print(f"Repo {df.iloc[0]['repo']} - commits on main branch:", len(df_main))
    print(df_main["commit_type"].value_counts().to_string())


#Plot bar charts of commit types for each repo
for i, df in enumerate(data):
    df_main = df[(df["on_main"]) & (~df["is_merge"]) & (df["commit_type"] != "none")]
    repo_name = df_main['repo'].iloc[0]
    counts = df_main["commit_type"].value_counts()
    plt.figure()
    counts.plot(kind="bar")
    plt.xlabel("commit_type")
    plt.ylabel("count")
    plt.title(f"{repo_name}: commit types")
    plt.savefig(f"anaylsis/plots/{repo_name}_commit_types_bar.png")
    plt.close()

    by_year = df_main.groupby(["year", "commit_type"]).size().unstack(fill_value=0)

    plt.figure()
    bottom = None
    for col in by_year.columns:
        if bottom is None:
            plt.bar(by_year.index, by_year[col], label=col)
            bottom = by_year[col]
        else:
            plt.bar(by_year.index, by_year[col], bottom=bottom, label=col)
            bottom = bottom + by_year[col]

    plt.xlabel("year")
    plt.ylabel("count")
    plt.title(f"{repo_name}: commit types per year")
    plt.legend()
    plt.savefig(f"anaylsis/plots/{repo_name}_commit_types_per_year.png")
    plt.close()

    sizes = df_main["num_lines_changed"].dropna()

    plt.figure()
    plt.hist(sizes, bins=60)
    plt.xlabel("lines changed per commit")
    plt.ylabel("count")
    plt.title(f"{repo_name}: commit size")
    plt.yscale("log")
    plt.savefig(f"anaylsis/plots/{repo_name}_commit_size.png")
    plt.close()

    print(f"{repo_name} commit size stats:")
    print("median lines changed:", float(sizes.median()) if len(sizes) else None)
    print("95th percentile:", float(sizes.quantile(0.95)) if len(sizes) else None)