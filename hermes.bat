@echo off
chcp 65001 >nul
"%~dp0venv\Scripts\python.exe" -m hermes_cli.main %*
