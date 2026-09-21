"""
MuMuManager driver module.
Encapsulates communication with MuMuManager.exe for emulator lifecycle,
virtual location injection, and ADB bridge initialization.
"""

import json
import time
import subprocess
from typing import Optional, Dict, Any, Tuple
from core.locator import MuMuLocator


class MuMuDriver:
    """Controls MuMu Player instances using MuMuManager CLI."""

    def __init__(self, manager_path: Optional[str] = None, vm_index: int = 0):
        if manager_path:
            self.manager_path = manager_path
        else:
            found = MuMuLocator.find_mumu_manager()
            if not found:
                raise FileNotFoundError("Could not find MuMuManager.exe. Please install MuMu Player 12 or specify path in config.yaml.")
            self.manager_path = found

        self.vm_index = vm_index

    def _run_cmd(self, args: list, timeout: int = 10) -> Tuple[int, str, str]:
        """Execute a MuMuManager command safely."""
        cmd = [self.manager_path] + args
        try:
            # On Windows, hide command console popup window when invoked
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired:
            return -1, "", "Command timed out"
        except Exception as e:
            return -2, "", str(e)

    def get_player_info(self, vm_index: Optional[int] = None) -> Dict[str, Any]:
        """Retrieve runtime information for a player instance (JSON)."""
        idx = self.vm_index if vm_index is None else vm_index
        code, stdout, stderr = self._run_cmd(["info", "-v", str(idx)])
        if stdout:
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                pass
        return {"error": stderr or "Unknown error", "returncode": code}

    def is_player_running(self, vm_index: Optional[int] = None) -> bool:
        """Check if the Android VM is fully running and ready."""
        info = self.get_player_info(vm_index)
        state = info.get("player_state", "")
        started = info.get("is_process_started", False)
        return (state == "start_finished") and started

    def launch_player(self, vm_index: Optional[int] = None, wait_ready: bool = True, timeout: int = 90) -> bool:
        """Launch the player instance and optionally wait until ready."""
        idx = self.vm_index if vm_index is None else vm_index
        if self.is_player_running(idx):
            return True

        self._run_cmd(["control", "-v", str(idx), "launch"])

        if not wait_ready:
            return True

        start_t = time.time()
        while time.time() - start_t < timeout:
            if self.is_player_running(idx):
                return True
            time.sleep(2)
        return False

    def set_location(self, lng: float, lat: float, vm_index: Optional[int] = None) -> Tuple[bool, str]:
        """
        Inject GPS location directly into the emulator kernel/hardware layer.
        lng: Longitude [-180, 180]
        lat: Latitude [-90, 90]
        """
        idx = self.vm_index if vm_index is None else vm_index
        # Format with 7 decimal places (~1.1 cm precision)
        lon_str = f"{lng:.7f}"
        lat_str = f"{lat:.7f}"

        code, stdout, stderr = self._run_cmd([
            "control", "-v", str(idx), "tool", "location",
            "-lon", lon_str,
            "-lat", lat_str,
        ], timeout=5)

        if stdout:
            try:
                data = json.loads(stdout)
                if data.get("errcode") == 0:
                    return True, ""
                return False, data.get("errmsg", f"Error {data.get('errcode')}")
            except json.JSONDecodeError:
                pass

        if code == 0:
            return True, ""
        return False, stderr or stdout or "Failed to set location"

    def get_adb_info(self, vm_index: Optional[int] = None) -> Tuple[Optional[str], Optional[int]]:
        """Query host and port for ADB connection."""
        idx = self.vm_index if vm_index is None else vm_index
        code, stdout, _ = self._run_cmd(["adb", "-v", str(idx)])
        if stdout:
            try:
                data = json.loads(stdout)
                return data.get("adb_host", "127.0.0.1"), data.get("adb_port")
            except json.JSONDecodeError:
                pass

        # Fallback to info
        info = self.get_player_info(idx)
        return info.get("adb_host_ip", "127.0.0.1"), info.get("adb_port")

    def connect_adb(self, vm_index: Optional[int] = None) -> Tuple[bool, str]:
        """Connect ADB server to this instance."""
        idx = self.vm_index if vm_index is None else vm_index
        code, stdout, stderr = self._run_cmd(["adb", "-v", str(idx), "connect"])
        if code == 0:
            return True, stdout
        return False, stderr or stdout
