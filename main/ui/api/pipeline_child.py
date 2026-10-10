"""Run the unchanged research entry point; exit if the owning worker disappears.

The parent holds stdin open. EOF also happens on abrupt parent termination, so
an orphan inference process cannot keep rewriting reports after worker restart.
"""
import os
import runpy
import sys
import threading
import time


def parent_watchdog():
    try:
        if os.name == 'nt':
            # A blocking CRT read holds a Windows descriptor lock that NumPy's
            # extension initialization also needs. Poll the pipe without that lock.
            import ctypes
            import msvcrt
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(sys.stdin.fileno()))
            peek = ctypes.windll.kernel32.PeekNamedPipe
            while peek(handle, None, 0, None, None, None):
                time.sleep(.2)
        else:
            os.read(sys.stdin.fileno(), 1)
    finally:
        os._exit(75)


if __name__ == '__main__':
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    threading.Thread(target=parent_watchdog, daemon=True).start()
    runpy.run_path(script, run_name='__main__')
