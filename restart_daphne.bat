@echo off
REM =======================================================
REM  Daphne 服务原地重启脚本 (无新窗口)
REM =======================================================

ECHO.
ECHO [1/4] 重启流程启动... 正在关闭所有旧的 daphne.exe 进程。
taskkill /F /IM daphne.exe > nul 2>&1

ECHO.
ECHO [2/4] 等待 3 秒，确保端口和资源已完全释放...
timeout /t 1 /nobreak > NUL

ECHO.
ECHO [3/4] 准备在当前窗口启动新的 Daphne 服务...

REM !!! (必须修改) 进入你的项目所在的文件夹 !!!
cd /d "D:\wuyuan_project\mytestdjango_five_final"

ECHO.
ECHO [4/4] 启动服务！输出日志将显示在本窗口：
ECHO ---------------------------------------------------

REM --- 直接调用 daphne，不再使用 start 命令 ---
REM !!! (可能需要修改) 如果daphne不在系统路径中，请使用完整路径 !!!
REM 例如: C:\path\to\your\venv\Scripts\daphne.exe -b 0.0.0.0 ...
daphne -b 0.0.0.0 -p 8000 mytest.asgi:application
