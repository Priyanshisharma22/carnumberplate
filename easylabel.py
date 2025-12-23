import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QWidget, QMessageBox, QScrollArea
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QWheelEvent
from PyQt6.QtCore import Qt, QRect


class ImageLabel(QLabel):
    def __init__(self, scroll_area: QScrollArea, parent=None):
        super().__init__(parent)
        self.scroll_area = scroll_area
        self.image = None
        self.start_point = None  # (x, y) in image coordinates
        self.end_point = None
        self.rectangles = []  # list of (x, y, w, h) in image coordinates
        self.drawing = False
        self.scale_factor = 1.0

    def load_image(self, path):
        self.image = QPixmap(path)
        self.scale_factor = 1.0
        self.rectangles.clear()
        self.setPixmap(self.image)
        self.adjustSize()

    def update_display(self):
        if self.image:
            scaled = self.image.scaled(
                int(self.image.width() * self.scale_factor),
                int(self.image.height() * self.scale_factor),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.setPixmap(scaled)
            self.adjustSize()

    def wheelEvent(self, event: QWheelEvent):
        old_pos = event.position().toPoint()
        h_scroll = self.scroll_area.horizontalScrollBar()
        v_scroll = self.scroll_area.verticalScrollBar()

        old_scroll_x = h_scroll.value()
        old_scroll_y = v_scroll.value()

        old_cursor_ratio_x = (old_pos.x() + old_scroll_x) / max(1, self.width())
        old_cursor_ratio_y = (old_pos.y() + old_scroll_y) / max(1, self.height())

        if event.angleDelta().y() > 0:
            self.scale_factor *= 1.1
        else:
            self.scale_factor /= 1.1

        self.scale_factor = max(0.1, min(self.scale_factor, 10.0))
        self.update_display()

        # maintain cursor position
        new_scroll_x = int(old_cursor_ratio_x * self.width() - old_pos.x())
        new_scroll_y = int(old_cursor_ratio_y * self.height() - old_pos.y())
        h_scroll.setValue(new_scroll_x)
        v_scroll.setValue(new_scroll_y)

    def mousePressEvent(self, event):
        if self.image and event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            img_x = pos.x() / self.scale_factor
            img_y = pos.y() / self.scale_factor
            self.start_point = (img_x, img_y)
            self.drawing = True

    def mouseMoveEvent(self, event):
        if self.drawing and self.image:
            pos = event.position().toPoint()
            img_x = pos.x() / self.scale_factor
            img_y = pos.y() / self.scale_factor
            self.end_point = (img_x, img_y)
            self.update()

    def mouseReleaseEvent(self, event):
        if self.drawing and event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            img_x = pos.x() / self.scale_factor
            img_y = pos.y() / self.scale_factor
            self.end_point = (img_x, img_y)
            x0, y0 = self.start_point
            x1, y1 = self.end_point
            x, y = min(x0, x1), min(y0, y1)
            w, h = abs(x1 - x0), abs(y1 - y0)
            self.rectangles.append((x, y, w, h))
            self.start_point = None
            self.end_point = None
            self.drawing = False
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.image:
            painter = QPainter(self)
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            # Draw saved rectangles
            for x, y, w, h in self.rectangles:
                r = QRect(
                    int(x * self.scale_factor),
                    int(y * self.scale_factor),
                    int(w * self.scale_factor),
                    int(h * self.scale_factor)
                )
                painter.drawRect(r)
            # Draw current rectangle
            if self.drawing and self.start_point and self.end_point:
                x0, y0 = self.start_point
                x1, y1 = self.end_point
                x, y = min(x0, x1), min(y0, y1)
                w, h = abs(x1 - x0), abs(y1 - y0)
                r = QRect(
                    int(x * self.scale_factor),
                    int(y * self.scale_factor),
                    int(w * self.scale_factor),
                    int(h * self.scale_factor)
                )
                painter.drawRect(r)

    def get_boxes(self):
        if not self.image:
            return []
        iw, ih = self.image.width(), self.image.height()
        boxes = []
        for x, y, w, h in self.rectangles:
            x_center = (x + w / 2) / iw
            y_center = (y + h / 2) / ih
            width = w / iw
            height = h / ih
            boxes.append((x_center, y_center, width, height))
        return boxes


class EasyLabel(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EasyLabel — Simple Image Annotation Tool")
        self.setGeometry(100, 100, 1280, 720)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(self.scroll_area)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #222;")
        self.scroll_area.setWidget(self.image_label)

        self.load_btn = QPushButton("Load Image")
        self.load_btn.clicked.connect(self.load_image)
        self.save_btn = QPushButton("Save YOLO Labels")
        self.save_btn.clicked.connect(self.save_labels)

        layout = QVBoxLayout()
        layout.addWidget(self.load_btn)
        layout.addWidget(self.save_btn)
        layout.addWidget(self.scroll_area)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
        self.current_image_path = None

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.current_image_path = file_path
            self.image_label.load_image(file_path)
            self.setWindowTitle(f"EasyLabel — {os.path.basename(file_path)}")

    def save_labels(self):
        if not self.current_image_path:
            QMessageBox.warning(self, "Warning", "No image loaded!")
            return
        boxes = self.image_label.get_boxes()
        if not boxes:
            QMessageBox.warning(self, "Warning", "No boxes to save!")
            return
        txt_path = os.path.splitext(self.current_image_path)[0] + ".txt"
        with open(txt_path, "w") as f:
            for box in boxes:
                f.write(f"0 {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}\n")
        QMessageBox.information(self, "Saved", f"Labels saved to:\n{txt_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EasyLabel()
    window.show()
    sys.exit(app.exec())
