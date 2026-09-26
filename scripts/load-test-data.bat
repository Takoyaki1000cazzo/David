@echo off
REM Development test data loader (watch the reference order)
REM Usage: scripts\load-test-data.bat [--reset]
setlocal
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

if "%1"=="--reset" (
  echo WARNING: this deletes all data in the dev database.
  set /p "CONFIRM=Type YES to continue: "
  if not "%CONFIRM%"=="YES" (
    echo Aborted.
    exit /b 1
  )
  echo flushing database...
  %PY% manage.py flush --noinput
)

echo loading fixtures...
%PY% manage.py loaddata sample_users free_books_seed sample_progress sample_favorites
echo done.
