"""
ADB communication driver.
Provides device diagnostics, application management, and background health checks.
"""

import re
import subprocess
from typing import Optional, Tuple, List
from core.locator import MuMuLocator


class AdbDriver:
    """Interfaces with Android devices via ADB."""

    def __init__(self, adb_path: Optional[str] = None, serial: Optional[str] = None):
        if adb_path:
            self.adb_path = adb_path
        else:
            found = MuMuLocator.find_adb()
            if not found:
                raise FileNotFoundError("Could not find adb.exe in MuMu directory or system PATH.")
            self.adb_path = found

        self.serial = serial  # e.g., "127.0.0.1:16384"

    def _run_cmd(self, args: list, timeout: int = 10) -> Tuple[int, str, str]:
        """Execute an ADB command."""
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += args

        startupinfo = None
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        try:
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
        except Exception as e:
            return -1, "", str(e)

    def connect(self, host: str = "127.0.0.1", port: int = 16384) -> Tuple[bool, str]:
        """Connect to Android device via TCP/IP."""
        target = f"{host}:{port}"
        code, stdout, stderr = self._run_cmd(["connect", target])
        if "connected" in stdout.lower():
            self.serial = target
            return True, stdout
        return False, stderr or stdout

    def get_devices(self) -> List[Tuple[str, str]]:
        """List attached devices as (serial, state)."""
        code, stdout, _ = self._run_cmd(["devices"])
        devices = []
        for line in stdout.splitlines()[1:]:
            parts = line.strip().split()
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))
        return devices

    def is_connected(self) -> bool:
        """Check if target device is online."""
        devs = self.get_devices()
        if not self.serial:
            return any(state == "device" for _, state in devs)
        return any(ser == self.serial and state == "device" for ser, state in devs)

    def run_shell(self, shell_cmd: str, timeout: int = 10) -> Tuple[int, str, str]:
        """Run an arbitrary shell command on the device."""
        return self._run_cmd(["shell", shell_cmd], timeout=timeout)

    def is_app_installed(self, package_name: str) -> bool:
        """Check if a package is installed."""
        code, stdout, _ = self.run_shell(f"pm list packages {package_name}")
        return package_name in stdout

    def get_foreground_app(self) -> Optional[str]:
        """Get the package name of the currently focused app."""
        # Try dumpsys window
        code, stdout, _ = self.run_shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        if stdout:
            match = re.search(r'([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+', stdout)
            if match:
                return match.group(1)

        # Fallback to dumpsys activity
        code, stdout, _ = self.run_shell("dumpsys activity top | grep ACTIVITY")
        if stdout:
            match = re.search(r'([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+', stdout)
            if match:
                return match.group(1)

        return None

    def launch_app(self, package_name: str) -> bool:
        """Launch an application by package name using monkey launcher."""
        code, stdout, _ = self.run_shell(f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
        return code == 0

    def stop_app(self, package_name: str) -> bool:
        """Force stop an application."""
        code, _, _ = self.run_shell(f"am force-stop {package_name}")
        return code == 0
