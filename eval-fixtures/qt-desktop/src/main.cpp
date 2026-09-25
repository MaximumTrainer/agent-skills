#include <QApplication>
#include "MainWindow.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    QCoreApplication::setAttribute(Qt::AA_ShareOpenGLContexts);
    MainWindow w;
    w.show();
    return app.exec();
}
