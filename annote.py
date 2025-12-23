import os, sys, cv2, json, random
from PyQt5 import QtWidgets, QtGui, QtCore

CONFIG_FILE = "last_dir.json"

def load_last_dir():
    if os.path.exists(CONFIG_FILE):
        try:
            return json.load(open(CONFIG_FILE)).get("last_dir","")
        except:
            return ""
    return ""

def save_last_dir(path):
    json.dump({"last_dir": path}, open(CONFIG_FILE,"w"))

# ---- BoxItem ----
class BoxItem(QtWidgets.QGraphicsRectItem):
    def __init__(self, rect, cls, cls_name, img_size, color):
        super().__init__(rect)
        self.cls = cls
        self.cls_name = cls_name
        self.img_w, self.img_h = img_size

        self.text_item = QtWidgets.QGraphicsSimpleTextItem(cls_name, self)
        self.text_item.setBrush(color)
        font = QtGui.QFont()
        font.setPointSize(20)
        self.text_item.setFont(font)
        self.text_item.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self.update_label_pos()

        pen = QtGui.QPen(color, 5)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QtGui.QBrush(QtCore.Qt.transparent))

    def update_label_pos(self):
        r = self.rect()
        self.text_item.setPos(r.left(), r.top() - 30)

    def to_yolo(self):
        r = self.rect()
        x1, y1, x2, y2 = max(0, r.left()), max(0, r.top()), min(self.img_w, r.right()), min(self.img_h, r.bottom())
        xc = ((x1 + x2) / 2) / self.img_w
        yc = ((y1 + y2) / 2) / self.img_h
        ww = abs(x2 - x1) / self.img_w
        hh = abs(y2 - y1) / self.img_h
        return f"{self.cls} {xc:.6f} {yc:.6f} {ww:.6f} {hh:.6f}"

# ---- Annotator ----
class ImageAnnotator(QtWidgets.QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QtWidgets.QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QtGui.QPainter.Antialiasing | QtGui.QPainter.SmoothPixmapTransform)
        self.setDragMode(QtWidgets.QGraphicsView.NoDrag)

        self.img = None
        self.pixmap_item = None
        self.img_w, self.img_h = 1, 1

        self.current_class = 0
        self.class_names = []
        self.class_colors = []

        self.mode = "rectangle"

        # states
        self.drawing = False
        self.start = None
        self.temp_rect = None
        self.points = []
        self.temp_points = []
        self.lasso_poly = None
        self.lasso_path = None

        self.setTransformationAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorUnderMouse)

    def load_image(self, path):
        self.scene.clear()
        # Reset drawing states
        self.drawing = False
        self.start = None
        self.temp_rect = None
        self.points = []
        self.temp_points = []
        self.lasso_poly = None
        self.lasso_path = None
        if hasattr(self, "lasso_item"):
            del self.lasso_item # Ensure lasso_item is cleared if it exists

        self.img = cv2.cvtColor(cv2.imread(path), cv2.COLOR_BGR2RGB)
        self.img_h, self.img_w, _ = self.img.shape
        qimg = QtGui.QImage(self.img.data, self.img_w, self.img_h, 3*self.img_w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.pixmap_item = self.scene.addPixmap(pix)
        self.setSceneRect(QtCore.QRectF(pix.rect()))
        self.fitInView(self.sceneRect(), QtCore.Qt.KeepAspectRatio)

    def load_yolo_annotations(self, txt_path):
        if not os.path.exists(txt_path):
            return

        with open(txt_path, "r") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 5:
                    cls, xc, yc, ww, hh = map(float, parts)
                    cls = int(cls)

                    # Convert YOLO to pixel coordinates
                    x_center = xc * self.img_w
                    y_center = yc * self.img_h
                    width = ww * self.img_w
                    height = hh * self.img_h

                    x1 = x_center - (width / 2)
                    y1 = y_center - (height / 2)
                    x2 = x_center + (width / 2)
                    y2 = y_center + (height / 2)

                    rect = QtCore.QRectF(x1, y1, width, height)

                    if cls < len(self.class_names):
                        class_name = self.class_names[cls]
                        color = self.class_colors[cls]
                        box = BoxItem(rect, cls, class_name, (self.img_w, self.img_h), color)
                        self.scene.addItem(box)

    def clamp_rect(self, rect):
        x1, y1, x2, y2 = rect.left(), rect.top(), rect.right(), rect.bottom()
        x1, x2 = max(0, min(x1, self.img_w)), max(0, min(x2, self.img_w))
        y1, y2 = max(0, min(y1, self.img_h)), max(0, min(y2, self.img_h))
        return QtCore.QRectF(QtCore.QPointF(x1,y1), QtCore.QPointF(x2,y2)).normalized()

    def wheelEvent(self, event):
        if QtWidgets.QApplication.keyboardModifiers() == QtCore.Qt.ControlModifier:
            zoom = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.scale(zoom, zoom)
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        pos = self.mapToScene(event.pos())
        if event.button() == QtCore.Qt.LeftButton and self.img is not None:
            if self.mode == "rectangle":
                self.start = pos
                self.drawing = True
                self.temp_rect = QtWidgets.QGraphicsRectItem(QtCore.QRectF(pos, pos))
                pen = QtGui.QPen(QtCore.Qt.green, 5, QtCore.Qt.DashLine)
                pen.setCosmetic(True)
                self.temp_rect.setPen(pen)
                self.scene.addItem(self.temp_rect)

            elif self.mode == "points":
                self.points.append(pos)
                dot = self.scene.addEllipse(pos.x()-3, pos.y()-3, 6, 6,
                                            QtGui.QPen(QtCore.Qt.blue, 5), QtGui.QBrush(QtCore.Qt.blue))
                dot.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
                self.temp_points.append(dot)

            elif self.mode == "lasso":
                if not self.lasso_path:
                    self.lasso_path = QtGui.QPainterPath(pos)
                    self.lasso_poly = QtGui.QPolygonF([pos])
                else:
                    self.lasso_path.lineTo(pos)
                    self.lasso_poly.append(pos)
                pen = QtGui.QPen(QtCore.Qt.magenta, 5)
                pen.setCosmetic(True)
                if hasattr(self, "lasso_item"):
                    self.scene.removeItem(self.lasso_item)
                self.lasso_item = self.scene.addPath(self.lasso_path, pen)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.mode == "rectangle" and self.drawing and self.temp_rect:
            end = self.mapToScene(event.pos())
            rect = QtCore.QRectF(self.start, end).normalized()
            rect = self.clamp_rect(rect)
            self.temp_rect.setRect(rect)
        elif self.mode == "lasso" and self.lasso_path:
            pos = self.mapToScene(event.pos())
            self.lasso_path.lineTo(pos)
            self.lasso_poly.append(pos)
            pen = QtGui.QPen(QtCore.Qt.magenta, 5)
            pen.setCosmetic(True)
            self.scene.removeItem(self.lasso_item)
            self.lasso_item = self.scene.addPath(self.lasso_path, pen)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.mode == "rectangle" and self.drawing and self.temp_rect:
            end = self.mapToScene(event.pos())
            rect = self.clamp_rect(QtCore.QRectF(self.start, end).normalized())
            self.scene.removeItem(self.temp_rect)
            color = self.class_colors[self.current_class]
            box = BoxItem(rect, self.current_class, self.class_names[self.current_class],
                          (self.img_w, self.img_h), color)
            self.scene.addItem(box)
            self.drawing = False
            self.temp_rect = None
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if self.mode == "points" and event.key() == QtCore.Qt.Key_Return:
            if self.points:
                xs = [p.x() for p in self.points]
                ys = [p.y() for p in self.points]
                rect = self.clamp_rect(QtCore.QRectF(QtCore.QPointF(min(xs), min(ys)),
                                     QtCore.QPointF(max(xs), max(ys))))
                for d in self.temp_points:
                    self.scene.removeItem(d)
                self.points.clear()
                self.temp_points.clear()
                color = self.class_colors[self.current_class]
                box = BoxItem(rect, self.current_class, self.class_names[self.current_class],
                              (self.img_w, self.img_h), color)
                self.scene.addItem(box)

        elif self.mode == "lasso" and event.key() == QtCore.Qt.Key_Return:
            if self.lasso_poly and not self.lasso_poly.isEmpty():
                xs = [p.x() for p in self.lasso_poly]
                ys = [p.y() for p in self.lasso_poly]
                rect = self.clamp_rect(QtCore.QRectF(QtCore.QPointF(min(xs), min(ys)),
                                     QtCore.QPointF(max(xs), max(ys))))
                self.scene.removeItem(self.lasso_item)
                self.lasso_path = None
                self.lasso_poly = None
                color = self.class_colors[self.current_class]
                box = BoxItem(rect, self.current_class, self.class_names[self.current_class],
                              (self.img_w, self.img_h), color)
                self.scene.addItem(box)

        else:
            super().keyPressEvent(event)

    def export_yolo(self, txt_path):
        items = [i for i in self.scene.items() if isinstance(i, BoxItem)]
        with open(txt_path, "w") as f:
            for item in items:
                f.write(item.to_yolo() + "\n")

# ---- Main Window ----
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Annotator - Minimal")
        self.showMaximized()

        # Setup shortcuts
        self.shortcut_prev = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Left"), self)
        self.shortcut_prev.activated.connect(self.prev_image)
        self.shortcut_next = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Right"), self)
        self.shortcut_next.activated.connect(self.next_image)

        # canvas
        self.annotator = ImageAnnotator()

        # right menu
        panel = QtWidgets.QVBoxLayout()
        panel.setSpacing(20)

        open_btn = QtWidgets.QPushButton("open folder")
        open_btn.clicked.connect(self.open_folder)

        self.class_combo = QtWidgets.QComboBox()
        self.class_combo.addItems(["numberplate"])
        self.annotator.class_names = [""]
        self.annotator.class_colors = [QtGui.QColor("red"), QtGui.QColor("blue"), QtGui.QColor("green")]
        self.class_combo.currentIndexChanged.connect(self.change_class)

        add_class_btn = QtWidgets.QPushButton("Add Class")
        add_class_btn.clicked.connect(self.add_new_class)

        next_btn = QtWidgets.QPushButton("Next (Ctrl+Right)")
        prev_btn = QtWidgets.QPushButton("Previous (Ctrl+Left)")
        next_btn.clicked.connect(self.next_image)
        prev_btn.clicked.connect(self.prev_image)

        mode_label = QtWidgets.QLabel("Mode:")
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItems(["rectangle", "points", "lasso"])
        self.mode_combo.currentTextChanged.connect(self.change_mode)

        quit_btn = QtWidgets.QPushButton("QUIT")
        quit_btn.clicked.connect(self.close)

        for w in [open_btn, self.class_combo, add_class_btn, next_btn, prev_btn, mode_label, self.mode_combo, quit_btn]:
            w.setStyleSheet("font-size:24px; background:white; color:black; padding:10px;")
            panel.addWidget(w)

        panel.addStretch()
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(panel)
        right_widget.setStyleSheet("background-color:black;")

        splitter = QtWidgets.QSplitter()
        splitter.addWidget(self.annotator)
        splitter.addWidget(right_widget)
        splitter.setSizes([1600,300])

        self.setCentralWidget(splitter)

        self.img_files, self.idx = [], 0
        last_dir = load_last_dir()
        if last_dir:
            self.load_folder(last_dir)

    def change_class(self):
        self.annotator.current_class = self.class_combo.currentIndex()

    def add_new_class(self):
        class_name, ok = QtWidgets.QInputDialog.getText(self, "Add New Class", "Enter class name:")
        if ok and class_name:
            if class_name not in self.annotator.class_names:
                self.annotator.class_names.append(class_name)
                self.class_combo.addItem(class_name)
                # Generate a random color for the new class
                color = QtGui.QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                self.annotator.class_colors.append(color)
                self.class_combo.setCurrentIndex(len(self.annotator.class_names) - 1) # Select the new class
            else:
                QtWidgets.QMessageBox.warning(self, "Class Exists", f"Class '{class_name}' already exists.")

    def change_mode(self, mode):
        self.annotator.mode = mode

    def open_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder: self.load_folder(folder)

    def load_folder(self, folder):
        save_last_dir(folder)
        self.img_files = [os.path.join(folder,f) for f in os.listdir(folder)
                          if f.lower().endswith((".jpg",".png",".jpeg"))]
        self.img_files.sort()
        self.idx = 0
        if self.img_files:
            img_path = self.img_files[self.idx]
            self.annotator.load_image(img_path)
            txt_path = os.path.splitext(img_path)[0] + ".txt"
            self.annotator.load_yolo_annotations(txt_path)

    def save_current(self):
        if not self.img_files: return
        img_path = self.img_files[self.idx]
        txt_path = os.path.splitext(img_path)[0] + ".txt"
        self.annotator.export_yolo(txt_path)

    def next_image(self):
        if self.idx+1 < len(self.img_files):
            self.save_current()
            self.idx += 1
            img_path = self.img_files[self.idx]
            self.annotator.load_image(img_path)
            txt_path = os.path.splitext(img_path)[0] + ".txt"
            self.annotator.load_yolo_annotations(txt_path)

    def prev_image(self):
        if self.idx > 0:
            self.save_current()
            self.idx -= 1
            img_path = self.img_files[self.idx]
            self.annotator.load_image(img_path)
            txt_path = os.path.splitext(img_path)[0] + ".txt"
            self.annotator.load_yolo_annotations(txt_path)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mw = MainWindow()
    mw.show()
    sys.exit(app.exec_())
