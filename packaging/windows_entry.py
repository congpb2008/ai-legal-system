import os
import sys

# Relative paths also support redirected Windows Documents folders.
if getattr(sys, 'frozen', False):
    # Windowed executables have no console streams. HTTP/TLS libraries still
    # expect writable streams when a client disconnects or aborts a handshake.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w')
    for variable, folder in [('TCL_LIBRARY', '_tcl_data'), ('TK_LIBRARY', '_tk_data')]:
        target = os.path.join(sys._MEIPASS, folder)
        try:
            target = os.path.relpath(target)
        except ValueError:
            pass
        os.environ[variable] = target

from legal_platform.desktop import main

if __name__ == '__main__':
    try:
        main()
    except Exception:
        import logging
        from pathlib import Path
        from legal_platform.paths import data_root
        folder = data_root() / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        import traceback
        (folder / 'startup-error.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise SystemExit(1)
