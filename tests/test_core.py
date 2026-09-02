import os
import sys
import tempfile
import json
import pytest

# Add src to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from core.switch_detector import SwitchDetector
from core.package_manager import PackageManager
from core.bundler import Bundler
from core.debloater import WindowsDebloater
from core.system_ops import SystemOps

def test_switch_detector():
    msi_res = SwitchDetector.detect_installer("test_app.msi")
    assert msi_res["category"] == "msi"
    assert "/qn" in msi_res["silent_args"]

    ps1_res = SwitchDetector.detect_installer("install.ps1")
    assert ps1_res["category"] == "ps1"
    assert "-ExecutionPolicy Bypass" in ps1_res["silent_args"]

    bat_res = SwitchDetector.detect_installer("setup.bat")
    assert bat_res["category"] == "bat"

    generic_res = SwitchDetector.detect_installer("unknown.exe")
    assert generic_res["category"] == "generic"

def test_package_manager_search():
    pm = PackageManager()
    results = pm.search("python")
    assert len(results) > 0
    assert any("python" in r["id"].lower() or "python" in r["name"].lower() for r in results)

    vcredist = pm.search("Visual C++")
    assert len(vcredist) > 0

    directx = pm.search("DirectX")
    assert len(directx) > 0

def test_bundler_create_and_extract():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create dummy installer file
        dummy_file = os.path.join(tmpdir, "dummy_setup.exe")
        with open(dummy_file, "wb") as f:
            f.write(b"MOCK_INSTALLER_BINARY_DATA_12345")

        bundle_path = os.path.join(tmpdir, "test_bundle.zip")
        items = [{
            "id": "app_test",
            "name": "Test Application",
            "version": "1.0",
            "category": "Test",
            "file_path": dummy_file,
            "silent_args": "/VERYSILENT",
            "installer_type": "Inno Setup"
        }]

        # Create bundle
        ok, msg = Bundler.create_bundle(items, bundle_path, "TestBundle")
        assert ok is True
        assert os.path.exists(bundle_path)

        # Extract bundle
        extract_dir = os.path.join(tmpdir, "extracted")
        ext_ok, manifest, ext_msg = Bundler.extract_bundle(bundle_path, extract_dir)
        assert ext_ok is True
        assert manifest["bundle_name"] == "TestBundle"
        assert len(manifest["packages"]) == 1
        assert manifest["packages"][0]["id"] == "app_test"
        assert os.path.exists(manifest["packages"][0]["absolute_path"])

def test_debloater_catalog_and_presets():
    catalog = WindowsDebloater.get_catalog()
    assert "appx" in catalog
    assert "telemetry" in catalog
    assert "system" in catalog
    assert "services" in catalog
    assert len(catalog["appx"]) > 10

    standard_preset = WindowsDebloater.get_preset("standard")
    assert len(standard_preset["selected_telemetry"]) > 0
    assert len(standard_preset["selected_system"]) > 0

    gamer_preset = WindowsDebloater.get_preset("gamer")
    assert len(gamer_preset["selected_appx"]) >= len(standard_preset["selected_appx"])

def test_system_telemetry():
    telemetry = SystemOps.get_telemetry()
    assert "os" in telemetry
    assert "cpu_percent" in telemetry
    assert "ram_percent" in telemetry
    assert "disk_percent" in telemetry
    assert "is_admin" in telemetry

def test_priming_state_persistence():
    from core.api_bridge import ApiBridge
    bridge = ApiBridge()

    sample_state = {
        "items": [
            {
                "id": "vscode",
                "name": "Visual Studio Code",
                "file_path": "C:\\Installers\\VSCodeUserSetup-x64.exe",
                "size_bytes": 95000000,
                "category": "Development",
                "installer_type": "Inno Setup",
                "silent_args": "/VERYSILENT /NORESTART"
            }
        ],
        "bundle_name": "Developer_Prime_Pack",
        "timestamp": "2026-08-15T12:00:00Z"
    }

    json_str = json.dumps(sample_state)
    assert bridge.savePrimingState(json_str) is True

    loaded_str = bridge.loadPrimingState()
    loaded_data = json.loads(loaded_str)
    assert loaded_data["bundle_name"] == "Developer_Prime_Pack"
    assert len(loaded_data["items"]) == 1
    assert loaded_data["items"][0]["id"] == "vscode"

    assert bridge.clearPrimingState() is True
    assert bridge.loadPrimingState() == "{}"

