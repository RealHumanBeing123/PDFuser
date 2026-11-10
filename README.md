# PDFuser

A simple Windows app for merging PDF files. I made this because the online ones either cost money (adobe cough cough) or just are difficult to use due to a bad UI or fishy download links once you've made the file.

## Features

- **Import a folder** of PDFs, or **add files by hand** (Add PDFs button, or drag and drop from Windows Explorer - files and folders both work).
- **Automatic ordering.** When importing, PDFUser looks for an order in the file names and uses it:
  - numbers: `1, 2, 3 ... 10` (compared as numbers, so `2` comes before `10`)
  - chapters / parts: `Chapter 1`, `Ch2`, `Part III`, `Section four`
  - letters: `a, b, c`, `Appendix_A`
  - nothing recognisable: sorted by name, and the app tells you so
- **Reorder anything** by dragging rows, or with the ▲ / ▼ buttons (Alt+Up / Alt+Down). "Re-detect order" re-sorts using the file names.
- **Remove pages** from any file (select it, *Edit pages...* or double-click): click thumbnails to mark them, or type ranges like `1-2, 5, 9-`.
- Optional bookmark per file in the merged PDF.
- Password-protected or damaged files are skipped with a message instead of breaking the merge.

## Run from source

```
pip install -r requirements.txt
python run.py            # optionally: python run.py file1.pdf some_folder
```

## Build the Windows exe

On Windows, run `build_exe.bat` (produces `dist\PDFuser.exe`). On GitHub, the **Build** workflow does this automatically; download `PDFuser-windows` from the run's artifacts, or push a tag like `v0.1.0` to attach the exe to a release.

## Tests

```
pip install -r requirements-dev.txt
python -m pytest
```

## Layout

- `pdfuser/core/ordering.py` - order detection
- `pdfuser/core/pdfops.py` - reading and merging (pypdf)
- `pdfuser/ui/` - Qt (PySide6) interface; page thumbnails use pypdfium2

License: MIT
