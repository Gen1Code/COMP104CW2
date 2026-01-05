import re
import pandas as pd
import networkx as nx

def is_test_file(filename):
    return \
    bool(re.search(r'test/|tests/|src/test/|src/tests/', filename)) or \
    bool(re.search(r'.*[Tt]est\.java$|^[Tt]est\w+\.java$', filename))

def is_prod_file(filename):
    return bool(re.search(r'src/|main/|lib/', filename)) and not is_test_file(filename)

def is_matching_testfile(file_path, candidate):
    patterns = [
        rf'[Tt]est{re.escape(file_path)}',           
        rf'{re.escape(file_path.replace('.java', ''))}[Tt]est\.java'     
    ]    
    return any(re.search(pattern, candidate) for pattern in patterns)

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
            "parents": c.get("parents", []),
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

    stats = {}
    stats["test_counts"] = test_counts
    stats["code_counts"] = code_counts
    stats["unknown_java_counts"] = unknown_java_counts
    stats["commit_types"] = commit_types

    return stats

def create_commit_graph(df):
    main_branch = df.iloc[0]["main_branch"]

    G = nx.DiGraph()
    for row in df.itertuples():
        G.add_node(row.hash, **{
            "timestamp": row.timestamp,
            "author": row.author,
            "is_merge": row.is_merge,
            "branches": row.branches,
            "on_main": main_branch in row.branches,
            "modified_files": row.modified_files
        })
    
    for row in df.itertuples():
        for parent_hash in row.parents:
            G.add_edge(row.hash, parent_hash)
    
    return G

def analyze_commit_graph(G):
    stats = {}
    stats["num_commits"] = G.number_of_nodes()
    stats["num_edges"] = G.number_of_edges()
    merge_commits = [node for node, data in G.nodes(data=True) if data.get("is_merge", False) or G.out_degree(node) > 1]
    stats["num_merge_commits"] = len(merge_commits)
    
    return stats

def tdd_adoption_anaylsis(df, G):
    results = []
    files_modified = set()

    df = df.sort_values('timestamp').reset_index(drop=True)
    for commit in df.itertuples():
        for file in commit.modified_files:
            if file["new_path"] and file["new_path"] not in files_modified and is_prod_file(file["new_path"]):
                prod_filename = file["filename"]
                files_modified.add(file["new_path"])
            
                test_file_found = False
                for other_file in commit.modified_files:
                    if other_file["new_path"] and is_test_file(other_file["new_path"]) and is_matching_testfile(prod_filename, other_file["filename"]):                        
                        test_file_found = True
                        results.append({
                            "commit_hash": commit.hash,
                            "prod_file": file["new_path"],
                            "test_file": other_file["new_path"],
                            "timestamp": commit.timestamp,
                            "merge_commit": False,
                            "delta_commits": 0
                        })
                        break
                    
                
                if not test_file_found:
                    #Search 30 commit using BFS
                    visited = set()
                    queue = [(commit.hash, 0)]  #(hash, depth)
                    while queue and not test_file_found:
                        current_hash, depth = queue.pop(0)
                        if depth >= 30:
                            continue
                        
                        for neighbour in G.successors(current_hash):
                            if neighbour not in visited:
                                visited.add(neighbour)
                                neighbour_data = G.nodes[neighbour]
                                
                                #Check modified files in neighbour commit
                                for other_file in neighbour_data.get("modified_files", []):
                                    if other_file["new_path"] and is_test_file(other_file["new_path"]) and is_matching_testfile(prod_filename, other_file["filename"]):
                                        results.append({
                                            "test_commit_hash": neighbour,
                                            "commit_hash": commit.hash,
                                            "prod_file": file["new_path"],
                                            "test_file": other_file["new_path"],
                                            "timestamp": commit.timestamp,
                                            "test_timestamp": neighbour_data.get("timestamp"),
                                            "merge_commit": neighbour_data.get("is_merge", False),
                                            "delta_commits": depth + 1
                                        })
                                        test_file_found = True
                                        break
                                
                                if test_file_found:
                                    break
                                queue.append((neighbour, depth + 1))
    
    return results, len(files_modified)