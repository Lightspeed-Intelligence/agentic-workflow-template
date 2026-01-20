#!/bin/bash
# 初始化所有子模块

set -e

echo "正在初始化子模块..."
git submodule init
git submodule update --progress

echo "✅ 所有子模块初始化完成！"
git submodule status
