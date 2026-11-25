#!/usr/bin/env bash
# 把「从模板创建的新仓库」整理成消费仓库：只保留调用方 workflow 与忽略规则，其余受跟踪文件
# 全部删除，README 换成骨架。只改索引和工作树，不提交；提交与推送由 template-cleanup.yml 完成。
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# 新增到模板仓库的文件默认属于模板专用，会被删除；要带进消费仓库的文件必须列在这里。
keep=(
  .github/workflows/ci.yml
  .gitignore
  .llmdoc-tmp/.gitignore
)
skeleton_source=.github/template/README.md

repository=${GITHUB_REPOSITORY:?GITHUB_REPOSITORY is required}
repo_name=${repository##*/}

for path in "${keep[@]}" "$skeleton_source"; do
  if ! git ls-files --error-unmatch -- "$path" > /dev/null 2>&1; then
    echo "::error::缺少 ${path}，这不是未清理的模板副本，拒绝清理。" >&2
    exit 1
  fi
done
if [[ -n "$(git status --porcelain)" ]]; then
  echo "::error::工作树有未提交的改动，拒绝清理。" >&2
  exit 1
fi

skeleton=$(< "$skeleton_source")
skeleton=${skeleton//'{{REPO_NAME}}'/$repo_name}

declare -A kept=()
for path in "${keep[@]}"; do
  kept[$path]=1
done

removed=0
while IFS= read -r -d '' path; do
  if [[ -n "${kept[$path]:-}" ]]; then
    continue
  fi
  git rm -q -- "$path"
  removed=$((removed + 1))
done < <(git ls-files -z)

printf '%s\n' "$skeleton" > README.md
git add -- README.md

echo "已删除 ${removed} 个模板专用文件；保留：${keep[*]} README.md"
