import os
from typing import Dict, Any, List

class SwitchDetector:
    """
    Intelligently inspects installer files, file extensions, and executable signatures
    to detect installer frameworks and suggest optimal silent/unattended switches.
    """

    KNOWN_SWITCHES = {
        "msi": {
            "type": "Microsoft Windows Installer (MSI)",
            "silent_args": "/qn /norestart ALLUSERS=1",
            "log_arg_template": "/l*v \"{log_path}\""
        },
        "inno": {
            "type": "Inno Setup",
            "silent_args": "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-",
            "log_arg_template": "/LOG=\"{log_path}\""
        },
        "nsis": {
            "type": "Nullsoft Scriptable Install System (NSIS)",
            "silent_args": "/S",
            "log_arg_template": ""
        },
        "installshield": {
            "type": "InstallShield",
            "silent_args": "/s /v\"/qn /norestart\"",
            "log_arg_template": "/v\"/l*v \\\"{log_path}\\\"\""
        },
        "wise": {
            "type": "Wise Installer",
            "silent_args": "/s",
            "log_arg_template": ""
        },
        "squirrel": {
            "type": "Squirrel / Electron Setup",
            "silent_args": "--silent",
            "log_arg_template": ""
        },
        "bat": {
            "type": "Batch Script",
            "silent_args": "",
            "log_arg_template": ""
        },
        "ps1": {
            "type": "PowerShell Script",
            "silent_args": "-NoProfile -ExecutionPolicy Bypass",
            "log_arg_template": ""
        },
        "zip": {
            "type": "Archive (Extract Only)",
            "silent_args": "",
            "log_arg_template": ""
        },
        "generic": {
            "type": "Standard Executable",
            "silent_args": "/quiet /norestart",
            "log_arg_template": ""
        }
    }

    @staticmethod
    def detect_installer(file_path: str) -> Dict[str, Any]:
        """
        Inspects the file extension and binary header to determine installer type and default silent arguments.
        """
        if not os.path.exists(file_path):
            ext = os.path.splitext(file_path)[1].lower().strip(".")
            if ext == "msi":
                return SwitchDetector._format_result("msi")
            elif ext == "bat" or ext == "cmd":
                return SwitchDetector._format_result("bat")
            elif ext == "ps1":
                return SwitchDetector._format_result("ps1")
            elif ext == "zip":
                return SwitchDetector._format_result("zip")
            return SwitchDetector._format_result("generic")

        ext = os.path.splitext(file_path)[1].lower().strip(".")
        
        if ext == "msi":
            return SwitchDetector._format_result("msi")
        elif ext in ["bat", "cmd"]:
            return SwitchDetector._format_result("bat")
        elif ext == "ps1":
            return SwitchDetector._format_result("ps1")
        elif ext == "zip":
            return SwitchDetector._format_result("zip")
        elif ext != "exe":
            return SwitchDetector._format_result("generic")

        # Inspect PE binary for signatures
        try:
            with open(file_path, "rb") as f:
                header = f.read(2 * 1024 * 1024) # Read first 2MB
                
                header_lower = header.lower()

                if b"inno setup" in header_lower or b"inno.setup" in header_lower:
                    return SwitchDetector._format_result("inno")
                elif b"nullsoft install" in header_lower or b"nullsoft.nsh" in header_lower or b"nsis.sf.net" in header_lower:
                    return SwitchDetector._format_result("nsis")
                elif b"installshield" in header_lower or b"issetup.dll" in header_lower:
                    return SwitchDetector._format_result("installshield")
                elif b"wise installation" in header_lower or b"wisescript" in header_lower:
                    return SwitchDetector._format_result("wise")
                elif b"squirrel" in header_lower or b"update.exe" in header_lower:
                    return SwitchDetector._format_result("squirrel")
                elif b"7-zip sfx" in header_lower or b"7z.sfx" in header_lower:
                    return {
                        "category": "7z",
                        "type": "7-Zip Self-Extracting Executable",
                        "silent_args": "-y -gm2",
                        "log_arg_template": ""
                    }
        except Exception:
            pass

        return SwitchDetector._format_result("generic")

    @staticmethod
    def _format_result(key: str) -> Dict[str, Any]:
        info = SwitchDetector.KNOWN_SWITCHES.get(key, SwitchDetector.KNOWN_SWITCHES["generic"])
        return {
            "category": key,
            "type": info["type"],
            "silent_args": info["silent_args"],
            "log_arg_template": info["log_arg_template"]
        }

    @staticmethod
    def get_supported_presets() -> List[Dict[str, str]]:
        """Returns list of common presets user can pick from in UI."""
        return [
            {"name": "Inno Setup", "args": "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-"},
            {"name": "Nullsoft (NSIS)", "args": "/S"},
            {"name": "Microsoft MSI", "args": "/qn /norestart ALLUSERS=1"},
            {"name": "InstallShield", "args": "/s /v\"/qn /norestart\""},
            {"name": "Standard /quiet", "args": "/quiet /norestart"},
            {"name": "Standard /silent", "args": "/silent /norestart"},
            {"name": "Standard /s", "args": "/s"},
            {"name": "7-Zip SFX", "args": "-y -gm2"},
            {"name": "Custom / None", "args": ""}
        ]
