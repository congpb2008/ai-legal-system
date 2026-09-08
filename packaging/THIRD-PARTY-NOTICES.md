# Third-party components and release licensing

The Windows bundle includes Python and its standard library (including Tcl/Tk), PyMuPDF/MuPDF, Pydantic, Cheroot, Cryptography, Pillow, pytesseract, pywin32 and their dependencies. Version pins are in `requirements.lock` and `packaging/requirements-build.lock`. PyInstaller packages the executable. Tesseract itself is optional and is not included in this Windows download.

PyMuPDF/MuPDF is offered under AGPL and commercial licensing. The repository owner's product license is still undecided; this implementation does not choose it on the owner's behalf. Resolve the intended product distribution and dependency licensing before distributing to customers. See [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html) and the license files accompanying the installed distributions.

The supplied executable is an unsigned development/pilot build. Code signing, an installer publisher identity, and the owner's license decision remain release work. Microsoft Visual C++ runtime components may be included where required by PyMuPDF; they retain their original terms.

Build mechanics follow [PyInstaller's documentation](https://pyinstaller.org/en/stable/spec-files.html). Windows service support uses [pywin32's service utilities](https://github.com/mhammond/pywin32/blob/main/win32/Lib/win32serviceutil.py).
