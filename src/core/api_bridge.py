import os
import json
import threading
from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtWidgets import QFileDialog

from .system_ops import SystemOps
from .switch_detector import SwitchDetector
from .package_manager import PackageManager
from .bundler import Bundler
from .installer_engine import InstallerEngine
from .debloater import WindowsDebloater

class ApiBridge(QObject):
    """
    QWebChannel Bridge exposing Python backend capabilities, hardware telemetry,
    silent installers, package search, and debloat functions directly to WebEngine UI.
    """

    # Signals to JavaScript
    telemetrySignal = Signal(str)
    searchResultSignal = Signal(str)
    downloadProgressSignal = Signal(str)
    bundleProgressSignal = Signal(str)
    installerEventSignal = Signal(str, str)
    debloatLogSignal = Signal(str, str)
    debloatProgressSignal = Signal(int, int)
    restorePointResultSignal = Signal(str)

    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.current_bundle_data: Dict[str, Any] = {}
        self.deployment_thread = None
        self.package_manager = PackageManager()
        self.installer_engine = InstallerEngine()

    @Slot(bool)
    def setTelemetryActive(self, active: bool):
        """Enable or suspend real-time hardware telemetry streaming."""
        if self.main_window and hasattr(self.main_window, 'set_telemetry_active'):
            self.main_window.set_telemetry_active(active)

    @Slot(result=str)
    def getSystemTelemetry(self) -> str:
        """Returns JSON serialized hardware telemetry and OS info."""
        telemetry = SystemOps.get_telemetry()
        return json.dumps(telemetry)

    @Slot(str)
    def searchPackages(self, query: str):
        """Asynchronously searches online package repositories and curated catalog."""
        def _worker():
            results = self.package_manager.search(query)
            self.searchResultSignal.emit(json.dumps(results))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(str)
    def downloadPackage(self, pkg_json: str):
        """Downloads a package asynchronously and streams progress."""
        pkg = json.loads(pkg_json)

        def _prog_cb(data):
            self.downloadProgressSignal.emit(json.dumps(data))

        def _worker():
            res = self.package_manager.download_package(pkg, _prog_cb)
            payload = {
                "id": pkg.get("id"),
                "status": "completed" if res.get("success") else "failed",
                "result": res
            }
            self.downloadProgressSignal.emit(json.dumps(payload))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(str)
    def cancelDownload(self, pkg_id: str):
        """Cancels an active download."""
        self.package_manager.cancel_download(pkg_id)

    @Slot(str, result=str)
    def inspectLocalFile(self, file_path: str) -> str:
        """Analyzes a local file and detects installer type & silent switches."""
        detection = SwitchDetector.detect_installer(file_path)
        base_name = os.path.basename(file_path)
        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        info = {
            "name": os.path.splitext(base_name)[0],
            "file_path": os.path.abspath(file_path),
            "size_bytes": size_bytes,
            "category": detection["category"],
            "installer_type": detection["type"],
            "silent_args": detection["silent_args"]
        }
        return json.dumps(info)

    @Slot(result=str)
    def openFileDialog(self) -> str:
        """Opens native Windows file picker for installers."""
        filters = "All Compatible Installers (*.exe *.msi *.bat *.cmd *.ps1 *.zip);;Executables (*.exe);;MSI Packages (*.msi);;Scripts (*.bat *.cmd *.ps1);;Archives (*.zip);;All Files (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Select Software Installer to Add", "", filters
        )
        if file_path:
            return self.inspectLocalFile(file_path)
        return ""

    @Slot(result=str)
    def openBundleFileDialog(self) -> str:
        """Opens native Windows file picker to load an existing mefresh .zip bundle."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window, "Select mefresh Deployment Bundle (.zip)", "", "mefresh Bundles (*.zip);;All Files (*.*)"
        )
        return file_path or ""

    @Slot(str, result=str)
    def saveBundleFileDialog(self, default_name: str) -> str:
        """Opens native Windows save file picker for export."""
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window, "Save mefresh Portable Bundle", default_name, "ZIP Archives (*.zip)"
        )
        return file_path or ""

    @Slot(str)
    def createBundle(self, bundle_json: str):
        """Packs software installers and manifest into single .zip bundle."""
        data = json.loads(bundle_json)
        items = data.get("items", [])
        output_zip = data.get("output_path", "")
        bundle_name = data.get("bundle_name", "mefresh_bundle")
        options = data.get("options", {})

        def _prog_cb(info):
            self.bundleProgressSignal.emit(json.dumps(info))

        def _worker():
            ok, msg = Bundler.create_bundle(items, output_zip, bundle_name, options, _prog_cb)
            self.bundleProgressSignal.emit(json.dumps({
                "status": "finished",
                "success": ok,
                "message": msg,
                "file_path": output_zip
            }))

        threading.Thread(target=_worker, daemon=True).start()

    def _get_state_path(self) -> str:
        appdata = os.environ.get("APPDATA")
        if appdata and os.path.isdir(appdata):
            base = os.path.join(appdata, "mefresh")
        else:
            base = os.path.join(os.path.expanduser("~"), ".mefresh")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "priming_state.json")

    @Slot(str, result=bool)
    def savePrimingState(self, state_json: str) -> bool:
        """Saves current priming stack and options to persistent storage."""
        try:
            state_path = self._get_state_path()
            with open(state_path, "w", encoding="utf-8") as f:
                f.write(state_json)
            return True
        except Exception as e:
            print(f"Error saving priming state: {e}")
            return False

    @Slot(result=str)
    def loadPrimingState(self) -> str:
        """Loads saved priming stack and options from persistent storage."""
        try:
            state_path = self._get_state_path()
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            print(f"Error loading priming state: {e}")
        return "{}"

    @Slot(result=bool)
    def clearPrimingState(self) -> bool:
        """Clears persisted priming state."""
        try:
            state_path = self._get_state_path()
            if os.path.exists(state_path):
                os.remove(state_path)
            return True
        except Exception:
            return False

    @Slot(str, result=str)
    def loadBundle(self, zip_path: str) -> str:
        """Extracts and parses a .zip bundle for deployment."""
        extract_dir = os.path.join(os.path.expanduser("~"), "mefresh_extracted")
        ok, manifest, msg = Bundler.extract_bundle(zip_path, extract_dir)
        return json.dumps({
            "success": ok,
            "manifest": manifest,
            "message": msg
        })

    @Slot(str)
    def startDeployment(self, plan_json: str):
        """Starts silent post-installation batch sequence."""
        data = json.loads(plan_json)
        queue = data.get("packages", [])
        options = data.get("options", {})

        def _event_cb(evt_type, evt_data):
            self.installerEventSignal.emit(evt_type, json.dumps(evt_data))

        self.installer_engine.start_batch(queue, options, _event_cb)

    @Slot()
    def pauseDeployment(self):
        self.installer_engine.pause()

    @Slot()
    def resumeDeployment(self):
        self.installer_engine.resume()

    @Slot()
    def cancelDeployment(self):
        self.installer_engine.cancel()

    @Slot(str)
    def createRestorePoint(self, desc: str):
        """Creates a manual or automated Windows System Restore Point."""
        def _worker():
            ok, msg = SystemOps.create_restore_point(desc or "mefresh_ManualCheck")
            self.restorePointResultSignal.emit(json.dumps({"success": ok, "message": msg}))

        threading.Thread(target=_worker, daemon=True).start()

    @Slot(result=str)
    def getDebloatCatalog(self) -> str:
        """Returns the full Windows debloat and optimization options."""
        return json.dumps(WindowsDebloater.get_catalog())

    @Slot(str, result=str)
    def getDebloatPreset(self, name: str) -> str:
        """Returns preset configuration for debloat."""
        return json.dumps(WindowsDebloater.get_preset(name))

    @Slot(str)
    def executeDebloat(self, config_json: str):
        """Executes selected debloat operations asynchronously."""
        config = json.loads(config_json)

        def _log_cb(lvl, msg):
            self.debloatLogSignal.emit(lvl, msg)

        def _prog_cb(done, total):
            self.debloatProgressSignal.emit(done, total)

        def _worker():
            ok, msg = WindowsDebloater.execute_debloat(config, _log_cb, _prog_cb)
            _log_cb("SUCCESS" if ok else "ERROR", f"Debloat Finished: {msg}")

        threading.Thread(target=_worker, daemon=True).start()

    @Slot()
    def requestElevation(self):
        """Requests UAC administrator elevation."""
        SystemOps.elevate()

    @Slot(result=str)
    def getSysInfoDetails(self) -> str:
        """Returns deep msinfo32-grade categorized system diagnostics."""
        details = SystemOps.get_sysinfo_full()
        return json.dumps(details)

    @Slot()
    def launchMsInfo(self):
        """Launches native Windows System Information (msinfo32.exe)."""
        SystemOps.launch_msinfo()

    @Slot(result=str)
    def exportSysInfoMarkdown(self) -> str:
        """Generates formatted markdown diagnostic report."""
        data = SystemOps.get_sysinfo_full()
        summary = data.get("summary", {})
        gpus = data.get("gpus", [])
        disks = data.get("disks", [])
        net = data.get("network", [])

        lines = [
            "# System Diagnostics & Hardware Profile",
            f"**Generated**: {data.get('timestamp')}",
            "",
            "## 📋 System Summary",
            f"- **OS**: {summary.get('os_name')} ({summary.get('os_version')})",
            f"- **System Model**: {summary.get('system_manufacturer')} {summary.get('system_model')}",
            f"- **Processor**: {summary.get('processor')}",
            f"- **Cores / Threads**: {summary.get('cores_threads')}",
            f"- **BIOS**: {summary.get('bios_version')}",
            f"- **Installed Physical Memory**: {summary.get('total_physical_memory')} ({summary.get('ram_speed')})",
            f"- **Available Physical Memory**: {summary.get('available_physical_memory')}",
            "",
            "## 🎮 Graphics & Displays"
        ]
        for g in gpus:
            lines.append(f"- **{g.get('name')}** ({g.get('type')}) | VRAM: {g.get('vram')} | Driver: {g.get('driver_version')} | {g.get('resolution')}")

        lines.extend(["", "## 💾 Storage & Drives"])
        for d in disks:
            lines.append(f"- **Drive {d.get('drive')}** ({d.get('filesystem')}): {d.get('free_gb')} GB free of {d.get('total_gb')} GB ({d.get('used_percent')}% used)")

        lines.extend(["", "## 🌐 Network Adapters"])
        for n in net:
            lines.append(f"- **{n.get('interface')}**: IPv4 {n.get('ipv4')} | MAC {n.get('mac')}")

        return "\n".join(lines)

    @Slot()
    def minimizeWindow(self):
        if self.main_window:
            self.main_window.showMinimized()

    @Slot()
    def maximizeWindow(self):
        if self.main_window:
            if self.main_window.isMaximized():
                self.main_window.showNormal()
            else:
                self.main_window.showMaximized()

    @Slot()
    def closeWindow(self):
        if self.main_window:
            self.main_window.close()

