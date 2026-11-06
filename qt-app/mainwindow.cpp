#include "mainwindow.h"
#include "ui_mainwindow.h"
#include <iomanip>
MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    connect(ui->lineEdit, &QLineEdit::returnPressed, this, &MainWindow::on_pushButton_clicked);
}

MainWindow::~MainWindow()
{
    delete ui;
}


void MainWindow::on_pushButton_clicked()
{
    ui->tableWidget->clearContents();
    ui->tableWidget_2->clearContents();
    QString s = ui->lineEdit->text();
    if(s.isEmpty()){
        ui->tableWidget->setRowCount(0);
        ui->tableWidget_2->setRowCount(0);
        ui->statusbar->showMessage("Введите сообщение");
        return;
    }
    QStringList bukv{};
    set<QString> alf;
    map<QString, QPair<double, double>> slov;
    for(QString ss: s){
        bukv.append(ss);
        alf.insert(ss);
    }
    ui->tableWidget->setRowCount(alf.size());
    ui->tableWidget_2->setRowCount(bukv.size());
    int c{};
    double interv{};
    for(auto ch: alf){
        ui->tableWidget->setItem(c, 0, new QTableWidgetItem(ch));
        double ver = double(bukv.count(ch)) / bukv.size();
        ui->tableWidget->setItem(c, 1, new QTableWidgetItem(QString::number(ver)));
        double start = interv;
        interv += ver;
        ui->tableWidget->setItem(c, 2, new QTableWidgetItem(QString("%1 - %2").arg(start).arg(interv)));
        QPair<double, double> l;
        l.first = interv-ver;
        l.second = interv;
        slov[ch] = l;
        c++;
    }
    QPair<long double, long double> in;
    in.first = slov[bukv[0]].first;
    in.second = slov[bukv[0]].second;
    ui->tableWidget_2->setItem(0, 0, new QTableWidgetItem(bukv[0]));
    ui->tableWidget_2->setItem(0, 1, new QTableWidgetItem(QString(QString("[%1 - %2)").arg(QString::number(in.first, 'f', 15)).arg(QString::number(in.second, 'f', 15)))));
    for(int c{1}; c<bukv.size(); c++){
        long double del = in.second - in.first;
//        qDebug() << QString("%1 + (%2 * %3) = %4").arg(QString::number(in.first, 'f', 15)).arg(QString::number(del, 'f', 15)).arg(slov[bukv[c]].first) << QString("%1 + (%2 * %3) = %4").arg(QString::number(in.first, 'f', 15)).arg(QString::number(del, 'f', 15)).arg(slov[bukv[c]].second) << endl;
        in.second = in.first + del*slov[bukv[c]].second;
        in.first += del*slov[bukv[c]].first;
//        std::cout << std::fixed << std::setprecision(12) << in.first << endl;
        ui->tableWidget_2->setItem(c, 0, new QTableWidgetItem(bukv[c]));
        ui->tableWidget_2->setItem(c, 1, new QTableWidgetItem(QString("[%1 - %2)").arg(QString::number(in.first, 'f', 15)).arg(QString::number(in.second, 'f', 15))));
    }
    ui->tableWidget->resizeColumnsToContents();
    ui->tableWidget_2->resizeColumnsToContents();
    ui->statusbar->showMessage(QString("Символов: %1, алфавит: %2").arg(bukv.size()).arg(alf.size()));
}
