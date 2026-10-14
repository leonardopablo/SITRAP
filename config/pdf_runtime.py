"""Load the Windows PDF runtime before PostgreSQL loads conflicting native DLLs."""

import ctypes
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Keep both the search directory and DLL loaded for the lifetime of the process.
_dll_directory_handles = []
_preloaded_libraries = []


def preload_windows_pdf_runtime(directories):
    if sys.platform != "win32" or not directories:
        return

    for value in directories.split(";"):
        if not value.strip():
            continue
        directory = Path(value.strip())
        pthread = directory / "libwinpthread-1.dll"
        if not directory.is_absolute() or not pthread.is_file():
            logger.warning("PDF runtime directory or libwinpthread-1.dll missing: %s", directory)
            continue
        try:
            handle = os.add_dll_directory(str(directory))
            try:
                library = ctypes.WinDLL(str(pthread))
            except OSError:
                handle.close()
                raise
        except OSError:
            logger.exception("Could not preload the Windows PDF runtime from %s", directory)
            continue
        _dll_directory_handles.append(handle)
        _preloaded_libraries.append(library)
        return
