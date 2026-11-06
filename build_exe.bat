@echo off
rem Сборка RangeCodingDemo.exe (нужен Python 3.9+ для Windows)
cd /d "%~dp0"
python -m pip install --upgrade pyinstaller -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name RangeCodingDemo ^
    --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide6 --exclude-module matplotlib --exclude-module numpy --exclude-module PIL ^
    --collect-data docx ^
    range_coding_gui.py
echo.
echo Готово: dist\RangeCodingDemo.exe
pause
