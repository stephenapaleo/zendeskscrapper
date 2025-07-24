@echo off
echo.
echo ========================================
echo    Zendesk Data Collector
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and try again
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist .env (
    echo ERROR: .env file not found
    echo Please copy .env.example to .env and configure your Zendesk credentials
    echo.
    if exist .env.example (
        echo Copying .env.example to .env...
        copy .env.example .env
        echo.
        echo Please edit .env file with your Zendesk credentials:
        echo - ZENDESK_SUBDOMAIN=your-subdomain  
        echo - ZENDESK_EMAIL=your-email@company.com
        echo - ZENDESK_API_TOKEN=your-api-token
        echo.
        notepad .env
    )
    pause
    exit /b 1
)

REM Check if dependencies are installed
echo Checking dependencies...
pip show requests >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
)

echo.
echo Available commands:
echo   1. Export everything (recommended)
echo   2. Export tickets only
echo   3. Export users only  
echo   4. Export organizations only
echo   5. Export knowledge base only
echo   6. Export macros only
echo   7. Export groups only
echo   8. Test connection
echo   9. Custom command
echo.

set /p choice="Enter your choice (1-9): "

if "%choice%"=="1" goto export_all
if "%choice%"=="2" goto export_tickets
if "%choice%"=="3" goto export_users
if "%choice%"=="4" goto export_organizations
if "%choice%"=="5" goto export_knowledge_base
if "%choice%"=="6" goto export_macros
if "%choice%"=="7" goto export_groups
if "%choice%"=="8" goto test_connection
if "%choice%"=="9" goto custom_command

echo Invalid choice. Please try again.
pause
goto :eof

:export_all
echo Running complete data export...
python main.py all
goto end

:export_tickets
echo Running tickets export...
python main.py tickets
goto end

:export_users
echo Running users export...
python main.py users
goto end

:export_organizations
echo Running organizations export...
python main.py organizations
goto end

:export_knowledge_base
echo Running knowledge base export...
python main.py knowledge-base
goto end

:export_macros
echo Running macros export...
python main.py macros
goto end

:export_groups
echo Running groups export...
python main.py groups
goto end

:test_connection
echo Testing connection...
python main.py test
goto end

:custom_command
echo.
echo Enter custom command options (e.g., tickets --status open):
set /p custom_options=""
python main.py %custom_options%
goto end

:end
echo.
if %errorlevel%==0 (
    echo ✅ Operation completed successfully!
    echo 📁 Check the 'output' folder for your markdown files
) else (
    echo ❌ Operation failed. Please check the error messages above.
)
echo.
pause 