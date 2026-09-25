#pragma once
#include <QMainWindow>
#include <QString>

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget *parent = nullptr);
private slots:
    void on_sportCombo_currentIndexChanged(const QString &text);
private:
    QString m_sport;
};
