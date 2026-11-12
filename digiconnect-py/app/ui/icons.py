from ..qt import QtGui, QtCore, Qt
from ..theme import C

def icon(name: str, color=None, size=22) -> QtGui.QIcon:
    color = color or (C["red"] if name == "speaker_off" else C["icon"])
    pm = QtGui.QPixmap(size * 2, size * 2); pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    p.scale(2, 2)
    pen = QtGui.QPen(QtGui.QColor(color), 1.6); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    R = QtCore.QRectF
    s = size
    if name == "grid":
        for x in (4, 12):
            for y in (4, 12): p.drawRoundedRect(R(x, y, 6, 6), 1.5, 1.5)
    elif name == "plus":
        p.drawLine(11, 5, 11, 17); p.drawLine(5, 11, 17, 11)
    elif name == "doc":
        p.drawRoundedRect(R(5, 3, 12, 16), 2, 2)
        for y in (8, 11, 14): p.drawLine(8, y, 14, y)
    elif name == "bars":
        p.drawLine(4, 18, 18, 18)
        for x, h in ((6, 6), (11, 10), (16, 13)): p.drawLine(x, 18, x, 18 - h)
    elif name == "clock":
        p.drawEllipse(R(4, 4, 14, 14)); p.drawLine(11, 7, 11, 11); p.drawLine(11, 11, 14, 13)
    elif name == "headphones":
        path = QtGui.QPainterPath(); path.moveTo(4, 14); path.lineTo(4, 11); path.arcTo(R(4, 3, 14, 16), 180, -180); path.lineTo(18, 14)
        p.drawPath(path); p.drawRoundedRect(R(3.5, 12, 4, 6), 1.5, 1.5); p.drawRoundedRect(R(14.5, 12, 4, 6), 1.5, 1.5)
    elif name == "circle":
        p.drawEllipse(R(5, 5, 12, 12))
    elif name == "download":
        p.drawLine(11, 4, 11, 14); p.drawLine(7, 10, 11, 14); p.drawLine(15, 10, 11, 14); p.drawLine(5, 18, 17, 18)
    elif name == "help":
        p.drawEllipse(R(4, 4, 14, 14)); f = p.font(); f.setPixelSize(11); f.setBold(True); p.setFont(f)
        p.drawText(R(4, 4, 14, 14), Qt.AlignmentFlag.AlignCenter, "?")
    elif name == "gear":
        p.drawEllipse(R(8, 8, 6, 6))
        import math
        for i in range(8):
            a = i * math.pi / 4
            p.drawLine(QtCore.QPointF(11 + 5 * math.cos(a), 11 + 5 * math.sin(a)), QtCore.QPointF(11 + 8 * math.cos(a), 11 + 8 * math.sin(a)))
    elif name == "mic":
        p.drawRoundedRect(R(8, 3, 6, 10), 3, 3); p.drawArc(R(5, 7, 12, 9), 0, -180 * 16); p.drawLine(11, 16, 11, 19)
    elif name == "lock":
        p.drawRoundedRect(R(5, 10, 12, 8), 2, 2); p.drawArc(R(7, 3, 8, 12), 0, 180 * 16)
    elif name == "power":
        p.drawArc(R(5, 5, 12, 12), 120 * 16, -300 * 16); p.drawLine(11, 3, 11, 10)
    elif name == "star":
        pass
    elif name == "pencil":
        p.drawLine(5, 17, 6, 13); p.drawLine(6, 13, 15, 4); p.drawLine(15, 4, 18, 7); p.drawLine(18, 7, 9, 16); p.drawLine(9, 16, 5, 17)
    elif name == "search":
        p.drawEllipse(R(4, 4, 10, 10)); p.drawLine(13, 13, 18, 18)
    elif name == "close":
        p.drawLine(6, 6, 16, 16); p.drawLine(16, 6, 6, 16)
    elif name == "speaker":
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(4, 9), QtCore.QPointF(8, 9), QtCore.QPointF(12, 5), QtCore.QPointF(12, 17), QtCore.QPointF(8, 13), QtCore.QPointF(4, 13)]))
        p.drawArc(R(11, 7, 6, 8), -60 * 16, 120 * 16)
    elif name == "speaker_off":                      # muted: the same speaker, no sound waves, a cross instead
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(3, 9), QtCore.QPointF(7, 9), QtCore.QPointF(11, 5), QtCore.QPointF(11, 17), QtCore.QPointF(7, 13), QtCore.QPointF(3, 13)]))
        p.drawLine(14, 8, 19, 14); p.drawLine(19, 8, 14, 14)
    p.end()
    return QtGui.QIcon(pm)


def dot(color: str, size=10) -> QtGui.QIcon:
    pm = QtGui.QPixmap(size * 2, size * 2); pm.fill(Qt.GlobalColor.transparent)
    p = QtGui.QPainter(pm); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing); p.setBrush(QtGui.QColor(color)); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(2, 2, size * 2 - 4, size * 2 - 4); p.end(); return QtGui.QIcon(pm)
