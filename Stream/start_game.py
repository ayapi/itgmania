"""Launch the portable game and remember its normal window position."""
from pathlib import Path
from ctypes import wintypes
import argparse
import ctypes
import json
import os
import subprocess
import time

user = ctypes.WinDLL('user32', use_last_error=True)
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
user.IsWindowVisible.argtypes = [wintypes.HWND]
user.IsIconic.argtypes = [wintypes.HWND]
user.IsZoomed.argtypes = [wintypes.HWND]
user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                            ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                           wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]


class MonitorInfo(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                ('work', wintypes.RECT), ('flags', wintypes.DWORD)]


user.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
user.MonitorFromPoint.restype = wintypes.HANDLE
user.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]


def find_window(pid):
    found = []

    @callback_type
    def visit(hwnd, unused):
        owner = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        name = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(hwnd, name, len(name))
        if owner.value == pid and name.value.lower() == 'itgmania' and user.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user.EnumWindows(visit, 0)
    return found[0] if found else None


def clamp_position(x, y, width, height, work):
    # Keep the title bar reachable if the previous monitor was disconnected.
    left, top, right, bottom = work
    return (max(left, min(x, max(left, right - width))),
            max(top, min(y, max(top, bottom - min(height, 64)))))


def restore(hwnd, saved):
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        return
    x, y = int(saved['x']), int(saved['y'])
    monitor = user.MonitorFromPoint(wintypes.POINT(x, y), 2)
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if user.GetMonitorInfoW(monitor, ctypes.byref(info)):
        w = info.work
        x, y = clamp_position(x, y, rect.right - rect.left,
                              rect.bottom - rect.top, (w.left, w.top, w.right, w.bottom))
    # Move only: leave game resolution, focus, and stacking order intact.
    if not user.SetWindowPos(hwnd, None, x, y, 0, 0, 0x0001 | 0x0004 | 0x0010):
        raise ctypes.WinError(ctypes.get_last_error())


def watch(root, pid, restore_saved=True):
    path = root / 'Save/WindowPosition.json'
    saved = None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if all(type(value.get(k)) is int for k in ('x', 'y')):
            saved = value
    except (OSError, ValueError, AttributeError):
        pass
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return
    try:
        name = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(name))
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)):
            raise ctypes.WinError(ctypes.get_last_error())
        if Path(name.value).resolve() != (root / 'Program/ITGmania.exe').resolve():
            raise ValueError('Window tracking must target this portable game')
        restored = None
        previous = None
        while True:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value != 259:
                break
            hwnd = find_window(pid)
            if (hwnd and user.GetWindowLongW(hwnd, -16) & 0x00C00000
                    and not user.IsIconic(hwnd) and not user.IsZoomed(hwnd)):
                if hwnd != restored:
                    # Let renderer initialization finish before moving the window.
                    time.sleep(0.4)
                    if saved and (restore_saved or restored is not None):
                        restore(hwnd, saved)
                    restored = hwnd
                rect = wintypes.RECT()
                if user.GetWindowRect(hwnd, ctypes.byref(rect)):
                    current = {'x': rect.left, 'y': rect.top}
                    if current != previous:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        temporary = path.with_suffix('.tmp')
                        temporary.write_text(json.dumps(current), encoding='utf-8')
                        os.replace(temporary, path)
                        previous = current
                        saved = current
            time.sleep(0.5)
    finally:
        kernel.CloseHandle(handle)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--pid', type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    pid = args.pid
    if pid is None:
        pid = subprocess.Popen([str(root / 'Program/ITGmania.exe')], cwd=root).pid
    watch(root, pid, restore_saved=args.pid is None)
