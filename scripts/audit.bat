@echo off
echo ==========================================
echo 🚀 SIFT: PRE-PUSH QUALITY GATE
echo ==========================================
echo.

set PYTHONPATH=.

echo [1/4] Checking Linting (Ruff)...
python -m ruff check .
if %errorlevel% neq 0 (
    echo ❌ LINT FAILURE: Please fix violations before pushing.
    exit /b %errorlevel%
)
echo All checks passed!
echo.

echo [2/4] Checking Type Safety (Mypy)...
python -m mypy context_pipe pipe_hook.py
if %errorlevel% neq 0 (
    echo ❌ TYPE FAILURE: Please fix type errors.
    exit /b %errorlevel%
)
echo Success: no type issues found.
echo.

echo [3/4] Running Security Scan (Bandit)...
python -m bandit -r context_pipe pipe_hook.py -ll -q
if %errorlevel% neq 0 (
    echo ❌ SECURITY FAILURE: Vulnerabilities detected!
    exit /b %errorlevel%
)
echo Secure.
echo.

echo [4/4] Running Unit Tests (Pytest)...
python -m pytest tests/ --tb=short -q
if %errorlevel% neq 0 (
    echo ❌ TEST FAILURE: Tests did not pass!
    exit /b %errorlevel%
)
echo.

echo ==========================================
echo ✅ GATE PASSED: Proceeding with push.
echo ==========================================
