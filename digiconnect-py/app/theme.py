"""Colour themes: dark (default) and light, blue accent. `C` and `NET_COLOR` are updated in place by set_theme()."""

_COMMON = dict(dstar="#f2b94b", c4fm="#f276b8", pink="#f276b8")

PALETTES = {
    "dark": dict(
        bg="#0b1220", panel="#111a2e", panel2="#152139", border="#243452", text="#e8eefb", muted="#8493b4",
        accent="#2f9bff", accent2="#1f6fd1", on_accent="#04122a", field="#0a101d",
        dmr="#5db0ff", echo="#35d0c0", asl="#e0a8ff", nxdn="#ff8a5c", p25="#9bd84e", m17="#8ea6ff", dstar="#f2b94b", c4fm="#f276b8", green="#47d39b", green_bd="#2b6e5b", amber="#f5c451", red="#ff5d6c", pink="#f276b8",
        rail="#0d1527", footer="#09101c", mixer="#0e172a", dock_a="#14274a", dock_b="#111a2e",
        btn="#172440", btn_hover="#1f3157", btn_dis="#111b31", btn_dis_fg="#5d6c8f",
        primary_hover="#58b0ff", primary_dis="#244067", primary_dis_fg="#7f95bb",
        sel="#1c3a66", tint="#14284a", tint_bd="#2b4a7d",
        danger="#3a1a2a", danger_bd="#7a2e48", ptt="#16365a", ptt_bd="#24527f", ptt_dis="#13253f", ptt_dis_fg="#4a6486",
        latch="#1a2b4d", latch_bd="#2c4575", latch_dis="#111d36", latch_dis_fg="#4a5f88",
        tab_on="#183a6b", rail_hover="#1a2a4a", rail_on="#21386a", groove="#27385c", scroll="#2f4270", sep="#172440", hover_row="#15233f",
        card_pink="#2a1a33", card_pink_bd="#7a3a74", card_amber="#47391a", card_green="#12342e", card_green_bd="#2c7a64",
        toast="#14284a", avatar="#21386a", progress="#060a14", tip_bg="#ffffff", tip_fg="#111111", icon="#b3c1e0",
    ),
    "light": dict(
        bg="#eef2f8", panel="#ffffff", panel2="#f6f8fc", border="#cfd9e8", text="#13203a", muted="#5a6a88",
        accent="#1769d6", accent2="#124fa3", on_accent="#ffffff", field="#ffffff",
        dmr="#1769d6", echo="#0b8f82", asl="#8a3fc2", nxdn="#c4551c", p25="#5f8f12", m17="#4a63d6", dstar="#b36f00", c4fm="#c42d80", green="#1b9a68", green_bd="#8fd1b5", amber="#b07a00", red="#d03545", pink="#c42d80",
        rail="#e3e9f3", footer="#e3e9f3", mixer="#e9eef6", dock_a="#e3edfb", dock_b="#ffffff",
        btn="#e6edf8", btn_hover="#d8e3f4", btn_dis="#eef2f8", btn_dis_fg="#9aa7c0",
        primary_hover="#2f80ea", primary_dis="#b9cdea", primary_dis_fg="#ffffff",
        sel="#d3e4fb", tint="#e3eefc", tint_bd="#a9c6ee",
        danger="#fde6ea", danger_bd="#e39aa7", ptt="#d6e6fb", ptt_bd="#8db6ec", ptt_dis="#e8eef8", ptt_dis_fg="#9aa7c0",
        latch="#e3ecf9", latch_bd="#a9c0e6", latch_dis="#eef2f8", latch_dis_fg="#9aa7c0",
        tab_on="#d3e4fb", rail_hover="#d6e0f0", rail_on="#c4d7f3", groove="#c3cfe3", scroll="#b2c0d8", sep="#e1e8f3", hover_row="#eef3fb",
        card_pink="#fbe6f1", card_pink_bd="#e08bb8", card_amber="#fcf0cf", card_green="#dff5ec", card_green_bd="#7cc9a8",
        toast="#ffffff", avatar="#c4d7f3", progress="#d5deec", tip_bg="#13203a", tip_fg="#ffffff", icon="#3a4a6c",
    ),
}
THEMES = ("dark", "light")

C: dict = dict(PALETTES["dark"])
NET_COLOR: dict = {}
current = "dark"


def set_theme(name: str) -> str:
    """Switches the palette in place (every module keeps the same dict objects)."""
    global current
    name = name if name in PALETTES else "dark"
    C.clear(); C.update(PALETTES[name]); current = name
    NET_COLOR.clear(); NET_COLOR.update({"DMR": C["dmr"], "D-Star": C["dstar"], "EchoLink": C["echo"], "AllStar": C["asl"], "C4FM": C["c4fm"], "NXDN": C["nxdn"], "P25": C["p25"], "M17": C["m17"]})
    return name


set_theme("dark")


def qss(font_px: int = 14) -> str:
    c = C
    return f"""
* {{ font-family: "Segoe UI","Inter","SF Pro Text","Noto Sans",sans-serif; font-size:{font_px-2}px; color:{c['text']}; }}
QMainWindow, #root {{ background:{c['bg']}; }}
QDialog, QMessageBox, QInputDialog {{ background:{c['panel']}; }}
QToolTip {{ background:{c['tip_bg']}; color:{c['tip_fg']}; border:1px solid {c['border']}; padding:3px 6px; }}
#rail {{ background:{c['rail']}; border-right:1px solid {c['green_bd']}; }}
#topbar {{ background:{c['bg']}; border-bottom:1px solid {c['green_bd']}; }}
#footer {{ background:{c['footer']}; border-top:1px solid {c['border']}; }}
#footer QLabel {{ color:{c['muted']}; font-size:{font_px-4}px; }}
#footer QFrame#chip {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:8px; }}
#footer QFrame#chip QLabel {{ background:transparent; }}
#footer QLabel[chipt="true"] {{ color:{c['muted']}; font-size:{font_px-6}px; font-weight:600; letter-spacing:1px; }}
#footer QLabel[chipv="true"] {{ color:{c['text']}; font-size:{font_px-3}px; font-weight:700; }}
#footer QLabel[chipv="true"][tone="green"] {{ color:{c['green']}; }}
#footer QLabel[chipv="true"][tone="amber"] {{ color:{c['amber']}; }}
#footer QLabel[chipv="true"][tone="red"] {{ color:{c['red']}; }}
#footer QLabel[brand="true"] {{ color:{c['text']}; font-size:{font_px-1}px; font-weight:800; }}
.muted, QLabel[muted="true"] {{ color:{c['muted']}; }}
QLabel[h1="true"] {{ font-size:{font_px+10}px; font-weight:700; }}
QLabel[eyebrow="true"] {{ color:{c['accent']}; font-size:{font_px-5}px; font-weight:700; letter-spacing:1px; }}
QLabel[tone="accent"] {{ color:{c['accent']}; font-weight:700; }}
QLabel[tone="amber"] {{ color:{c['amber']}; }}
QLabel[tone="echo"] {{ color:{c['echo']}; }}
QLabel[net="DMR"] {{ color:{c['dmr']}; font-weight:700; }}
QLabel[net="D-Star"] {{ color:{c['dstar']}; font-weight:700; }}
QLabel[net="EchoLink"] {{ color:{c['echo']}; font-weight:700; }}
QLabel[net="AllStar"] {{ color:{c['asl']}; font-weight:700; }}
QLabel[net="C4FM"] {{ color:{c['c4fm']}; font-weight:700; }}
QLabel[net="NXDN"] {{ color:{c['nxdn']}; font-weight:700; }}
QLabel[net="P25"] {{ color:{c['p25']}; font-weight:700; }}
QLabel[net="M17"] {{ color:{c['m17']}; font-weight:700; }}
QLabel#toast {{ background:{c['toast']}; border:1px solid {c['green']}; border-radius:10px; padding:10px 16px; }}
QLabel#avatar {{ background:{c['avatar']}; border-radius:18px; font-weight:700; }}
QLabel[section="true"] {{ color:{c['muted']}; font-size:{font_px-5}px; font-weight:700; letter-spacing:1.5px; }}
#panel, #drawer, #dock, #mixer {{ background:{c['panel']}; border:1px solid {c['green_bd']}; border-radius:14px; }}
#drawer {{ border-radius:0; border-top:none; border-bottom:none; border-right:none; }}
#dock {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {c['dock_a']},stop:1 {c['dock_b']}); }}
#mixer {{ border-radius:0; border-left:none; border-right:none; background:{c['mixer']}; }}
QFrame#card {{ background:{c['panel2']}; border:1px solid {c['green_bd']}; border-radius:12px; }}
QFrame#card[sel="true"] {{ border:2px solid {c['accent']}; }}
QFrame#card[state="pink"] {{ background:{c['card_pink']}; border-color:{c['card_pink_bd']}; }}
QFrame#card[state="amber"] {{ background:{c['card_amber']}; border-color:{c['amber']}; }}
QFrame#card[state="green"] {{ background:{c['card_green']}; border-color:{c['card_green_bd']}; }}
QFrame#tx {{ background:{c['field']}; border:1px solid {c['border']}; border-radius:10px; }}
QFrame#note {{ background:{c['tint']}; border:1px solid {c['tint_bd']}; border-radius:8px; }}
QPushButton {{ background:{c['btn']}; border:1px solid {c['border']}; border-radius:9px; padding:6px 12px; }}
QPushButton:hover {{ background:{c['btn_hover']}; }}
QPushButton:disabled {{ color:{c['btn_dis_fg']}; background:{c['btn_dis']}; }}
QPushButton[kind="primary"] {{ background:{c['accent']}; border-color:{c['accent']}; color:{c['on_accent']}; font-weight:700; }}
QPushButton[kind="primary"]:hover {{ background:{c['primary_hover']}; }}
QPushButton[kind="primary"]:disabled {{ background:{c['primary_dis']}; color:{c['primary_dis_fg']}; border-color:{c['primary_dis']}; }}
QPushButton[kind="seg"] {{ background:transparent; }}
QPushButton[kind="seg"]:checked {{ background:{c['sel']}; border-color:{c['accent']}; }}
QPushButton[kind="danger"] {{ background:{c['danger']}; border-color:{c['danger_bd']}; }}
QPushButton[kind="ptt"] {{ background:{c['ptt']}; border:1px solid {c['ptt_bd']}; font-weight:700; min-height:40px; }}
QPushButton[kind="ptt"]:disabled {{ background:{c['ptt_dis']}; color:{c['ptt_dis_fg']}; }}
QPushButton[kind="ptt"]:pressed, QPushButton[kind="ptt"]:checked {{ background:{c['red']}; color:#ffffff; }}
QPushButton[kind="latch"] {{ background:{c['latch']}; border:1px solid {c['green_bd']}; font-weight:700; min-height:40px; }}
QPushButton[kind="latch"]:disabled {{ background:{c['latch_dis']}; color:{c['latch_dis_fg']}; }}
QPushButton[kind="latch"]:checked {{ background:{c['red']}; color:#ffffff; }}
QPushButton[kind="tab"] {{ background:{c['panel']}; border:1px solid {c['green_bd']}; border-radius:12px; padding:9px 18px; font-size:{font_px-1}px; }}
QPushButton[kind="tab"]:checked {{ background:{c['tab_on']}; border:2px solid {c['green']}; }}
QPushButton[kind="tab"][closed="true"] {{ color:{c['muted']}; border:1px dashed {c['muted']}; }}
QFrame#card[closed="true"] {{ background:{c['panel']}; border:1px dashed {c['muted']}; }}
QPushButton[kind="rail"] {{ background:transparent; border:none; border-radius:10px; padding:0; }}
QPushButton[kind="rail"]:hover {{ background:{c['rail_hover']}; }}
QPushButton[kind="rail"]:checked {{ background:{c['rail_on']}; }}
QPushButton[kind="star"] {{ background:transparent; border:none; font-size:{font_px+4}px; padding:0 6px; color:{c['accent']}; }}
QLineEdit, QComboBox, QDateEdit, QDateTimeEdit, QPlainTextEdit, QSpinBox {{
  background:{c['field']}; border:1px solid {c['border']}; border-radius:9px; padding:8px 10px; selection-background-color:{c['accent2']}; selection-color:#ffffff; }}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border-color:{c['accent']}; }}
QComboBox::drop-down {{ border:none; width:22px; }}
QComboBox QAbstractItemView {{ background:{c['panel']}; border:1px solid {c['border']}; selection-background-color:{c['accent2']}; selection-color:#ffffff; }}
QCheckBox::indicator {{ width:16px; height:16px; border-radius:4px; border:1px solid {c['border']}; background:{c['field']}; }}
QCheckBox::indicator:checked {{ background:{c['green']}; border-color:{c['green']}; }}
QSlider::groove:horizontal {{ height:4px; background:{c['groove']}; border-radius:2px; }}
QSlider::sub-page:horizontal {{ background:{c['green']}; border-radius:2px; }}
QSlider::handle:horizontal {{ background:{c['green']}; width:14px; height:14px; margin:-5px 0; border-radius:7px; }}
QProgressBar {{ background:{c['progress']}; border:none; border-radius:3px; }}
QProgressBar::chunk {{ background:{c['green']}; border-radius:3px; }}
QScrollArea {{ border:none; background:transparent; }}
QScrollArea > QWidget > QWidget {{ background:transparent; }}
QScrollBar:vertical {{ background:transparent; width:9px; }}
QScrollBar::handle:vertical {{ background:{c['scroll']}; border-radius:4px; min-height:30px; }}
QScrollBar:horizontal {{ background:transparent; height:9px; }}
QScrollBar::handle:horizontal {{ background:{c['scroll']}; border-radius:4px; min-width:30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height:0; width:0; }}
QListWidget {{ background:transparent; border:none; outline:none; }}
QListWidget::item {{ border-bottom:1px solid {c['sep']}; padding:10px 14px; }}
QListWidget::item:selected {{ background:{c['sel']}; }}
QListWidget::item:hover {{ background:{c['hover_row']}; }}
QTableWidget {{ background:{c['panel']}; border:1px solid {c['border']}; border-radius:12px; gridline-color:{c['sep']}; }}
QHeaderView::section {{ background:{c['panel2']}; color:{c['muted']}; border:none; padding:10px; }}
"""
