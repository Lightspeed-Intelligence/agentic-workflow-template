#!/bin/bash
# 查看所有子模块状态

echo "=== 子模块状态 ==="
git submodule status

echo ""
echo "=== 各子模块分支信息 ==="
git submodule foreach 'echo "[$name] $(git branch --show-current) - $(git log -1 --oneline)"'
