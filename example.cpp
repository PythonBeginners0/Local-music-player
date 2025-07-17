// example.cpp
#include <pybind11/pybind11.h>
#include <pybind11/qt.h>
#include <QWidget>

class FastWidget : public QWidget {
public:
    using QWidget::QWidget;

protected:
    void paintEvent(QPaintEvent *event) override {
        QPainter painter(this);
        painter.setRenderHint(QPainter::Antialiasing);
        if (isMaximized()) {
            painter.fillRect(rect(), painter.background());
        } else {
            QPainterPath path;
            path.addRoundedRect(rect(), 15, 15);
            painter.fillPath(path, painter.background());
        }
    }
};

PYBIND11_MODULE(example, m) {
    pybind11::class_<FastWidget, QWidget>(m, "FastWidget")
        .def(pybind11::init<>());
}
