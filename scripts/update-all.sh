#!/bin/bash
# 更新所有子模块到最新版本

set -e

echo "正在更新所有子模块..."
git submodule update --remote --merge --progress

echo "✅ 所有子模块更新完成！"
git submodule status
