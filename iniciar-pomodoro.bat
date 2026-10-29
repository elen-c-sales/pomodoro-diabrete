@echo off
REM Abre o Pomodoro Pet sem janela de console. Flags opcionais: --demo, --opaque, --sound
cd /d "%~dp0"
set "VENV_PY=.venv\Scripts\python.exe"

REM Confere se o pygame importa, e nao so se a venv existe: uma instalacao
REM interrompida deixaria a venv sem pygame e o pythonw falharia em silencio.
"%VENV_PY%" -c "import pygame" >nul 2>&1
if errorlevel 1 (
    echo Preparando o ambiente, so acontece na primeira vez...
    if not exist "%VENV_PY%" (
        py -3 -m venv .venv >nul 2>&1 || python -m venv .venv || goto :erro
    )
    "%VENV_PY%" -m pip install -q --disable-pip-version-check -r requirements.txt || goto :erro
)
start "" ".venv\Scripts\pythonw.exe" pomodoro.py %*
exit /b 0

:erro
echo.
echo Nao foi possivel preparar o ambiente. Confira se o Python 3 esta instalado
echo em https://www.python.org e se ha conexao com a internet.
pause
exit /b 1
