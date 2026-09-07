@echo off
rem ============================================================
rem 本地打包脚本（不参与版本控制，已在 .gitignore 中忽略）
rem 产物: dist\main\main.exe（onedir + windowed）
rem ============================================================
setlocal
cd /d "%~dp0"

rem 通过 CONDA_EXE 自动定位 conda 安装目录，无需 conda init
if not defined CONDA_EXE (
    echo [错误] 未找到 CONDA_EXE 环境变量，请确认 Anaconda/Miniconda 已安装。
    pause
    exit /b 1
)
for %%i in ("%CONDA_EXE%") do set "CONDA_BASE=%%~dpi"

call "%CONDA_BASE%activate.bat" agent
if errorlevel 1 (
    echo [错误] 无法激活 conda 环境 "agent"，请确认该环境已创建。
    pause
    exit /b 1
)

python -m PyInstaller --clean --noconfirm --onedir --windowed .\main.py
if errorlevel 1 (
    echo [错误] PyInstaller 打包失败。
    pause
    exit /b 1
)

echo.
echo [完成] 可执行文件位于: %CD%\dist\main\main.exe
pause
endlocal
