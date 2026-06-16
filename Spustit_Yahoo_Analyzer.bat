@echo off
setlocal
cd /d "%~dp0"

echo ==============================================
echo   Yahoo News Impact Analyzer - spoustec
echo ==============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python nebyl nalezen. Nainstaluj Python 3.10+ a zaskrtni "Add python.exe to PATH".
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Vytvarim lokalni prostredi .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Nepodarilo se vytvorit .venv.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

if not exist ".venv\.news_impact_installed" (
    echo Instaluji potrebne knihovny do lokalni slozky .venv ...
    python -m pip install --upgrade pip
    if errorlevel 1 (
        echo Nepodarilo se aktualizovat pip.
        pause
        exit /b 1
    )
    python -m pip install -e .
    if errorlevel 1 (
        echo Nepodarilo se nainstalovat zavislosti projektu.
        pause
        exit /b 1
    )
    echo ok > ".venv\.news_impact_installed"
)

echo.
echo Spoustim webovou aplikaci. Po otevreni prohlizece klikni na "Spustit analyzu".
echo Pro ukonceni zavri toto okno nebo stiskni Ctrl+C.
echo.
python -m streamlit run src\streamlit_app.py
pause
