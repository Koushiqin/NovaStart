@echo off
chcp 65001 >nul
pushd %~dp0
"D:\Javatools\pgsql\bin\pg_ctl.exe" start -D D:\Javatools\pg-data
popd
