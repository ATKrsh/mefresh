import os
import sys
import json
import shutil
import subprocess
import threading
import time
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional, Callable

class PackageManager:
    """
    Manages package search, metadata retrieval, and downloading.
    Supports both WinGet CLI query integration and a high-speed curated
    catalog of essential Windows runtimes, frameworks, and power-tools.
    """

    CURATED_CATALOG = [
        {
            "id": "Microsoft.VCRedist.2015+.x64",
            "name": "Visual C++ 2015-2022 Redistributable (x64)",
            "category": "Runtimes",
            "version": "14.40+",
            "description": "Essential Microsoft Visual C++ runtime library for modern Windows software and games.",
            "url": "https://aka.ms/vs/17/release/vc_redist.x64.exe",
            "filename": "vc_redist.x64.exe",
            "silent_args": "/quiet /norestart",
            "installer_type": "Microsoft VC++"
        },
        {
            "id": "Microsoft.VCRedist.2015+.x86",
            "name": "Visual C++ 2015-2022 Redistributable (x86)",
            "category": "Runtimes",
            "version": "14.40+",
            "description": "32-bit Microsoft Visual C++ runtime library required by legacy and 32-bit applications.",
            "url": "https://aka.ms/vs/17/release/vc_redist.x86.exe",
            "filename": "vc_redist.x86.exe",
            "silent_args": "/quiet /norestart",
            "installer_type": "Microsoft VC++"
        },
        {
            "id": "Microsoft.DirectX",
            "name": "DirectX End-User Runtimes (June 2010)",
            "category": "Runtimes",
            "version": "9.29.1974.1",
            "description": "Full DirectX runtime libraries including legacy Direct3D 9, 10, 11 components for gaming.",
            "url": "https://download.microsoft.com/download/8/4/A/84A35BF1-DAFE-4AE8-82AF-AD2AE20B6B14/directx_Jun2010_redist.exe",
            "filename": "directx_Jun2010_redist.exe",
            "silent_args": "/Q /T:C:\\DirectXTemp && C:\\DirectXTemp\\DXSETUP.exe /silent",
            "installer_type": "DirectX Redistributable"
        },
        {
            "id": "Microsoft.DotNet.DesktopRuntime.8",
            "name": ".NET Desktop Runtime 8.0 (x64)",
            "category": "Runtimes",
            "version": "8.0 (LTS)",
            "description": "Runs existing Windows desktop applications built for modern .NET 8.0.",
            "url": "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe",
            "filename": "dotnet-desktop-runtime-8-x64.exe",
            "silent_args": "/install /quiet /norestart",
            "installer_type": ".NET Bootstrapper"
        },
        {
            "id": "Python.Python.3.12",
            "name": "Python 3.12 (x64)",
            "category": "Development",
            "version": "3.12.9",
            "description": "High-level programming language with standard library, pip, and environment path injection.",
            "url": "https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe",
            "filename": "python-3.12.9-amd64.exe",
            "silent_args": "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0",
            "installer_type": "Python Installer"
        },
        {
            "id": "Antigravity.Workspace.PythonEcosystem",
            "name": "Workspace Full Python & AI Ecosystem",
            "category": "Development",
            "version": "1.0.0",
            "description": "Complete 111-package Python AI, Vision, PySide6 GUI, and Win32 ecosystem for workspace projects.",
            "url": "",
            "local_fallback": "E:\\workspace\\install_workspace_packages.ps1",
            "filename": "install_workspace_packages.ps1",
            "silent_args": "-NoProfile -ExecutionPolicy Bypass",
            "installer_type": "PowerShell Script"
        },
        {
            "id": "AdoptOpenJDK.OpenJDK.21",
            "name": "Eclipse Temurin OpenJDK 21 (LTS x64)",
            "category": "Development",
            "version": "21 (LTS)",
            "description": "Enterprise-grade Java SE development kit and runtime environment with PATH integration.",
            "url": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.6%2B7/OpenJDK21U-jdk_x64_windows_hotspot_21.0.6_7.msi",
            "filename": "OpenJDK21U-jdk_x64_windows.msi",
            "silent_args": "/qn /norestart ADDLOCAL=FeatureMain,FeatureEnvironment,FeatureJarFileRunWith,FeatureJavaHome",
            "installer_type": "Microsoft MSI"
        },
        {
            "id": "7zip.7zip",
            "name": "7-Zip (x64)",
            "category": "Utilities",
            "version": "24.09",
            "description": "High-ratio open-source file archiver supporting 7z, ZIP, RAR, TAR, GZ, and ISO.",
            "url": "https://www.7-zip.org/a/7z2409-x64.exe",
            "filename": "7z2409-x64.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        },
        {
            "id": "Git.Git",
            "name": "Git for Windows (x64)",
            "category": "Development",
            "version": "2.48.1",
            "description": "Distributed version control system with Git Bash and CLI tooling.",
            "url": "https://github.com/git-for-windows/git/releases/download/v2.48.1.windows.1/Git-2.48.1-64-bit.exe",
            "filename": "Git-2.48.1-64-bit.exe",
            "silent_args": "/VERYSILENT /NORESTART /NOCANCEL /SP- /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS",
            "installer_type": "Inno Setup"
        },
        {
            "id": "Microsoft.VisualStudioCode",
            "name": "Visual Studio Code (x64 System)",
            "category": "Development",
            "version": "1.97+",
            "description": "Lightweight and powerful source-code editor with broad language support.",
            "url": "https://update.code.visualstudio.com/latest/win32-x64/stable",
            "filename": "VSCodeSetup-x64.exe",
            "silent_args": "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /MERGETASKS=\"!runcode,addcontextmenufiles,addcontextmenufolders,associatewithfiles,addtopath\"",
            "installer_type": "Inno Setup"
        },
        {
            "id": "Google.Chrome",
            "name": "Google Chrome (Standalone Enterprise x64)",
            "category": "Browsers",
            "version": "Latest",
            "description": "Fast, secure, and modern web browser built for enterprise and consumer desktop.",
            "url": "https://dl.google.com/tag/s/appguid%3D%7B8A69D345-D564-463C-AFF1-A69D9E530F96%7D%26iid%3D%7B00000000-0000-0000-0000-000000000000%7D%26lang%3Den%26browser%3D4%26usagestats%3D0%26appname%3DGoogle%2520Chrome%26needsadmin%3Dtrue%26ap%3Dx64-stable-statsdef_1%26installdataindex%3Dempty/update2/installers/ChromeStandaloneSetup64.exe",
            "filename": "ChromeStandaloneSetup64.exe",
            "silent_args": "/silent /install",
            "installer_type": "Google Installer"
        },
        {
            "id": "Mozilla.Firefox",
            "name": "Mozilla Firefox (x64)",
            "category": "Browsers",
            "version": "Latest",
            "description": "Privacy-focused, customizable modern web browser.",
            "url": "https://download.mozilla.org/?product=firefox-latest-ssl&os=win64&lang=en-US",
            "filename": "FirefoxSetup.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        },
        {
            "id": "VideoLAN.VLC",
            "name": "VLC Media Player (x64)",
            "category": "Media",
            "version": "3.0.21",
            "description": "Universal multimedia player that plays most codecs and video/audio formats.",
            "url": "https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe",
            "filename": "vlc-3.0.21-win64.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        },
        {
            "id": "Notepad++.Notepad++",
            "name": "Notepad++ (x64)",
            "category": "Utilities",
            "version": "8.7.7",
            "description": "Fast and versatile text and source code editor with syntax highlighting.",
            "url": "https://github.com/notepad-plus-plus/notepad-plus-plus/releases/download/v8.7.7/npp.8.7.7.Installer.x64.exe",
            "filename": "npp.8.7.7.Installer.x64.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        },
        {
            "id": "OpenJS.NodeJS.LTS",
            "name": "Node.js (LTS x64)",
            "category": "Development",
            "version": "22.14.0",
            "description": "JavaScript runtime built on Chrome's V8 engine with npm package manager.",
            "url": "https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi",
            "filename": "node-v22.14.0-x64.msi",
            "silent_args": "/qn /norestart",
            "installer_type": "Microsoft MSI"
        },
        {
            "id": "Valve.Steam",
            "name": "Steam Client",
            "category": "Gaming",
            "version": "Latest",
            "description": "Digital storefront and multiplayer gaming platform.",
            "url": "https://cdn.akamai.steamstatic.com/client/installer/SteamSetup.exe",
            "filename": "SteamSetup.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        },
        {
            "id": "Discord.Discord",
            "name": "Discord",
            "category": "Communication",
            "version": "Latest",
            "description": "Voice, video and text communication service.",
            "url": "https://discord.com/api/download?platform=win",
            "filename": "DiscordSetup.exe",
            "silent_args": "--silent",
            "installer_type": "Squirrel / Electron"
        },
        {
            "id": "OBSProject.OBSStudio",
            "name": "OBS Studio (x64)",
            "category": "Media",
            "version": "31.0.2",
            "description": "Free and open source software for video recording and live streaming.",
            "url": "https://github.com/obsproject/obs-studio/releases/download/31.0.2/OBS-Studio-31.0.2-Windows-Installer.exe",
            "filename": "OBS-Studio-31.0.2-Windows-Installer.exe",
            "silent_args": "/S",
            "installer_type": "Nullsoft (NSIS)"
        }
    ]

    def __init__(self, download_dir: str = ""):
        if not download_dir:
            self.download_dir = os.path.abspath(os.path.join(os.path.expanduser("~"), "mefresh_downloads"))
        else:
            self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self._cancel_flags: Dict[str, bool] = {}

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches both the curated high-speed catalog and the local WinGet index (if available).
        """
        results: List[Dict[str, Any]] = []
        q = query.lower().strip()

        # 1. Search Curated Catalog
        for item in self.CURATED_CATALOG:
            if (q in item["id"].lower() or 
                q in item["name"].lower() or 
                q in item["description"].lower() or 
                q in item["category"].lower()):
                results.append({
                    "id": item["id"],
                    "name": item["name"],
                    "version": item["version"],
                    "category": item["category"],
                    "description": item["description"],
                    "source": "Curated Catalog",
                    "url": item["url"],
                    "filename": item["filename"],
                    "silent_args": item["silent_args"],
                    "installer_type": item["installer_type"]
                })

        # 2. Search WinGet if available
        winget_results = self._search_winget(query)
        # Avoid duplicate IDs
        existing_ids = {r["id"].lower() for r in results}
        for wr in winget_results:
            if wr["id"].lower() not in existing_ids:
                results.append(wr)

        return results

    def _search_winget(self, query: str) -> List[Dict[str, Any]]:
        """Invokes winget search and parses tabular output."""
        try:
            cmd = ["winget", "search", "--query", query, "--accept-source-agreements"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=12
            )
            if res.returncode != 0 or not res.stdout:
                return []

            lines = res.stdout.strip().splitlines()
            results = []
            
            # Find header index
            header_idx = -1
            for i, line in enumerate(lines):
                if "Name" in line and "Id" in line and "Version" in line:
                    header_idx = i
                    break
            
            if header_idx != -1 and len(lines) > header_idx + 2:
                # Lines after divider
                for line in lines[header_idx + 2:]:
                    parts = line.split()
                    if len(parts) >= 3:
                        # Extract Id (usually 2nd or 3rd column)
                        pkg_id = ""
                        for part in parts:
                            if "." in part and not part.endswith("."):
                                pkg_id = part
                                break
                        if not pkg_id:
                            pkg_id = parts[1]
                        
                        name = parts[0]
                        version = parts[-1]
                        
                        results.append({
                            "id": pkg_id,
                            "name": name,
                            "version": version,
                            "category": "WinGet Repository",
                            "description": f"WinGet package: {pkg_id}",
                            "source": "WinGet",
                            "url": "",
                            "filename": f"{pkg_id}.exe",
                            "silent_args": "/quiet /norestart",
                            "installer_type": "WinGet Managed"
                        })
            return results[:20]
        except Exception:
            return []

    def download_package(
        self,
        pkg: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Downloads a package installer to the local download directory.
        Provides real-time byte counters and progress percentages.
        """
        pkg_id = pkg.get("id", "package")
        self._cancel_flags[pkg_id] = False
        filename = pkg.get("filename", f"{pkg_id}.exe")
        target_path = os.path.join(self.download_dir, filename)

        # Check if local fallback exists
        local_fallback = pkg.get("local_fallback", "")
        if not local_fallback:
            for item in self.CURATED_CATALOG:
                if item["id"].lower() == pkg_id.lower() and item.get("local_fallback"):
                    local_fallback = item["local_fallback"]
                    break

        if local_fallback and os.path.exists(local_fallback):
            shutil.copy2(local_fallback, target_path)
            if progress_callback:
                progress_callback({
                    "id": pkg_id,
                    "status": "completed",
                    "percent": 100,
                    "result": {
                        "success": True,
                        "file_path": target_path,
                        "file_size": os.path.getsize(target_path)
                    }
                })
            return {
                "success": True,
                "file_path": target_path,
                "file_size": os.path.getsize(target_path)
            }

        # Check if URL exists in catalog
        url = pkg.get("url", "")
        if not url:
            # Check if curated
            for item in self.CURATED_CATALOG:
                if item["id"].lower() == pkg_id.lower():
                    url = item["url"]
                    break

        if url:
            # Direct HTTP Download
            return self._download_http(pkg_id, url, target_path, progress_callback)
        else:
            # Use WinGet Download
            return self._download_winget(pkg_id, target_path, progress_callback)

    def _download_http(
        self,
        pkg_id: str,
        url: str,
        target_path: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) mefresh/1.0"}
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 128 * 1024
                start_time = time.time()

                with open(target_path, "wb") as out_file:
                    while True:
                        if self._cancel_flags.get(pkg_id, False):
                            return {"success": False, "error": "Download cancelled by user."}

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        downloaded += len(chunk)

                        elapsed = time.time() - start_time
                        speed_mbps = (downloaded / (1024 * 1024)) / max(elapsed, 0.001)
                        percent = (downloaded / total_size * 100) if total_size > 0 else 0

                        if progress_callback:
                            progress_callback({
                                "id": pkg_id,
                                "status": "downloading",
                                "percent": round(percent, 1),
                                "downloaded_mb": round(downloaded / (1024 * 1024), 2),
                                "total_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
                                "speed_mbps": round(speed_mbps, 2)
                            })

            return {
                "success": True,
                "file_path": target_path,
                "file_size": downloaded
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _download_winget(
        self,
        pkg_id: str,
        target_path: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        try:
            cmd = [
                "winget", "download",
                "--id", pkg_id,
                "-d", self.download_dir,
                "--accept-package-agreements",
                "--accept-source-agreements"
            ]
            if progress_callback:
                progress_callback({
                    "id": pkg_id,
                    "status": "downloading",
                    "percent": 50,
                    "downloaded_mb": 0,
                    "total_mb": 0,
                    "speed_mbps": 0
                })

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                timeout=180
            )

            if res.returncode == 0:
                # Find downloaded file
                return {
                    "success": True,
                    "file_path": self.download_dir,
                    "file_size": 0
                }
            else:
                return {"success": False, "error": res.stderr or res.stdout}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_download(self, pkg_id: str):
        """Signals cancellation for an active download."""
        self._cancel_flags[pkg_id] = True
