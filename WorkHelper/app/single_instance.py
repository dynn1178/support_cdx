from __future__ import annotations

from PyQt6.QtCore import QObject, QSharedMemory, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

_KEY = "WorkHelper-6PM-Assistant-SingleInstance-v1"


class SingleInstanceGuard(QObject):
    """중복 실행 방지.

    QSharedMemory로 최초 실행 여부를 판별하고, 이미 실행 중이면 로컬 소켓으로
    기존 인스턴스에 '창을 띄워달라'는 신호를 보낸다. Windows는 프로세스가
    종료되면(비정상 종료 포함) 공유 메모리를 자동 해제하므로 별도의 잠금 파일
    정리가 필요 없다.
    """

    show_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._shared_memory = QSharedMemory(_KEY)
        self._server: QLocalServer | None = None

    def try_acquire(self) -> bool:
        """최초 인스턴스면 True. 이미 다른 인스턴스가 실행 중이면 False."""
        if self._shared_memory.attach():
            return False
        if self._shared_memory.create(1):
            self._start_server()
            return True
        return False

    def _start_server(self) -> None:
        QLocalServer.removeServer(_KEY)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._server.listen(_KEY)

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection() if self._server else None
        if socket is None:
            return
        socket.readyRead.connect(lambda s=socket: self._on_ready_read(s))
        socket.disconnected.connect(socket.deleteLater)

    def _on_ready_read(self, socket: QLocalSocket) -> None:
        socket.readAll()
        self.show_requested.emit()

    def notify_running_instance(self, timeout_ms: int = 500) -> bool:
        """이미 실행 중인 인스턴스에 창을 띄우라고 알린다."""
        socket = QLocalSocket()
        socket.connectToServer(_KEY)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(b"show")
        socket.waitForBytesWritten(timeout_ms)
        socket.disconnectFromServer()
        return True
