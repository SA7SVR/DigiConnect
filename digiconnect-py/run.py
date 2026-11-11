import sys
from app.qt import QtWidgets, BINDING
from app.theme import qss
from app.context import Ctx
from app.store import Store
from app.engine_client import EngineClient, find_engine
from app.ui.main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv); app.setApplicationName("DigiConnect"); app.setOrganizationName("HELLASZone")
    store = Store(); path = find_engine()
    ctx = Ctx(store, EngineClient(path, store) if path else None); app.setStyleSheet(qss(ctx.store.settings["text_size"]))
    w = MainWindow(ctx); w.show(); sys.exit(app.exec())


if __name__ == "__main__":
    main()
