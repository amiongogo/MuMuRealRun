"""
MuMu emulator and ADB location detector.
Provides robust, multi-tier discovery that works independently of machine setup.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple, List


class MuMuLocator:
    """Intelligently detects MuMu Player installation and tools."""

    CANDIDATE_SUBPATHS_MANAGER = [
        os.path.join("nx_main", "MuMuManager.exe"),
        os.path.join("shell", "MuMuManager.exe"),
        os.path.join("MuMuPlayer-12.0", "shell", "MuMuManager.exe"),
        "MuMuManager.exe",
    ]

    CANDIDATE_SUBPATHS_ADB = [
        os.path.join("nx_main", "adb.exe"),
        os.path.join("nx_device", "12.0", "shell", "adb.exe"),
        os.path.join("shell", "adb.exe"),
        os.path.join("vms", "myand_1", "adb.exe"),
        "adb.exe",
    ]

    COMMON_INSTALL_DIRS = [
        r"D:\Games\MuMu Player 12",
        r"C:\Program Files\Netease\MuMuPlayer-12.0",
        r"C:\Program Files\Netease\MuMu Player 12",
        r"C:\Program Files (x86)\Netease\MuMuPlayer-12.0",
        r"D:\Program Files\Netease\MuMuPlayer-12.0",
        r"E:\Games\MuMu Player 12",
        r"E:\Program Files\Netease\MuMuPlayer-12.0",
        r"C:\MuMuPlayer-12.0",
        r"D:\MuMuPlayer-12.0",
    ]

    @classmethod
    def find_mumu_dir(cls, user_hint: Optional[str] = None) -> Optional[str]:
        """
        Locates the MuMu Player installation root directory.
        Checks:
        1. User-provided hint / config path
        2. Environment variables: MUMU_DIR, MUMU_PATH
        3. Running MuMu processes
        4. Windows Registry uninstall information
        5. Common directory paths on Windows
        """
        # 1. User hint
        if user_hint and os.path.exists(user_hint):
            if cls._has_mumu_manager(user_hint):
                return os.path.abspath(user_hint)

        # 2. Environment variables
        for env_var in ["MUMU_DIR", "MUMU_PATH", "MUMUPLAYER_HOME"]:
            val = os.environ.get(env_var)
            if val and os.path.exists(val):
                if cls._has_mumu_manager(val):
                    return os.path.abspath(val)

        # 3. Running processes (Windows)
        proc_dir = cls._detect_from_running_processes()
        if proc_dir:
            return proc_dir

        # 4. Windows Registry
        reg_dir = cls._detect_from_registry()
        if reg_dir:
            return reg_dir

        # 5. Common installation paths
        for p in cls.COMMON_INSTALL_DIRS:
            if os.path.exists(p) and cls._has_mumu_manager(p):
                return os.path.abspath(p)

        return None

    @classmethod
    def _has_mumu_manager(cls, base_dir: str) -> bool:
        """Check if base_dir contains MuMuManager.exe in expected subpaths."""
        for rel in cls.CANDIDATE_SUBPATHS_MANAGER:
            if os.path.isfile(os.path.join(base_dir, rel)):
                return True
        return False

    @classmethod
    def _detect_from_running_processes(cls) -> Optional[str]:
        """Search running process table for MuMu executables."""
        if sys.platform != "win32":
            return None
        try:
            # Query tasklist or PowerShell for MuMuNxMain / MuMuPlayer
            cmd = ["powershell", "-NoProfile", "-Command",
                   "Get-Process | Where-Object { $_.ProcessName -like '*mumu*' -or $_.ProcessName -like '*nemu*' } | Select-Object -ExpandProperty Path"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    path = line.strip()
                    if path and os.path.isfile(path):
                        # For example: D:\Games\MuMu Player 12\nx_main\MuMuNxMain.exe
                        # Walk up to find the root folder containing nx_main or shell
                        dir_path = os.path.dirname(path)
                        if cls._has_mumu_manager(dir_path):
                            return dir_path
                        parent = os.path.dirname(dir_path)
                        if cls._has_mumu_manager(parent):
                            return parent
        except Exception:
            pass
        return None

    @classmethod
    def _detect_from_registry(cls) -> Optional[str]:
        """Query Windows Registry for MuMu uninstall paths."""
        if sys.platform != "win32":
            return None
        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for hkey, subkey_path in reg_paths:
                try:
                    with winreg.OpenKey(hkey, subkey_path) as key:
                        subkeys_count = winreg.QueryInfoKey(key)[0]
                        for i in range(subkeys_count):
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    disp_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "mumu" in disp_name.lower():
                                        # Try InstallLocation
                                        try:
                                            install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                            if install_loc and os.path.exists(install_loc) and cls._has_mumu_manager(install_loc):
                                                return os.path.abspath(install_loc)
                                        except Exception:
                                            pass
                                        # Try UninstallString
                                        try:
                                            uninst = winreg.QueryValueEx(subkey, "UninstallString")[0].strip('"')
                                            uninst_dir = os.path.dirname(uninst)
                                            if uninst_dir and os.path.exists(uninst_dir) and cls._has_mumu_manager(uninst_dir):
                                                return os.path.abspath(uninst_dir)
                                        except Exception:
                                            pass
                                except Exception:
                                    continue
                except Exception:
                    continue
        except Exception:
            pass
        return None

    @classmethod
    def find_mumu_manager(cls, mumu_dir: Optional[str] = None) -> Optional[str]:
        """Find the full path to MuMuManager.exe."""
        if mumu_dir:
            for rel in cls.CANDIDATE_SUBPATHS_MANAGER:
                full = os.path.join(mumu_dir, rel)
                if os.path.isfile(full):
                    return os.path.abspath(full)

        # Check system PATH
        in_path = shutil.which("MuMuManager.exe") or shutil.which("MuMuManager")
        if in_path:
            return in_path

        # If mumu_dir was not passed, discover it
        discovered_dir = cls.find_mumu_dir()
        if discovered_dir:
            return cls.find_mumu_manager(discovered_dir)

        return None

    @classmethod
    def find_adb(cls, mumu_dir: Optional[str] = None) -> Optional[str]:
        """Find the full path to adb.exe."""
        if mumu_dir:
            for rel in cls.CANDIDATE_SUBPATHS_ADB:
                full = os.path.join(mumu_dir, rel)
                if os.path.isfile(full):
                    return os.path.abspath(full)

        # Check system PATH
        in_path = shutil.which("adb.exe") or shutil.which("adb")
        if in_path:
            return in_path

        # If mumu_dir was not passed, discover it
        discovered_dir = cls.find_mumu_dir()
        if discovered_dir:
            return cls.find_adb(discovered_dir)

        return None

    @classmethod
    def discover_environment(cls, user_hint: Optional[str] = None) -> dict:
        """Run full discovery and return diagnostic summary."""
        mumu_dir = cls.find_mumu_dir(user_hint)
        manager_exe = cls.find_mumu_manager(mumu_dir)
        adb_exe = cls.find_adb(mumu_dir)

        return {
            "mumu_dir": mumu_dir,
            "manager_exe": manager_exe,
            "adb_exe": adb_exe,
            "ready": bool(manager_exe and os.path.isfile(manager_exe)),
        }
