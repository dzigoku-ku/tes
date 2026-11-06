#!/bin/sh
# Сборка исполняемого файла dist/RangeCodingDemo для Linux.
# Нужны Python 3 с tkinter (Ubuntu/Debian: sudo apt install python3-tk python3-venv).
set -e
cd "$(dirname "$0")"
python3 -m venv .venv-build
.venv-build/bin/pip install --upgrade pyinstaller -r requirements.txt
.venv-build/bin/pyinstaller --noconfirm --onefile --windowed --name RangeCodingDemo \
    --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide6 --exclude-module matplotlib --exclude-module numpy --exclude-module PIL \
    --collect-data docx \
    range_coding_gui.py
echo "Готово: dist/RangeCodingDemo  (запуск: ./dist/RangeCodingDemo)"
