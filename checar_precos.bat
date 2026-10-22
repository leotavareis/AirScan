@echo off
rem Usado pelo Agendador de Tarefas do Windows.
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist logs mkdir logs
".venv\Scripts\python.exe" manage.py checar_precos >> logs\checar_precos.log 2>&1
