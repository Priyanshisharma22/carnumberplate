import sys
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

PX_PER_METER = 10
GRID_SIZE = 5
INTER_SIZE = 120


class Road:
    def __init__(self, points, width=6, rid=0):
        self.points = points
        self.width = width
        self.id = rid


class Intersection:
    def __init__(self, x, y, iid):
        self.x = x
        self.y = y
        self.id = iid
        self.phase = 0
        self.timer = 0
        self.greenTime = 15
        self.connectedRoads = []
        self.directions = []


class Canvas(QWidget):
    def __init__(self):
        super().__init__()

        # world movement & zoom
        self.offset = QPointF(0, 0)
        self.zoom = 0.1

        # Tools
        self.currentTool = "select"
        self.snapToGrid = True
        self.roadPoints = []

        # Data
        self.roads = []
        self.intersections = []

        # States
        self.isPanning = False
        self.lastMousePos = None
        self.selectedObject = None
        self.hoverObject = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        # Initialize default map
        self.initializeDefaultMap()

    # -----------------------------
    # WORLD COORDINATE CONVERSION
    # -----------------------------
    def toWorld(self, pos):
        return QPointF(
            pos.x() / self.zoom + self.offset.x(),
            pos.y() / self.zoom + self.offset.y()
        )

    def toScreen(self, pos):
        return QPointF(
            (pos.x() - self.offset.x()) * self.zoom,
            (pos.y() - self.offset.y()) * self.zoom
        )

    # -----------------------------
    # GRID SNAPPING
    # -----------------------------
    def snapPoint(self, p):
        if not self.snapToGrid:
            return p
        gx = GRID_SIZE * PX_PER_METER
        x = round(p.x() / gx) * gx
        y = round(p.y() / gx) * gx
        return QPointF(x, y)

    # -----------------------------
    # DEFAULT MAP
    # -----------------------------
    def initializeDefaultMap(self):
        def addRoad(p1, p2):
            self.roads.append(Road([QPointF(*p1), QPointF(*p2)], rid=len(self.roads)))

        addRoad((2000 * PX_PER_METER, 3000 * PX_PER_METER),
                (8000 * PX_PER_METER, 3000 * PX_PER_METER))
        addRoad((5000 * PX_PER_METER, 1000 * PX_PER_METER),
                (5000 * PX_PER_METER, 9000 * PX_PER_METER))
        addRoad((2000 * PX_PER_METER, 7000 * PX_PER_METER),
                (8000 * PX_PER_METER, 7000 * PX_PER_METER))

        self.createIntersectionsFromRoads()

    # -----------------------------
    # INTERSECTION DETECTION (Simplified)
    # -----------------------------
    def createIntersectionsFromRoads(self):
        self.intersections.clear()

        for i, r1 in enumerate(self.roads):
            for j, r2 in enumerate(self.roads):
                if i >= j:
                    continue

                p1, p2 = r1.points[0], r1.points[-1]
                p3, p4 = r2.points[0], r2.points[-1]

                inter = self.segmentIntersection(p1, p2, p3, p4)
                if inter:
                    self.intersections.append(
                        Intersection(inter.x(), inter.y(), len(self.intersections))
                    )

    def segmentIntersection(self, A, B, C, D):
        a1 = B.y() - A.y()
        b1 = A.x() - B.x()
        c1 = a1 * A.x() + b1 * A.y()

        a2 = D.y() - C.y()
        b2 = C.x() - D.x()
        c2 = a2 * C.x() + b2 * C.y()

        det = a1 * b2 - a2 * b1
        if abs(det) < 1e-6:
            return None

        x = (b2 * c1 - b1 * c2) / det
        y = (a1 * c2 - a2 * c1) / det

        if min(A.x(), B.x()) <= x <= max(A.x(), B.x()) and \
           min(C.x(), D.x()) <= x <= max(C.x(), D.x()):
            return QPointF(x, y)

        return None

    # -----------------------------
    # PAINT EVENT
    # -----------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#34495e"))
        painter.setRenderHint(QPainter.Antialiasing)

        self.drawGrid(painter)
        self.drawRoads(painter)
        self.drawIntersections(painter)
        self.drawRoadPreview(painter)

    # -----------------------------
    # DRAW GRID (FIXED)
    # -----------------------------
    def drawGrid(self, painter):
        if not self.snapToGrid:
            return

        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        gx = GRID_SIZE * PX_PER_METER

        left = self.offset.x()
        right = self.offset.x() + self.width() / self.zoom
        top = self.offset.y()
        bottom = self.offset.y() + self.height() / self.zoom

        x = int(left / gx) * gx
        while x < right:
            sx = (x - self.offset.x()) * self.zoom
            painter.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            x += gx

        y = int(top / gx) * gx
        while y < bottom:
            sy = (y - self.offset.y()) * self.zoom
            painter.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            y += gx

    # -----------------------------
    # DRAW ROADS
    # -----------------------------
    def drawRoads(self, painter):
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2c3e50"))

        for road in self.roads:
            poly = QPolygonF()
            for p in road.points:
                poly.append(self.toScreen(p))
            painter.drawPolyline(poly)

    # -----------------------------
    # DRAW INTERSECTIONS
    # -----------------------------
    def drawIntersections(self, painter):
        painter.setBrush(QColor("#c0392b"))
        painter.setPen(QPen(Qt.black, 2))

        for inter in self.intersections:
            rect = QRectF(
                (inter.x - INTER_SIZE/2 - self.offset.x()) * self.zoom,
                (inter.y - INTER_SIZE/2 - self.offset.y()) * self.zoom,
                INTER_SIZE * self.zoom,
                INTER_SIZE * self.zoom
            )
            painter.drawRect(rect)

    # -----------------------------
    # DRAW ROAD PREVIEW
    # -----------------------------
    def drawRoadPreview(self, painter):
        if self.currentTool != "road" or len(self.roadPoints) == 0:
            return
        
        painter.setPen(QPen(QColor("#3498db"), 3))

        for i in range(len(self.roadPoints)-1):
            p1 = self.toScreen(self.roadPoints[i])
            p2 = self.toScreen(self.roadPoints[i+1])
            painter.drawLine(p1, p2)

    # -----------------------------
    # MOUSE EVENTS
    # -----------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.isPanning = True
            self.lastMousePos = e.pos()
            return

        world = self.snapPoint(self.toWorld(e.pos()))

        if self.currentTool == "road":
            if not self.roadPoints:
                self.roadPoints.append(world)
            else:
                last = self.roadPoints[-1]
                if (world - last).manhattanLength() < 10:
                    if len(self.roadPoints) >= 2:
                        self.roads.append(Road(self.roadPoints.copy(), rid=len(self.roads)))
                        self.createIntersectionsFromRoads()
                    self.roadPoints.clear()
                else:
                    self.roadPoints.append(world)

        self.update()

    def mouseMoveEvent(self, e):
        if self.isPanning:
            delta = (e.pos() - self.lastMousePos) / self.zoom
            self.offset -= delta
            self.lastMousePos = e.pos()
            self.update()
            return

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MiddleButton:
            self.isPanning = False

    # -----------------------------
    # WHEEL EVENT (ZOOM)
    # -----------------------------
    def wheelEvent(self, e):
        oldZoom = self.zoom
        if e.angleDelta().y() > 0:
            self.zoom = min(1.0, self.zoom * 1.1)
        else:
            self.zoom = max(0.05, self.zoom / 1.1)

        # Zoom towards mouse
        before = self.toWorld(e.pos())
        after = self.toWorld(e.pos())
        self.offset += (before - after)

        self.update()

    # -----------------------------
    # KEYBOARD
    # -----------------------------
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.currentTool = "select"
            self.roadPoints.clear()
            self.update()


class TrafficSimWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traffic Simulator - PyQt5")
        self.resize(1200, 800)

        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)

        self.createToolbar()

    def createToolbar(self):
        tb = QToolBar()
        self.addToolBar(tb)

        def addBtn(name, tool):
            btn = QAction(name, self)
            btn.triggered.connect(lambda: self.setTool(tool))
            tb.addAction(btn)

        addBtn("Select", "select")
        addBtn("Draw Road", "road")
        addBtn("Add Intersection", "intersection")
        addBtn("Delete", "delete")

    def setTool(self, t):
        self.canvas.currentTool = t
        self.canvas.roadPoints.clear()
        self.canvas.update()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TrafficSimWindow()
    win.show()
    sys.exit(app.exec_())
