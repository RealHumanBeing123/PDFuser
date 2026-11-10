import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("PDFuser")
    win = MainWindow()
    win.show()
    # PDFs / folders passed on the command line (e.g. "Open with") are added right away
    if len(sys.argv) > 1:
        win.add_paths(sys.argv[1:])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
