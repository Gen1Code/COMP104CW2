import pandas as pd
import json
import os
import matplotlib.pyplot as plt

from utils import to_commit_df, classify_commits, create_commit_graph, analyze_commit_graph
pd.set_option('display.max_columns', None)

data = []
#Load all mined repos into dataframes
for file in os.listdir("data"):
    with open(f'data/{file}', 'r', encoding="utf-8") as f:
        repo_data = json.load(f)

    df = to_commit_df(repo_data)
    data.append(df)
    print(file+" total commits loaded:", len(df))

#Anaylse commit graphs and classify commits
for i, df in enumerate(data):
    repo_name = df.iloc[0]['repo']

    G = create_commit_graph(df)
    stats = analyze_commit_graph(G)
    
    print(f"Commit Analysis for {repo_name}")
    print(f"Total commits: {stats['num_commits']}")
    print(f"Merge commits: {stats['num_merge_commits']}")

    stats = classify_commits(df)
    df["test_file_mods"] = stats["test_counts"]
    df["code_file_mods"] = stats["code_counts"]
    df["unknown_java_file_mods"] = stats["unknown_java_counts"]
    df["commit_type"] = stats["commit_types"]

    df_main = df[(df["on_main"]) & (~df["is_merge"]) & (df["commit_type"] != "none")]

    print(f"Non merge commits on main branch:", len(df_main))
    print(df_main["commit_type"].value_counts().to_string())
    print()


#Plot bar charts of commit types for each repo
for i, df in enumerate(data):
    df_main = df[(df["on_main"]) & (~df["is_merge"]) & (df["commit_type"] != "none")]
    repo_name = df_main['repo'].iloc[0]

    #Plot commit type distribution
    counts = df_main["commit_type"].value_counts()
    plt.figure()
    counts.plot(kind="bar")
    plt.xlabel("commit_type")
    plt.ylabel("count")
    plt.title(f"{repo_name}: commit types")
    plt.savefig(f"anaylsis/plots/{repo_name}_commit_types_bar.png")
    plt.close()

    #Plot commit types over time
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

    #Plot commit size distribution
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
    print("median lines changed:", round(float(sizes.median()),3) if len(sizes) else None)
    print("95th percentile:", round(float(sizes.quantile(0.95)),3) if len(sizes) else None)
    print()