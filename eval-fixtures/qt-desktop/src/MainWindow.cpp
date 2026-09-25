#include "MainWindow.h"
#include <QComboBox>
#include <QVBoxLayout>

MainWindow::MainWindow(QWidget *parent) : QMainWindow(parent) {
    auto *combo = new QComboBox(this);
    combo->setObjectName("sportCombo");
    combo->addItems({"Row", "Bike", "Run"});
    setCentralWidget(combo);
    QMetaObject::connectSlotsByName(this);
}

void MainWindow::on_sportCombo_currentIndexChanged(const QString &text) {
    m_sport = text;
}
