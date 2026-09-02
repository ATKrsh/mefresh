import os
import sys
import ctypes
import argparse
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtGui import QIcon
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from PySide6.QtWebChannel import QWebChannel

# Set Explicit Windows Application User Model ID so Taskbar shows custom icon
try:
    if sys.platform == "win32":
        myappid = "mefresh.studio.postinstall.v1"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

# Import Core
from core.api_bridge import ApiBridge
from core.system_ops import SystemOps

class MeFreshMainWindow(QMainWindow):
    """
    Main application window hosting the ultra-futuristic WebEngine dashboard
    and QWebChannel bidirectional bridge.
    """

    def __init__(self, initial_bundle: str = ""):
        super().__init__()
        self.setWindowTitle("mefresh // Ultra-Futuristic Windows Post-Install & Priming Studio")
        self.resize(1300, 840)
        self.setMinimumSize(1024, 700)

        # Set Window & Taskbar Icon
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = getattr(sys, '_MEIPASS')
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        icon_path = os.path.join(base_dir, "icon.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(base_dir, "ui", "icon.png")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            QApplication.setWindowIcon(QIcon(icon_path))

        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

        # Setup WebEngine View
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)

        # Enable WebEngine Settings
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.WebGLEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True)

        # Setup WebChannel Bridge
        self.channel = QWebChannel(self.web_view.page())
        self.bridge = ApiBridge(self)
        self.channel.registerObject("pyBridge", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Determine path to UI (supports both source and PyInstaller frozen onefile)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_dir = getattr(sys, '_MEIPASS')
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        ui_path = os.path.join(base_dir, "ui", "index.html")
        self.web_view.load(QUrl.fromLocalFile(ui_path))

        # Real-Time Hardware Telemetry Timer (every 750ms for rock-solid, calm live metrics)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self._send_telemetry_update)
        self.telemetry_timer.start(750)

        self.initial_bundle = initial_bundle

    def set_telemetry_active(self, active: bool):
        """Enable or suspend live telemetry timer and background sampler."""
        if active:
            if not self.telemetry_timer.isActive():
                self.telemetry_timer.start(750)
            SystemOps.resume_sampler()
            # Immediately push one fresh sample upon reactivation
            self._send_telemetry_update()
        else:
            if self.telemetry_timer.isActive():
                self.telemetry_timer.stop()
            SystemOps.pause_sampler()

    def _send_telemetry_update(self):
        """Pushes live system telemetry to the UI."""
        if not hasattr(self, 'telemetry_timer') or self.telemetry_timer.isActive():
            data = self.bridge.getSystemTelemetry()
            self.bridge.telemetrySignal.emit(data)


def main():
    parser = argparse.ArgumentParser(description="mefresh - Futuristic Windows Post-Install & Priming Studio")
    parser.add_argument("--bundle", type=str, default="", help="Path to .zip bundle to load on startup")
    parser.add_argument("--elevate", action="store_true", help="Auto-request UAC administrator privileges")
    args = parser.parse_args()

    if args.elevate and not SystemOps.is_admin():
        if SystemOps.elevate():
            sys.exit(0)

    # Set High-DPI Scaling attributes
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("mefresh")
    app.setOrganizationName("mefresh")

    window = MeFreshMainWindow(initial_bundle=args.bundle)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
