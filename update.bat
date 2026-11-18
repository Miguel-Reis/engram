@echo off
chcp 65001 >nul
echo ====================================================================
echo  🔄 A verificar e instalar atualizacoes do Engram v9.0...
echo ====================================================================
python "%~dp0auto_updater.py"
python "%~dp0install.py" --silent
echo.
echo ✅ Concluido!
pause
