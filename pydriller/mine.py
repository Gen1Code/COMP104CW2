from pydriller import Repository 
from datetime import datetime
import json
import re
import os

url = "https://github.com/apache/commons-io"
name_pattern = r"/([^/]+)$"
MANUAL_REMINE = False #Set to true if you want to remine a repo

def save_to_json(repo_url):
    matches = re.findall(name_pattern, repo_url)
    if not matches:
        print("Fix the jank seraching for naming in pydriller")
        assert False

    output_file = f"data/{matches[0]}.json"

    if not MANUAL_REMINE and os.path.exists(output_file):
        return

    data = {}

    for commit in Repository(repo_url, 
            only_modifications_with_file_types=['.java'], 
            only_in_branch="master", 
            num_workers=4
        ).traverse_commits():

        timestamp = commit.author_date.isoformat()
        commit_data = {
            "timestamp": timestamp,
            'is_merge': commit.merge,
        } 
    
        modified_files = []
        for modified_file in commit.modified_files:
            if modified_file.filename.endswith(".java"):
                file_data = {
                    "filename": modified_file.filename,
                }
                modified_files.append(file_data)

        commit_data["modified_files"] = modified_files

        data[timestamp] = commit_data

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved {repo_url} to {output_file}")


save_to_json(url)