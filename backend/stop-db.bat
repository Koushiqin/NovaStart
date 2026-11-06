@echo off
chcp 65001 >nul
pushd %~dp0
"D:\Javatools\pgsql\bin\pg_ctl.exe" stop -D D:\Javatools\pg-data -m fast
popd
