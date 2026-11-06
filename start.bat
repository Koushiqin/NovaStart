@echo off
rem 一键交付启动：构建并拉起 postgres/backend/frontend 三容器
pushd %~dp0
docker compose up -d --build
echo.
echo NovaStart 已启动，浏览器打开 http://localhost
pause
