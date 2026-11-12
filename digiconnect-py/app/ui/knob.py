"""Microphone volume knob (potentiometer) with a live level meter. Same value as the slider in Settings / the station page:
a change in one place is applied to the settings and shown in all the others (through the audio bus)."""
import math
from ..qt import QtWidgets as W, QtCore, QtGui, Qt
from ..theme import C
from ..i18n import tr
from .audioblock import bus


class MicKnob(W.QWidget):
    START, SWEEP = 225, 270          # degrees: the knob turns from 7:30 o'clock over the top to 4:30 o'clock

    def __init__(self, ctx, size: int = 96, parent=None):
        super().__init__(parent); self.ctx = ctx; self._size = size
        self.setFixedSize(size + 12, size + 34); self.setCursor(Qt.CursorShape.PointingHandCursor); self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self._v = int(ctx.store.settings.get("mic_gain", 100)); self._level = 0.0; self._drag = None
        self.setToolTip(tr("Microphone volume") + " — " + tr("drag up/down, use the mouse wheel, or double-click for 100%"))
        bus().gain.connect(self._from_bus)
        self._t = QtCore.QTimer(self); self._t.setInterval(80); self._t.timeout.connect(self._poll); self._t.start()

    # ---- value ---------------------------------------------------------------
    def value(self) -> int: return self._v

    def set_value(self, v: int, from_user: bool = False):
        v = max(0, min(300, int(v)))
        if v == self._v: return
        self._v = v; self.update()
        if from_user: self.ctx.set_mic_gain(v); bus().gain.emit(v)

    def _from_bus(self, v):
        if v != self._v: self._v = max(0, min(300, int(v))); self.update()

    def _poll(self):
        try: lv = float(self.ctx.engine.mic_level())
        except Exception: lv = 0.0
        if abs(lv - self._level) > 0.01 or (lv == 0 and self._level): self._level = lv; self.update()

    # ---- input ---------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton: self._drag = (e.position().y(), self._v); self.setFocus()

    def mouseMoveEvent(self, e):
        if self._drag: self.set_value(self._drag[1] + (self._drag[0] - e.position().y()) * 1.5, True)

    def mouseReleaseEvent(self, e): self._drag = None

    def mouseDoubleClickEvent(self, e): self.set_value(100, True)

    def wheelEvent(self, e):
        self.set_value(self._v + (5 if e.angleDelta().y() > 0 else -5), True); e.accept()

    def keyPressEvent(self, e):
        d = {Qt.Key.Key_Up: 5, Qt.Key.Key_Right: 5, Qt.Key.Key_Down: -5, Qt.Key.Key_Left: -5}.get(e.key())
        if d: self.set_value(self._v + d, True)
        else: super().keyPressEvent(e)

    # ---- paint -----------------------------------------------------------------
    def paintEvent(self, _):
        p = QtGui.QPainter(self); p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        s = self._size; r = QtCore.QRectF(6, 6, s, s); inner = r.adjusted(10, 10, -10, -10)
        col = QtGui.QColor
        track = col(C["groove"]); boost = self._v > 100
        fill = col(C["amber"] if boost else C["green"])
        pen = QtGui.QPen(track, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap); p.setPen(pen)
        p.drawArc(r.adjusted(3, 3, -3, -3), int(self.START * 16), int(-self.SWEEP * 16))
        frac = self._v / 300.0
        pen.setColor(fill); p.setPen(pen)
        if frac > 0: p.drawArc(r.adjusted(3, 3, -3, -3), int(self.START * 16), int(-self.SWEEP * frac * 16))
        # 100 % tick
        a = math.radians(self.START - self.SWEEP / 3.0); c = r.center(); rad = s / 2 - 3
        p.setPen(QtGui.QPen(col(C["muted"]), 2)); p.drawLine(QtCore.QPointF(c.x() + (rad - 7) * math.cos(a), c.y() - (rad - 7) * math.sin(a)), QtCore.QPointF(c.x() + (rad + 5) * math.cos(a), c.y() - (rad + 5) * math.sin(a)))
        # knob body
        g = QtGui.QRadialGradient(inner.center().x() - 8, inner.center().y() - 10, s * 0.55); g.setColorAt(0, col(C["panel2"]).lighter(135)); g.setColorAt(1, col(C["panel"]))
        p.setPen(QtGui.QPen(col(C["green"]), 2)); p.setBrush(g); p.drawEllipse(inner)
        # pointer
        a = math.radians(self.START - self.SWEEP * frac); ir = inner.width() / 2
        p.setPen(QtGui.QPen(fill, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QtCore.QPointF(c.x() + ir * 0.42 * math.cos(a), c.y() - ir * 0.42 * math.sin(a)), QtCore.QPointF(c.x() + ir * 0.86 * math.cos(a), c.y() - ir * 0.86 * math.sin(a)))
        p.setPen(col(C["text"])); f = p.font(); f.setBold(True); f.setPixelSize(15); p.setFont(f)
        p.drawText(QtCore.QRectF(inner.x(), inner.center().y() - 2, inner.width(), 22), Qt.AlignmentFlag.AlignCenter, f"{self._v}%")
        # label + live level meter
        f.setBold(False); f.setPixelSize(11); p.setFont(f); p.setPen(col(C["muted"]))
        p.drawText(QtCore.QRectF(0, s + 4, self.width(), 14), Qt.AlignmentFlag.AlignCenter, "MIC")
        bar = QtCore.QRectF(8, s + 20, self.width() - 16, 6); p.setPen(Qt.PenStyle.NoPen); p.setBrush(col(C["groove"])); p.drawRoundedRect(bar, 3, 3)
        lv = max(0.0, min(1.0, self._level))
        if lv > 0:
            p.setBrush(col(C["red"] if lv > 0.9 else (C["amber"] if lv > 0.7 else C["green"]))); p.drawRoundedRect(QtCore.QRectF(bar.x(), bar.y(), bar.width() * lv, bar.height()), 3, 3)
