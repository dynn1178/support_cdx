from __future__ import annotations

"""매크로 스크립트의 창(window) 관련 명령(WinActivate, WinWait 등)이 쓰는 win32 헬퍼.

hotkey_manager.py 와 같은 스타일로 pywin32 없이 ctypes 로 직접 user32/kernel32 를 호출한다.
"""

import ctypes
from ctypes import wintypes

USER32 = ctypes.WinDLL("user32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

WM_CLOSE = 0x0010
SW_RESTORE = 9
SW_MINIMIZE = 6
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

USER32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
USER32.IsWindowVisible.argtypes = [wintypes.HWND]
USER32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
USER32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
USER32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
USER32.GetForegroundWindow.restype = wintypes.HWND
USER32.SetForegroundWindow.argtypes = [wintypes.HWND]
USER32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
USER32.IsIconic.argtypes = [wintypes.HWND]
USER32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
USER32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
USER32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
USER32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
USER32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
KERNEL32.OpenProcess.restype = wintypes.HANDLE
KERNEL32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL32.GetCurrentThreadId.restype = wintypes.DWORD


def _window_title(hwnd: int) -> str:
    length = USER32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    USER32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = KERNEL32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(260)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not KERNEL32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return buffer.value.rsplit("\\", 1)[-1]
    finally:
        KERNEL32.CloseHandle(handle)


def find_window(criteria: str) -> int | None:
    """창 제목의 일부(부분 일치, 대소문자 무시) 또는 'ahk_exe 파일명.exe' 로 창을 찾는다."""
    criteria = (criteria or "").strip()
    if not criteria:
        return None

    if criteria.lower().startswith("ahk_exe"):
        exe_name = criteria[len("ahk_exe"):].strip().lower()
        matcher = lambda hwnd: _window_process_name(hwnd).lower() == exe_name
    else:
        needle = criteria.lower()
        matcher = lambda hwnd: needle in _window_title(hwnd).lower()

    found: list[int] = []

    def _callback(hwnd, _lparam):
        if not USER32.IsWindowVisible(hwnd):
            return True
        if not _window_title(hwnd):
            return True
        if matcher(hwnd):
            found.append(hwnd)
            return False
        return True

    USER32.EnumWindows(_WNDENUMPROC(_callback), 0)
    return found[0] if found else None


def is_window_active(hwnd: int) -> bool:
    return bool(hwnd) and USER32.GetForegroundWindow() == hwnd


def activate_window(hwnd: int) -> None:
    if not hwnd:
        return
    if USER32.IsIconic(hwnd):
        USER32.ShowWindow(hwnd, SW_RESTORE)
    if USER32.GetForegroundWindow() == hwnd:
        return
    # 포그라운드가 아닌 프로세스의 SetForegroundWindow 호출은 윈도우 보안 정책상
    # 대개 무시되므로, 현재 포그라운드 스레드에 입력 큐를 붙여 우회한다.
    foreground = USER32.GetForegroundWindow()
    current_thread = KERNEL32.GetCurrentThreadId()
    foreground_thread = USER32.GetWindowThreadProcessId(foreground, None)
    target_thread = USER32.GetWindowThreadProcessId(hwnd, None)
    attached_fg = attached_target = False
    try:
        if foreground_thread and foreground_thread != current_thread:
            attached_fg = bool(USER32.AttachThreadInput(current_thread, foreground_thread, True))
        if target_thread and target_thread != current_thread:
            attached_target = bool(USER32.AttachThreadInput(current_thread, target_thread, True))
        USER32.SetForegroundWindow(hwnd)
    finally:
        if attached_fg:
            USER32.AttachThreadInput(current_thread, foreground_thread, False)
        if attached_target:
            USER32.AttachThreadInput(current_thread, target_thread, False)


def minimize_window(hwnd: int) -> None:
    if hwnd:
        USER32.ShowWindow(hwnd, SW_MINIMIZE)


def close_window(hwnd: int) -> None:
    if hwnd:
        USER32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def active_window() -> int | None:
    """현재 활성(포그라운드) 창의 핸들을 돌려준다."""
    hwnd = USER32.GetForegroundWindow()
    return hwnd or None


def client_origin(hwnd: int | None) -> tuple[int, int] | None:
    """창의 클라이언트 영역(제목표시줄/테두리 제외) 좌상단의 화면 좌표."""
    if not hwnd:
        return None
    point = wintypes.POINT(0, 0)
    if not USER32.ClientToScreen(hwnd, ctypes.byref(point)):
        return None
    return (point.x, point.y)


def window_origin(hwnd: int | None) -> tuple[int, int] | None:
    """창 전체(제목표시줄/테두리 포함) 좌상단의 화면 좌표."""
    if not hwnd:
        return None
    rect = wintypes.RECT()
    if not USER32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    return (rect.left, rect.top)
