from unittest.mock import Mock

from config import pdf_runtime


def test_preloads_windows_pthread_before_postgres(tmp_path, monkeypatch):
    pthread = tmp_path / "libwinpthread-1.dll"
    pthread.touch()
    directory_handle = Mock()
    library = Mock()
    add_directory = Mock(return_value=directory_handle)
    load_library = Mock(return_value=library)
    monkeypatch.setattr(pdf_runtime.sys, "platform", "win32")
    monkeypatch.setattr(pdf_runtime.os, "add_dll_directory", add_directory, raising=False)
    monkeypatch.setattr(pdf_runtime.ctypes, "WinDLL", load_library, raising=False)
    before = len(pdf_runtime._dll_directory_handles)
    try:
        pdf_runtime.preload_windows_pdf_runtime(str(tmp_path))
        add_directory.assert_called_once_with(str(tmp_path))
        load_library.assert_called_once_with(str(pthread))
        assert pdf_runtime._dll_directory_handles[before] is directory_handle
        assert pdf_runtime._preloaded_libraries[before] is library
    finally:
        del pdf_runtime._dll_directory_handles[before:]
        del pdf_runtime._preloaded_libraries[before:]


def test_missing_runtime_does_not_prevent_app_start(tmp_path, monkeypatch):
    load_library = Mock()
    monkeypatch.setattr(pdf_runtime.sys, "platform", "win32")
    monkeypatch.setattr(pdf_runtime.ctypes, "WinDLL", load_library, raising=False)
    pdf_runtime.preload_windows_pdf_runtime(str(tmp_path))
    load_library.assert_not_called()
