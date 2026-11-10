"""Entry point used for running from source and for the PyInstaller build."""
import sys

from pdfuser.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
