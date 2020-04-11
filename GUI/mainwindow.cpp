#include "mainwindow.h"
#include "./ui_mainwindow.h"

MainWindow::MainWindow(QWidget *parent)
    : QMainWindow(parent)
    , ui(new Ui::MainWindow)
{
    ui->setupUi(this);
    this->model = new QFileSystemModel;
    this->model->setRootPath("");
    this->ui->treeView->setModel(this->model);
}

MainWindow::~MainWindow()
{
    delete ui;
}

