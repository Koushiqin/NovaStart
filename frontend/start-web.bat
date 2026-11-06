@echo off
rem 前端开发服务器启动脚本（双击可用，工作目录固定为脚本所在目录）
pushd %~dp0
npm run dev
