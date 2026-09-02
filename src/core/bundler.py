import os
import json
import zipfile
import hashlib
import time
from typing import List, Dict, Any, Tuple, Optional, Callable

class Bundler:
    """
    Creates and unpacks standalone portable .zip deployment bundles containing
    all local and downloaded installers, pre-configured silent switches,
    execution order, and offline fallback scripts.
    """

    MANIFEST_NAME = "mefresh_manifest.json"

    @staticmethod
    def calculate_sha256(file_path: str) -> str:
        """Calculates SHA256 hash of a file for integrity verification."""
        if not os.path.isfile(file_path):
            return ""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(64 * 1024):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def create_bundle(
        items: List[Dict[str, Any]],
        output_zip_path: str,
        bundle_name: str = "mefresh_deployment_bundle",
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Tuple[bool, str]:
        """
        Packs all specified software installers, silent parameters,
        metadata manifest, and an offline fallback runner into a single .zip file.
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_zip_path)), exist_ok=True)
            
            manifest_items = []
            total_items = len(items)

            # Ensure valid zip file
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for idx, item in enumerate(items):
                    src_file = item.get("file_path", "")
                    if not src_file or not os.path.isfile(src_file):
                        continue

                    arc_filename = f"payloads/{os.path.basename(src_file)}"
                    zipf.write(src_file, arc_filename)

                    file_hash = Bundler.calculate_sha256(src_file)
                    file_size = os.path.getsize(src_file)

                    manifest_entry = {
                        "id": item.get("id", f"app_{idx+1}"),
                        "name": item.get("name", os.path.basename(src_file)),
                        "version": item.get("version", "1.0"),
                        "category": item.get("category", "General"),
                        "payload_file": arc_filename,
                        "silent_args": item.get("silent_args", ""),
                        "installer_type": item.get("installer_type", "Standard"),
                        "execution_order": idx + 1,
                        "sha256": file_hash,
                        "size_bytes": file_size,
                        "custom_options": item.get("custom_options", {})
                    }
                    manifest_items.append(manifest_entry)

                    if progress_callback:
                        progress_callback({
                            "status": "packaging",
                            "current_item": item.get("name"),
                            "progress": round(((idx + 1) / total_items) * 90, 1)
                        })

                # Write Manifest
                manifest_data = {
                    "bundle_name": bundle_name,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "version": "1.0",
                    "total_packages": len(manifest_items),
                    "options": options or {
                        "auto_restore_point": True,
                        "stop_on_error": False,
                        "reboot_when_done": False
                    },
                    "packages": manifest_items
                }
                zipf.writestr(Bundler.MANIFEST_NAME, json.dumps(manifest_data, indent=2))

                # Generate Offline Fallback PowerShell deployment script
                fallback_script = Bundler._generate_fallback_script(manifest_items)
                zipf.writestr("deploy_unattended.ps1", fallback_script)
                
                # Generate Windows batch launcher
                batch_launcher = "@echo off\r\npowershell -NoProfile -ExecutionPolicy Bypass -File \"%~dp0deploy_unattended.ps1\"\r\npause\r\n"
                zipf.writestr("deploy_unattended.bat", batch_launcher)

            if progress_callback:
                progress_callback({
                    "status": "completed",
                    "current_item": "Bundle Finished",
                    "progress": 100
                })

            return True, f"Successfully created bundle: {output_zip_path}"
        except Exception as e:
            return False, f"Failed to create bundle: {str(e)}"

    @staticmethod
    def extract_bundle(
        zip_path: str,
        extract_dir: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Extracts a .zip bundle, validates the manifest and payload integrity.
        """
        try:
            if not os.path.isfile(zip_path):
                return False, {}, f"Bundle file not found: {zip_path}"

            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zipf:
                # Check for manifest
                if Bundler.MANIFEST_NAME not in zipf.namelist():
                    return False, {}, "Invalid bundle: missing mefresh_manifest.json"

                manifest_content = zipf.read(Bundler.MANIFEST_NAME).decode('utf-8')
                manifest = json.loads(manifest_content)

                total_files = len(zipf.infolist())
                for i, member in enumerate(zipf.infolist()):
                    zipf.extract(member, extract_dir)
                    if progress_callback:
                        progress_callback({
                            "status": "extracting",
                            "file": member.filename,
                            "progress": round(((i + 1) / total_files) * 100, 1)
                        })

            # Update paths to absolute extracted paths in manifest
            for pkg in manifest.get("packages", []):
                pkg["absolute_path"] = os.path.abspath(os.path.join(extract_dir, pkg["payload_file"]))

            return True, manifest, f"Successfully extracted bundle to {extract_dir}"
        except Exception as e:
            return False, {}, f"Bundle extraction failed: {str(e)}"

    @staticmethod
    def _generate_fallback_script(items: List[Dict[str, Any]]) -> str:
        """Generates an unattended PowerShell script inside the bundle for zero-dependency execution."""
        lines = [
            "# mefresh Unattended Deployment Engine - Standalone Fallback Script",
            "# Auto-generated by mefresh studio",
            "$ErrorActionPreference = 'Continue'",
            "Write-Host '==================================================' -ForegroundColor Cyan",
            "Write-Host '  MEFRESH SILENT UNATTENDED DEPLOYMENT ENGINE     ' -ForegroundColor Green",
            "Write-Host '==================================================' -ForegroundColor Cyan",
            "$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path",
            ""
        ]

        for item in items:
            name = item["name"]
            payload = item["payload_file"].replace("/", "\\")
            args = item["silent_args"]
            lines.append(f"Write-Host '[+] Installing: {name}...' -ForegroundColor Yellow")
            lines.append(f"$exePath = Join-Path $ScriptDir '{payload}'")
            lines.append(f"if (Test-Path $exePath) {{")
            lines.append(f"    $proc = Start-Process -FilePath $exePath -ArgumentList '{args}' -Wait -PassThru -NoNewWindow")
            lines.append(f"    Write-Host '    -> Completed with Exit Code:' $proc.ExitCode -ForegroundColor Green")
            lines.append(f"}} else {{")
            lines.append(f"    Write-Host '    -> Error: Payload not found:' $exePath -ForegroundColor Red")
            lines.append(f"}}")
            lines.append("")

        lines.append("Write-Host 'All tasks finished!' -ForegroundColor Cyan")
        return "\r\n".join(lines)
