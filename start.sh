#!/bin/sh
# 一键交付启动：构建并拉起 postgres/backend/frontend 三容器
cd "$(dirname "$0")"
docker compose up -d --build
echo "NovaStart 已启动，浏览器打开 http://localhost"
