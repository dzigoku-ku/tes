# chos — Qt-версия демонстрации интервального кодирования

Qt5 / C++ приложение: вводится сообщение, по нему строится таблица
вероятностей символов и их интервалов, затем пошагово показывается
сужение интервала при кодировании.

## Сборка под Linux

```bash
sudo apt install qtbase5-dev qt5-qmake build-essential curl
./build_appimage.sh          # результат: chos-x86_64.AppImage
```

Только собрать бинарник (нужен установленный Qt5 для запуска):

```bash
mkdir build && cd build && qmake ../chos.pro && make
./chos
```

Под Windows проект открывается в Qt Creator (`chos.pro`).
