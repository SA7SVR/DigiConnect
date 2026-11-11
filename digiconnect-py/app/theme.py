"""Dark violet theme (original stylesheet, layout modelled on the reference screenshots)."""
C = dict(
    bg="#0a0c1b", panel="#10142a", panel2="#141935", border="#1f2547", text="#e9ebf8",
    muted="#7f86aa", accent="#8b7cf6", accent2="#6d5be0", field="#0b0e20",
    dmr="#9b8cf8", dstar="#f2b94b", echo="#4cc3f0", c4fm="#f276b8",
    green="#47d39b", amber="#f5c451", red="#ff5d6c", pink="#f276b8",
)
NET_COLOR = {"DMR": C["dmr"], "D-Star": C["dstar"], "EchoLink": C["echo"], "C4FM": C["c4fm"]}


def qss(font_px: int = 14) -> str:
    c = C
    return f"""
* {{ font-family: "Segoe UI","Inter","SF Pro Text","Noto Sans",sans-serif; font-size:{font_px-2}px; color:{c['text']}; }}
QMainWindow, #root {{ background:{c['bg']}; }}
QToolTip {{ background:#fff; color:#111; border:1px solid #bbb; padding:3px 6px; }}
#rail {{ background:#0c0f21; border-right:1px solid {c['border']}; }}
#topbar {{ background:{c['bg']}; border-bottom:1px solid {c['border']}; }}
#footer {{ background:#090b18; border-top:1px solid {c['border']}; }}
#footer QLabel {{ color:{c['muted']}; font-size:{font_px-4}px; }}
.muted, QLabel[muted="true"] {{ color:{c['muted']}; }}
QLabel[h1="true"] {{ font-size:{font_px+10}px; font-weight:700; }}
QLabel[eyebrow="true"] {{ color:{c['accent']}; font-size:{font_px-5}px; font-weight:700; letter-spacing:1px; }}
QLabel[section="true"] {{ color:{c['muted']}; font-size:{font_px-5}px; font-weight:700; letter-spacing:1.5px; }}
#panel, #drawer, #dock, #mixer {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:14px; }}
#drawer {{ border-radius:0; border-top:none; border-bottom:none; border-right:none; }}
#dock {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #1a1533,stop:1 #10142a); }}
#mixer {{ border-radius:0; border-left:none; border-right:none; background:#0d1024; }}
QFrame#card {{ background:{c['panel2']}; border:1px solid {c['border']}; border-radius:12px; }}
QFrame#card[sel="true"] {{ border:2px solid {c['accent']}; }}
QFrame#card[state="pink"] {{ background:#2a1630; border-color:#7a3a74; }}
QFrame#card[state="amber"] {{ background:#4a3a10; border-color:{c['amber']}; }}
QFrame#card[state="green"] {{ background:#12342e; border-color:#2c7a64; }}
QFrame#tx {{ background:{c['field']}; border:1px solid {c['border']}; border-radius:10px; }}
QFrame#note {{ background:#201a3d; border:1px solid #3a2f6b; border-radius:8px; }}
QPushButton {{ background:#171c3a; border:1px solid {c['border']}; border-radius:9px; padding:6px 12px; }}
QPushButton:hover {{ background:#1f2548; }}
QPushButton:disabled {{ color:#5a6088; background:#12162e; }}
QPushButton[kind="primary"] {{ background:{c['accent']}; border-color:{c['accent']}; color:#120c33; font-weight:700; }}
QPushButton[kind="primary"]:hover {{ background:#9d90fa; }}
QPushButton[kind="primary"]:disabled {{ background:#3b3470; color:#8d86c0; border-color:#3b3470; }}
QPushButton[kind="seg"] {{ background:transparent; }}
QPushButton[kind="seg"]:checked {{ background:#2a2358; border-color:{c['accent']}; }}
QPushButton[kind="danger"] {{ background:#3a1424; border-color:#7a2640; }}
QPushButton[kind="ptt"] {{ background:#16365a; border:1px solid #24527f; font-weight:700; min-height:40px; }}
QPushButton[kind="ptt"]:disabled {{ background:#13253f; color:#4a6486; }}
QPushButton[kind="ptt"]:pressed, QPushButton[kind="ptt"]:checked {{ background:{c['red']}; color:#2a0610; }}
QPushButton[kind="latch"] {{ background:#241b3d; border:1px solid #3a2f6b; font-weight:700; min-height:40px; }}
QPushButton[kind="latch"]:disabled {{ background:#171230; color:#4d4676; }}
QPushButton[kind="latch"]:checked {{ background:{c['red']}; color:#2a0610; }}
QPushButton[kind="tab"] {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:12px; padding:9px 18px; font-size:{font_px-1}px; }}
QPushButton[kind="tab"]:checked {{ background:#251f52; border-color:{c['accent']}; }}
QPushButton[kind="rail"] {{ background:transparent; border:none; border-radius:10px; padding:0; }}
QPushButton[kind="rail"]:hover {{ background:#1a1f40; }}
QPushButton[kind="rail"]:checked {{ background:#232a55; }}
QPushButton[kind="star"] {{ background:transparent; border:none; font-size:{font_px+4}px; padding:0 6px; color:{c['accent']}; }}
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit, QPlainTextEdit, QSpinBox {{
  background:{c['field']}; border:1px solid {c['border']}; border-radius:9px; padding:8px 10px; selection-background-color:{c['accent2']}; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color:{c['accent']}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{c['panel']}; border:1px solid {c['border']}; selection-background-color:{c['accent2']}; }}
QCheckBox::indicator {{ width:16px; height:16px; border-radius:4px; border:1px solid {c['border']}; background:{c['field']}; }}
QCheckBox::indicator:checked {{ background:{c['accent']}; border-color:{c['accent']}; }}
QSlider::groove:horizontal {{ height:4px; background:#262c52; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{c['accent']}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{c['accent']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QProgressBar {{ background:#05070f; border:none; height:5px; border-radius:2px; }}
QProgressBar::chunk {{ background:{c['green']}; border-radius:2px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:9px; }}
QScrollBar::handle:vertical {{ background:#2a3160; border-radius:4px; min-height:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QListWidget {{ background:transparent; border:none; outline:none; }}
QListWidget::item {{ border-bottom:1px solid #181d3b; padding:10px 14px; }}
QListWidget::item:selected {{ background:#201b47; }}
QListWidget::item:hover {{ background:#171c3c; }}
QTableWidget {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:12px; gridline-color:#181d3b; }}
QHeaderView::section {{ background:{c['panel2']}; color:{c['muted']}; border:none; padding:10px; }}
"""
