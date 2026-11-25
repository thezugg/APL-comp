#!/usr/bin/env bash
# Safely publish this package into an EXISTING GitHub repository.
# Usage: bash scripts/publish-to-github.sh https://github.com/OWNER/APL-comp.git
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/publish-to-github.sh https://github.com/OWNER/APL-comp.git" >&2
  exit 2
fi
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
remote="$1"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
printf 'Cloning %s ...\n' "$remote"
git clone "$remote" "$work/repo"
# Preserve the remote's .git metadata and exclude secrets, databases and build files.
tar -C "$source_dir" -cf - \
  --exclude=.git --exclude=.env --exclude='.env.*' --exclude='*.db' \
  --exclude='*.sqlite*' --exclude='*.csv' --exclude='*.xlsx' \
  --exclude=node_modules --exclude=dist --exclude=.venv \
  --exclude=__pycache__ --exclude=.pytest_cache --exclude=backups . \
  | tar -C "$work/repo" -xf -
# Restore only safe tracked examples excluded by the blanket secret filters.
cp "$source_dir/.env.example" "$work/repo/.env.example"
mkdir -p "$work/repo/examples"
cp "$source_dir/examples/example-members.csv" "$work/repo/examples/example-members.csv"
cd "$work/repo"
git add -A
if git diff --cached --quiet; then
  echo 'Repository already matches this package. Nothing to publish.'
  exit 0
fi
git commit -m 'Add Pool League v4 React and FastAPI application'
git push -u origin HEAD
printf 'Published to %s\n' "$remote"
