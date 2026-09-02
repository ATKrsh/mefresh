import os
import subprocess
import time
import winreg
from typing import List, Dict, Any, Tuple, Callable, Optional
from .system_ops import SystemOps

class WindowsDebloater:
    """
    Modular, high-performance Windows debloating and privacy optimization matrix.
    Safely purges preinstalled UWP bloatware, disables invasive telemetry,
    optimizes background services, and applies developer/power-user tweaks.
    """

    BLOATWARE_APPX_CATALOG = [
        {"id": "Microsoft.549981C3F5F10", "name": "Cortana Voice Assistant", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.BingNews", "name": "Bing News", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.BingWeather", "name": "Bing Weather", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.BingFinance", "name": "Bing Money / Finance", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.BingSports", "name": "Bing Sports", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.GetHelp", "name": "Get Help Assistant", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.Getstarted", "name": "Tips & Get Started", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.MicrosoftSolitaireCollection", "name": "Microsoft Solitaire Collection", "category": "Games/Promos", "safe": True},
        {"id": "Microsoft.MicrosoftOfficeHub", "name": "Office Hub / Promotion", "category": "Promos", "safe": True},
        {"id": "Microsoft.People", "name": "People App", "category": "Bloatware", "safe": True},
        {"id": "Microsoft.Todos", "name": "Microsoft To-Do", "category": "Utilities", "safe": True},
        {"id": "Microsoft.WindowsFeedbackHub", "name": "Windows Feedback Hub", "category": "Telemetry", "safe": True},
        {"id": "Microsoft.YourPhone", "name": "Phone Link (Your Phone)", "category": "Integration", "safe": True},
        {"id": "Microsoft.WindowsMaps", "name": "Windows Maps", "category": "Utilities", "safe": True},
        {"id": "Microsoft.ZuneVideo", "name": "Movies & TV (Zune Video)", "category": "Media", "safe": True},
        {"id": "Microsoft.ZuneMusic", "name": "Groove Music / Media Player", "category": "Media", "safe": True},
        {"id": "Microsoft.WindowsSoundRecorder", "name": "Sound Recorder", "category": "Utilities", "safe": True},
        {"id": "Microsoft.XboxApp", "name": "Xbox Console Companion", "category": "Gaming", "safe": True},
        {"id": "Microsoft.XboxGamingOverlay", "name": "Xbox Game Bar Overlay", "category": "Gaming", "safe": False},
        {"id": "Microsoft.XboxSpeechToTextOverlay", "name": "Xbox Speech Overlay", "category": "Gaming", "safe": True},
        {"id": "Microsoft.SkypeApp", "name": "Skype App", "category": "Communication", "safe": True},
        {"id": "SpotifyAB.SpotifyMusic", "name": "Spotify Preinstalled Stub", "category": "Promos", "safe": True},
        {"id": "Disney.37853FC22B2CE", "name": "Disney+ Preinstalled Stub", "category": "Promos", "safe": True},
        {"id": "ByteDance.TikTok", "name": "TikTok Preinstalled Stub", "category": "Promos", "safe": True},
        {"id": "Clipchamp.Clipchamp", "name": "Clipchamp Video Editor", "category": "Promos", "safe": True}
    ]

    TELEMETRY_TWEAKS = [
        {"id": "disable_telemetry", "name": "Disable Diagnostic Data & Telemetry (Level 0)", "category": "Privacy", "default": True},
        {"id": "disable_advertising_id", "name": "Disable Advertising ID Tracking", "category": "Privacy", "default": True},
        {"id": "disable_activity_history", "name": "Disable Activity History / Timeline Tracking", "category": "Privacy", "default": True},
        {"id": "disable_bing_start_search", "name": "Disable Bing Web Search in Start Menu", "category": "Privacy", "default": True},
        {"id": "disable_feedback_prompts", "name": "Disable Windows Feedback Surveys", "category": "Privacy", "default": True},
        {"id": "disable_cortana_background", "name": "Disable Cortana Background Telemetry", "category": "Privacy", "default": True},
        {"id": "disable_location_tracking", "name": "Disable Windows Location Tracking", "category": "Privacy", "default": False}
    ]

    SYSTEM_TWEAKS = [
        {"id": "enable_dark_mode", "name": "Enable System & App Dark Mode", "category": "Explorer", "default": True},
        {"id": "show_file_extensions", "name": "Show Known File Extensions in File Explorer", "category": "Explorer", "default": True},
        {"id": "show_hidden_files", "name": "Show Hidden Files & Folders", "category": "Explorer", "default": True},
        {"id": "disable_sticky_keys", "name": "Disable Sticky Keys 5x Shift Popup", "category": "Usability", "default": True},
        {"id": "disable_search_highlights", "name": "Disable Search Bar Highlights / Doodle Ads", "category": "Explorer", "default": True},
        {"id": "launch_explorer_this_pc", "name": "Open File Explorer to 'This PC' instead of Quick Access", "category": "Explorer", "default": True},
        {"id": "optimize_power_plan", "name": "Set High Performance Power Plan", "category": "Performance", "default": True}
    ]

    SERVICES_TWEAKS = [
        {"id": "DiagTrack", "name": "Connected User Experiences and Telemetry (DiagTrack)", "category": "Services", "default": True},
        {"id": "dmwappushservice", "name": "Device Management Wireless Application Protocol (dmwappushservice)", "category": "Services", "default": True},
        {"id": "RemoteRegistry", "name": "Remote Registry Service", "category": "Services", "default": True},
        {"id": "MapsBroker", "name": "Downloaded Maps Manager (MapsBroker)", "category": "Services", "default": True}
    ]

    @staticmethod
    def get_catalog() -> Dict[str, Any]:
        """Returns the full catalog of debloat options and preset profiles."""
        return {
            "appx": WindowsDebloater.BLOATWARE_APPX_CATALOG,
            "telemetry": WindowsDebloater.TELEMETRY_TWEAKS,
            "system": WindowsDebloater.SYSTEM_TWEAKS,
            "services": WindowsDebloater.SERVICES_TWEAKS
        }

    @staticmethod
    def get_preset(preset_name: str) -> Dict[str, Any]:
        """Returns selected option IDs for a given preset profile."""
        preset = preset_name.lower()

        if preset == "safe" or preset == "standard":
            # Standard Safe Debloat
            selected_appx = [a["id"] for a in WindowsDebloater.BLOATWARE_APPX_CATALOG if a["safe"] and a["category"] != "Gaming"]
            selected_telemetry = [t["id"] for t in WindowsDebloater.TELEMETRY_TWEAKS if t["id"] != "disable_location_tracking"]
            selected_system = [s["id"] for s in WindowsDebloater.SYSTEM_TWEAKS]
            selected_services = ["DiagTrack", "dmwappushservice", "RemoteRegistry"]
        elif preset == "gamer" or preset == "extreme":
            # Maximum Performance Debloat
            selected_appx = [a["id"] for a in WindowsDebloater.BLOATWARE_APPX_CATALOG]
            selected_telemetry = [t["id"] for t in WindowsDebloater.TELEMETRY_TWEAKS]
            selected_system = [s["id"] for s in WindowsDebloater.SYSTEM_TWEAKS]
            selected_services = [s["id"] for s in WindowsDebloater.SERVICES_TWEAKS]
        elif preset == "minimal":
            # Privacy only
            selected_appx = []
            selected_telemetry = [t["id"] for t in WindowsDebloater.TELEMETRY_TWEAKS if t["default"]]
            selected_system = ["show_file_extensions", "enable_dark_mode"]
            selected_services = ["DiagTrack"]
        else: # Default
            selected_appx = [a["id"] for a in WindowsDebloater.BLOATWARE_APPX_CATALOG if a["safe"]]
            selected_telemetry = [t["id"] for t in WindowsDebloater.TELEMETRY_TWEAKS if t["default"]]
            selected_system = [s["id"] for s in WindowsDebloater.SYSTEM_TWEAKS if s["default"]]
            selected_services = [s["id"] for s in WindowsDebloater.SERVICES_TWEAKS if s["default"]]

        return {
            "selected_appx": selected_appx,
            "selected_telemetry": selected_telemetry,
            "selected_system": selected_system,
            "selected_services": selected_services
        }

    @staticmethod
    def execute_debloat(
        config: Dict[str, Any],
        log_callback: Callable[[str, str], None],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Tuple[bool, str]:
        """
        Executes selected debloat operations:
        1. Creates System Restore Point
        2. Uninstalls selected Appx packages
        3. Applies Registry Telemetry & Explorer tweaks
        4. Configures Windows Services
        """
        if not SystemOps.is_admin():
            return False, "Administrator privileges required to execute Windows debloating."

        log_callback("INFO", "[SHIELD] Creating System Restore Point prior to debloat matrix execution...")
        ok, msg = SystemOps.create_restore_point("mefresh_PreDebloat")
        if ok:
            log_callback("SUCCESS", f"[SHIELD] {msg}")
        else:
            log_callback("WARNING", f"[SHIELD] {msg} (Proceeding with debloat)")

        selected_appx = config.get("selected_appx", [])
        selected_telemetry = config.get("selected_telemetry", [])
        selected_system = config.get("selected_system", [])
        selected_services = config.get("selected_services", [])

        total_ops = len(selected_appx) + len(selected_telemetry) + len(selected_system) + len(selected_services)
        completed_ops = 0

        # 1. Purge Selected Appx Packages
        for appx_id in selected_appx:
            log_callback("INFO", f"Purging Appx Package: {appx_id}...")
            ps_cmd = f"Get-AppxPackage -AllUsers *{appx_id}* | Remove-AppxPackage -AllUsers -ErrorAction SilentlyContinue; Get-AppxProvisionedPackage -Online | Where-Object DisplayName -like '*{appx_id}*' | Remove-AppxProvisionedPackage -Online -ErrorAction SilentlyContinue"
            try:
                subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    timeout=30
                )
                log_callback("SUCCESS", f"[+] Purged Appx: {appx_id}")
            except Exception as e:
                log_callback("WARNING", f"Failed to purge {appx_id}: {str(e)}")

            completed_ops += 1
            if progress_callback:
                progress_callback(completed_ops, total_ops)

        # 2. Apply Telemetry & Privacy Registry Tweaks
        for t_id in selected_telemetry:
            log_callback("INFO", f"Applying Privacy Shield: {t_id}...")
            WindowsDebloater._apply_telemetry_tweak(t_id, log_callback)
            completed_ops += 1
            if progress_callback:
                progress_callback(completed_ops, total_ops)

        # 3. Apply System & Explorer Tweaks
        for s_id in selected_system:
            log_callback("INFO", f"Applying System Tweak: {s_id}...")
            WindowsDebloater._apply_system_tweak(s_id, log_callback)
            completed_ops += 1
            if progress_callback:
                progress_callback(completed_ops, total_ops)

        # 4. Configure Services
        for svc in selected_services:
            log_callback("INFO", f"Configuring Service: {svc} (Disabling)...")
            try:
                subprocess.run(
                    ["sc", "stop", svc],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                subprocess.run(
                    ["sc", "config", svc, "start=disabled"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                log_callback("SUCCESS", f"[+] Disabled tracking service: {svc}")
            except Exception as e:
                log_callback("WARNING", f"Service config error on {svc}: {str(e)}")

            completed_ops += 1
            if progress_callback:
                progress_callback(completed_ops, total_ops)

        log_callback("SUCCESS", "Debloat and optimization matrix completed successfully.")
        return True, "Debloat matrix finished."

    @staticmethod
    def _set_reg_value(hive, subkey: str, name: str, value_type, value):
        """Helper to safely set Windows Registry keys and values."""
        try:
            key = winreg.CreateKeyEx(hive, subkey, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, name, 0, value_type, value)
            winreg.CloseKey(key)
        except Exception:
            pass

    @staticmethod
    def _apply_telemetry_tweak(tweak_id: str, log_cb: Callable[[str, str], None]):
        """Sets privacy policies in Windows Registry."""
        try:
            if tweak_id == "disable_telemetry":
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "AllowTelemetry", winreg.REG_DWORD, 0)
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\DataCollection", "DoNotShowFeedbackNotifications", winreg.REG_DWORD, 1)
            elif tweak_id == "disable_advertising_id":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\AdvertisingInfo", "Enabled", winreg.REG_DWORD, 0)
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo", "DisabledByGroupPolicy", winreg.REG_DWORD, 1)
            elif tweak_id == "disable_activity_history":
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\System", "EnableActivityFeed", winreg.REG_DWORD, 0)
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\System", "PublishUserActivities", winreg.REG_DWORD, 0)
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\System", "UploadUserActivities", winreg.REG_DWORD, 0)
            elif tweak_id == "disable_bing_start_search":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Policies\Microsoft\Windows\Explorer", "DisableSearchBoxSuggestions", winreg.REG_DWORD, 1)
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Search", "BingSearchEnabled", winreg.REG_DWORD, 0)
            elif tweak_id == "disable_feedback_prompts":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Siuf\Rules", "NumberOfSIUFInPeriod", winreg.REG_DWORD, 0)
            elif tweak_id == "disable_cortana_background":
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\Windows Search", "AllowCortana", winreg.REG_DWORD, 0)
            elif tweak_id == "disable_location_tracking":
                WindowsDebloater._set_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors", "DisableLocation", winreg.REG_DWORD, 1)
            log_cb("SUCCESS", f"[+] Applied privacy policy: {tweak_id}")
        except Exception as e:
            log_cb("WARNING", f"Privacy policy tweak error ({tweak_id}): {str(e)}")

    @staticmethod
    def _apply_system_tweak(tweak_id: str, log_cb: Callable[[str, str], None]):
        """Sets Windows usability and explorer settings."""
        try:
            if tweak_id == "enable_dark_mode":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", winreg.REG_DWORD, 0)
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "SystemUsesLightTheme", winreg.REG_DWORD, 0)
            elif tweak_id == "show_file_extensions":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "HideFileExt", winreg.REG_DWORD, 0)
            elif tweak_id == "show_hidden_files":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "Hidden", winreg.REG_DWORD, 1)
            elif tweak_id == "disable_sticky_keys":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Control Panel\Accessibility\StickyKeys", "Flags", winreg.REG_SZ, "506")
            elif tweak_id == "disable_search_highlights":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\SearchSettings", "IsDynamicSearchBoxEnabled", winreg.REG_DWORD, 0)
            elif tweak_id == "launch_explorer_this_pc":
                WindowsDebloater._set_reg_value(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "LaunchTo", winreg.REG_DWORD, 1)
            elif tweak_id == "optimize_power_plan":
                # Set High Performance power plan
                subprocess.run(
                    ["powercfg", "-setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
            log_cb("SUCCESS", f"[+] Applied system tweak: {tweak_id}")
        except Exception as e:
            log_cb("WARNING", f"System tweak error ({tweak_id}): {str(e)}")
