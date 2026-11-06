#!/bin/sh
# Сборка chos-x86_64.AppImage под Linux.
# Нужны: Qt5 (Ubuntu/Debian: sudo apt install qtbase5-dev qt5-qmake build-essential), curl.
set -e
cd "$(dirname "$0")"
mkdir -p build && cd build
qmake CONFIG+=release ../chos.pro
make -j"$(nproc)"
cd ..
for tool in linuxdeploy linuxdeploy-plugin-qt; do
    [ -x "$tool-x86_64.AppImage" ] || curl -fLO \
        "https://github.com/linuxdeploy/$tool/releases/download/continuous/$tool-x86_64.AppImage"
    chmod +x "$tool-x86_64.AppImage"
done
rm -rf AppDir
OUTPUT=chos-x86_64.AppImage APPIMAGE_EXTRACT_AND_RUN=1 QMAKE="$(command -v qmake)" ./linuxdeploy-x86_64.AppImage \
    --appdir AppDir -e build/chos \
    -d packaging/chos.desktop -i packaging/chos.png \
    --plugin qt --output appimage
echo "Готово: $(pwd)/chos-x86_64.AppImage"
