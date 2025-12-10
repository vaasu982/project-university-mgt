#!/usr/bin/env python3

import subprocess
import sys

# -----------------------------------------------------
# Run AutoSys commands
# -----------------------------------------------------
def run_cmd(cmd):
    try:
        output = subprocess.check_output(cmd, shell=True, text=True)
        return output.strip()
    except subprocess.CalledProcessError:
        return ""

# -----------------------------------------------------
# Extract dependent jobs from autorep -q -J <job>
# -----------------------------------------------------
def get_downstream(job):
    output = run_cmd(f"autorep -q -J {job}")
    children = []

    for line in output.splitlines():
        line = line.strip()
        # look for conditions like s(child_job)
        if "(" in line and ")" in line:
            cond = line.split("(")[1].split(")")[0]
            parts = cond.split(",")[0]     # remove time window
            if "_" in parts or parts.isalnum():
                child_job = parts.strip()
                if child_job != job:
                    children.append(child_job)
    return list(set(children))

# -----------------------------------------------------
# Find jobs that depend on this job (parents)
# -----------------------------------------------------
def get_upstream(job):
    output = run_cmd(f"autorep -D -J {job}")
    parents = []

    for line in output.splitlines():
        line = line.strip()
        if line and not line.startswith(" ") and job not in line:
            parents.append(line)
    return list(set(parents))

# -----------------------------------------------------
# Recursive tree print helpers
# -----------------------------------------------------
def print_tree(job, depth, direction, visited):
    indent = "   " * depth + ("└── " if depth else "")
    print(f"{indent}{job}")

    if job in visited:
        return
    visited.add(job)

    if direction == "down":
        for child in get_downstream(job):
            print_tree(child, depth + 1, "down", visited)

    elif direction == "up":
        for parent in get_upstream(job):
            print_tree(parent, depth + 1, "up", visited)

# -----------------------------------------------------
# Main - How to run
# chmod +x autosys_tree.py
# ./autosys_tree.py <JOB_NAME>
# -----------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 autosys_tree.py <JOB_NAME>")
        sys.exit(1)

    job = sys.argv[1]

    print("\n==========================")
    print("   DOWNSTREAM DEPENDENCY TREE")
    print("==========================")
    print_tree(job, 0, "down", set())

    print("\n==========================")
    print("   UPSTREAM DEPENDENCY TREE")
    print("==========================")
    print_tree(job, 0, "up", set())
