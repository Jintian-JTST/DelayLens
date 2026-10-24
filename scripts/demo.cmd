@echo off
rem Double-click or run from any shell (cmd, PowerShell, bash): starts API + UI together.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1" %*
