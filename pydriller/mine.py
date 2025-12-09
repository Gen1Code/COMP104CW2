from pydriller import Repository 
from datetime import datetime
import json
import re
import os

urls = [
    "https://github.com/apache/commons-io",
    "https://github.com/apache/lucene",
    "https://github.com/apache/commons-lang",
    "https://github.com/apache/kafka",
    "https://github.com/apache/hadoop",
    "https://github.com/apache/cassandra",
    "https://github.com/apache/tomcat",
    "https://github.com/apache/maven"
]

name_pattern = r"/([^/]+)$"
MANUAL_REMINE = True #Set to true if you want to remine a repo


def get_default_branch(repo_url):
    repo = Repository(repo_url)
    for commit in repo.traverse_commits():
        if 'main' in commit.branches:
            return 'main'
        elif 'master' in commit.branches:
            return 'master'
        
        print(f"No master or main detected in {repo_url}")
        assert False

def save_to_json(repo_url):
    matches = re.findall(name_pattern, repo_url)
    if not matches:
        print("Fix the jank seraching for naming in pydriller")
        assert False

    output_file = f"data/{matches[0]}.json"
    if os.path.basename(os.getcwd()) == "pydriller":
        output_file = "../" +output_file 

    if not MANUAL_REMINE and os.path.exists(output_file):
        return

    main_branch = get_default_branch(repo_url)
    print(f"Main branch for {matches[0]} is {main_branch}")

    data = {}
    i = 1
    for commit in Repository(repo_url, 
            only_modifications_with_file_types=['.java'], 
            only_in_branch=main_branch,
            num_workers=8
        ).traverse_commits():

        if i%1000 == 0:
            print(f"Currently at {i} commits for {matches[0]}")

        timestamp = commit.author_date.isoformat()
        commit_data = {
            "timestamp": timestamp,
            "author": commit.author.name,
            'is_merge': commit.merge,
            "commit_msg": commit.msg[:100], #Limit to only first 100 characters
            "num_insertions": commit.insertions,
            "num_deletions": commit.deletions,
            "num_lines_changed": commit.lines
        } 
    
        modified_files = []
        for modified_file in commit.modified_files:
            if modified_file.filename.endswith(".java"):
                file_data = {
                    "filename": modified_file.filename,
                    "modification_type": modified_file.change_type.value, #https://pydriller.readthedocs.io/en/latest/reference.html#pydriller.domain.commit.ModificationType
                    "new_path": modified_file.new_path,
                    "old_path": modified_file.old_path,
                }
                modified_files.append(file_data)

        commit_data["modified_files"] = modified_files

        data[timestamp] = commit_data

        i+=1

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"saved {repo_url} to {output_file}")


for url in urls:
    save_to_json(url)