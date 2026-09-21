"""
MuMuRealRun - MuMu Android Emulator Athletic Running Simulator
Inspired by iosrealrun, providing realistic GPS motion, speed fluctuation,
and MuMuManager/ADB hardware-level location injection.
"""

import sys
import os
import time
import argparse
import atexit
import signal
from typing import Optional

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".simulator.lock")


def is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is currently running."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == 259
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def terminate_pid(pid: int):
    """Terminate a lingering process by PID."""
    try:
        if sys.platform == "win32":
            import ctypes
            PROCESS_TERMINATE = 0x0001
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
            if handle:
                ctypes.windll.kernel32.TerminateProcess(handle, 1)
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception:
        pass


def acquire_instance_lock():
    """
    Ensure only one instance of MuMuRealRun is actively injecting coordinates.
    If a previous background or zombie instance is found, terminate it and take over
    to completely prevent concurrent GPS jitter/spikes.
    """
    my_pid = os.getpid()
    if os.path.isfile(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if content.isdigit():
                old_pid = int(content)
                if old_pid != my_pid and is_pid_alive(old_pid):
                    print(f"⚠️ 检测到另一个模拟进程仍在运行 (PID: {old_pid})，正在自动终止以避免多进程坐标冲突...")
                    terminate_pid(old_pid)
                    time.sleep(0.5)
        except Exception:
            pass

    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(my_pid))
    except Exception:
        pass

    def _release_lock():
        try:
            if os.path.isfile(LOCK_FILE):
                with open(LOCK_FILE, "r", encoding="utf-8") as f:
                    if f.read().strip() == str(my_pid):
                        os.remove(LOCK_FILE)
        except Exception:
            pass

    atexit.register(_release_lock)


from core.config import Config
from core.coord import convert_coordinates
from core.locator import MuMuLocator
from core.mumu_driver import MuMuDriver
from core.adb_driver import AdbDriver
from core.route import Route
from core.motion import MotionSimulator
from core.ui import TerminalDashboard, check_keyboard_input, format_seconds


def run_doctor(cfg: Config):
    """Diagnose local MuMu installation, paths, and ADB connectivity."""
    print("=" * 60)
    print("[*] MuMuRealRun 环境与模拟器自检 (Doctor Diagnostic)")
    print("=" * 60)

    user_hint = cfg.get("mumu.path")
    env = MuMuLocator.discover_environment(user_hint)

    print(f"📁 MuMu 安装目录: {env['mumu_dir'] or '[red]未自动探测到[/red]'}")
    print(f"⚙  MuMuManager:   {env['manager_exe'] or '[red]未找到[/red]'}")
    print(f"📱 adb.exe:       {env['adb_exe'] or '[yellow]未找到 (非强制)[/yellow]'}")

    if not env["ready"]:
        print("\n❌ 诊断失败: 无法定位 MuMuManager.exe！")
        print("请检查是否已安装网易 MuMu 模拟器 12，或在 config.yaml 中手动设置 'mumu.path'")
        return False

    print("\n✔ MuMu 核心工具定位成功！正在查询模拟器实例状态...")
    try:
        vm_index = int(cfg.get("mumu.vm_index", 0))
        driver = MuMuDriver(env["manager_exe"], vm_index=vm_index)
        info = driver.get_player_info(vm_index)

        is_running = driver.is_player_running(vm_index)
        state_str = info.get("player_state", "unknown")
        print(f"🎮 模拟器实例 [{vm_index}]:")
        print(f"   - 进程状态: {'运行中' if info.get('is_process_started') else '未运行'}")
        print(f"   - 运行状态: {state_str}")
        print(f"   - 就绪状态: {'✔ 已完全就绪 (Ready)' if is_running else '⏳ 尚未完全启动'}")

        adb_host, adb_port = driver.get_adb_info(vm_index)
        print(f"   - ADB 端口: {adb_host}:{adb_port}")

        if env["adb_exe"] and adb_port:
            adb = AdbDriver(env["adb_exe"], f"{adb_host}:{adb_port}")
            if adb.is_connected():
                print(f"   - ADB 状态: ✔ 已连接")
                fg = adb.get_foreground_app()
                if fg:
                    print(f"   - 前台 App: {fg}")
            else:
                print(f"   - ADB 状态: 未连接 (启动时将自动连接)")

        # Test location command
        if is_running:
            print("\n📡 测试坐标注入功能...")
            ok, msg = driver.set_location(120.088, 30.311, vm_index)
            if ok:
                print("✔ 底层硬件级坐标注入接口测试通过！")
            else:
                print(f"❌ 坐标注入接口返回错误: {msg}")

        print("\n🎉 自检完成！环境整体状态良好。")
        return True

    except Exception as e:
        print(f"\n❌ 诊断过程中发生异常: {e}")
        return False


def interactive_menu(cfg: Config) -> bool:
    """Show interactive menu when no CLI arguments are supplied."""
    print("=" * 60)
    print("          MuMuRealRun - 运动模拟与虚拟定位控制台")
    print("=" * 60)
    dist = cfg.get("target.distance_meters", 0)
    laps = cfg.get("target.laps", 0)
    infinite = cfg.get("target.infinite_loop", True)
    spd = cfg.get("run.speed_mps", 3.2)
    route = cfg.get("run.route_file", "ZJGroute.txt")

    if infinite:
        mode_str = "无限循环奔跑"
    elif dist > 0:
        mode_str = f"目标里程 {dist} 米"
    elif laps > 0:
        mode_str = f"目标圈数 {laps} 圈"
    else:
        mode_str = "无限循环奔跑"

    print(f"当前配置: 路线=[{route}] | 目标模式=[{mode_str}] | 配速基准=[{spd} m/s]")
    print()
    print("请选择运行模式:")
    print(" [1] 开始跑步 (默认: 无限循环奔跑)")
    print(" [2] 环境自检与接口诊断 (Doctor)")
    print(" [3] 自定义跑步里程 (输入公里数，如 2.5 或 3.0)")
    print(" [4] 自定义跑步圈数 (输入目标圈数，如 5 或 8)")
    print(" [5] 启动路线可视化绘制工具 (Web 地图交互)")
    print(" [0] 退出程序")
    print()

    try:
        choice = input("请输入选项 [0-5] (默认 1): ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    if not choice or choice == "1":
        cfg.set("target.infinite_loop", True)
        cfg.set("target.distance_meters", 0)
        cfg.set("target.laps", 0)
        return True
    elif choice == "2":
        run_doctor(cfg)
        print()
        try:
            input("按回车键返回主菜单...")
        except Exception:
            pass
        return interactive_menu(cfg)
    elif choice == "3":
        try:
            km_input = input("请输入目标跑步公里数 (例如 2.5 或 3.0): ").strip()
            val = float(km_input) if km_input else 2.5
            cfg.set("target.distance_meters", int(val * 1000))
            cfg.set("target.laps", 0)
            cfg.set("target.infinite_loop", False)
            return True
        except ValueError:
            print("输入格式有误，将使用默认配置。")
            return True
    elif choice == "4":
        try:
            laps_input = input("请输入目标圈数 (例如 5 或 8): ").strip()
            val = int(laps_input) if laps_input else 5
            cfg.set("target.laps", val)
            cfg.set("target.distance_meters", 0)
            cfg.set("target.infinite_loop", False)
            return True
        except ValueError:
            print("输入格式有误，将使用默认配置。")
            return True
    elif choice == "5":
        print()
        from route_editor import start_editor
        start_editor()
        return interactive_menu(cfg)
    elif choice == "0":
        return False
    else:
        cfg.set("target.infinite_loop", True)
        return True


def main():
    parser = argparse.ArgumentParser(description="MuMu 模拟器运动模拟器 (MuMuRealRun)")
    parser.add_argument("--route", "-r", type=str, help="路线文件路径 (如 ZJGroute.txt)")
    parser.add_argument("--speed", "-s", type=float, help="跑步基础速度 (m/s，如 3.2)")
    parser.add_argument("--distance", "-d", type=float, help="目标跑步里程 (米，如 2500)")
    parser.add_argument("--laps", "-l", type=int, help="目标圈数 (如 5)")
    parser.add_argument("--coord-type", "-c", type=str, choices=["gcj02", "wgs84", "bd09"], help="输入路线的坐标系")
    parser.add_argument("--lateral-variance", "--lateral-var", "-lv", type=float, help="轨迹横向方差与道次扩散 (米，如 2.2)")
    parser.add_argument("--vm-index", "-v", type=int, help="目标 MuMu 模拟器多开编号 (默认 0)")
    parser.add_argument("--mumu-path", "-m", type=str, help="手动指定 MuMu 模拟器安装路径")
    parser.add_argument("--doctor", "--scan", action="store_true", help="运行环境自检与诊断")
    parser.add_argument("--editor", action="store_true", help="启动路线可视化网页绘制工具")

    args = parser.parse_args()
    is_interactive = (len(sys.argv) == 1)

    if args.editor:
        from route_editor import start_editor
        start_editor()
        return

    # Load base config
    cfg = Config.load_from_file("config.yaml")

    # Apply CLI overrides
    if args.mumu_path:
        cfg.set("mumu.path", args.mumu_path)
    if args.vm_index is not None:
        cfg.set("mumu.vm_index", args.vm_index)
    if args.route:
        cfg.set("run.route_file", args.route)
    if args.speed is not None:
        cfg.set("run.speed_mps", args.speed)
    if args.distance is not None:
        cfg.set("target.distance_meters", args.distance)
        cfg.set("target.infinite_loop", False)
    if args.laps is not None:
        cfg.set("target.laps", args.laps)
        cfg.set("target.infinite_loop", False)
    if args.coord_type:
        cfg.set("run.coord_type", args.coord_type)
    if args.lateral_variance is not None:
        cfg.set("run.lateral_variance_meters", args.lateral_variance)

    if args.doctor:
        run_doctor(cfg)
        return

    # If run with no arguments (e.g. double-clicked start.bat), show interactive menu
    if is_interactive:
        should_run = interactive_menu(cfg)
        if not should_run:
            return

    # Ensure single instance to prevent conflicting GPS injection
    acquire_instance_lock()

    # 1. Discover MuMu Environment
    env = MuMuLocator.discover_environment(cfg.get("mumu.path"))
    if not env["ready"]:
        print("❌ 未能检测到 MuMu 模拟器安装目录！")
        print("请运行 'python main.py --doctor' 进行自检，或在 config.yaml 的 mumu.path 中填入安装路径。")
        sys.exit(1)

    vm_index = int(cfg.get("mumu.vm_index", 0))
    driver = MuMuDriver(env["manager_exe"], vm_index=vm_index)

    # 2. Check VM Running State
    if not driver.is_player_running(vm_index):
        if cfg.get("mumu.auto_launch", True):
            print(f"⏳ 检测到模拟器 [{vm_index}] 尚未完全启动，正在尝试自动调起...")
            driver.launch_player(vm_index, wait_ready=True, timeout=90)
            if not driver.is_player_running(vm_index):
                print("❌ 模拟器启动超时，请在 MuMu 窗口中手动开机后再试。")
                sys.exit(1)
        else:
            print(f"❌ 模拟器 [{vm_index}] 尚未启动，请先开启模拟器，或在 config.yaml 开启 auto_launch。")
            sys.exit(1)

    # 3. Connect ADB if enabled
    adb_instance: Optional[AdbDriver] = None
    if cfg.get("adb.auto_connect", True) and env["adb_exe"]:
        try:
            host, port = driver.get_adb_info(vm_index)
            if host and port:
                adb_instance = AdbDriver(env["adb_exe"], f"{host}:{port}")
                adb_instance.connect(host, port)
        except Exception:
            pass

    # 4. Load and convert Route
    route_file = cfg.get("run.route_file", "ZJGroute.txt")
    if not os.path.isabs(route_file):
        route_file = os.path.abspath(route_file)

    if not os.path.isfile(route_file):
        print(f"❌ 找不到路线文件: {route_file}")
        sys.exit(1)

    try:
        raw_route = Route.load_from_file(route_file)
    except Exception as e:
        print(f"❌ 解析路线文件失败: {e}")
        sys.exit(1)

    source_coord = cfg.get("run.coord_type", "gcj02")
    # Keep route coordinates in source system for dashboard display and accurate tracking
    sim_route = raw_route

    # 5. Setup Motion Simulation
    speed_mps = float(cfg.get("run.speed_mps", 3.2))
    speed_jitter = float(cfg.get("run.speed_jitter_pct", 0.10))
    gps_jitter = float(cfg.get("run.gps_jitter_meters", 0.6))
    lateral_variance = float(cfg.get("run.lateral_variance_meters", 2.2))
    lane_drift = bool(cfg.get("run.lane_drift_per_lap", True))
    turn_slowdown = bool(cfg.get("run.slow_down_on_turns", True))
    interval = float(cfg.get("run.interval_sec", 1.0))

    target_dist = float(cfg.get("target.distance_meters", 0))
    target_laps = int(cfg.get("target.laps", 0))
    infinite = bool(cfg.get("target.infinite_loop", True))
    if infinite:
        target_dist = 0.0
        target_laps = 0

    simulator = MotionSimulator(
        route=sim_route,
        base_speed_mps=speed_mps,
        speed_jitter_pct=speed_jitter,
        gps_jitter_meters=gps_jitter,
        lateral_variance_meters=lateral_variance,
        lane_drift_per_lap=lane_drift,
        slow_down_on_turns=turn_slowdown,
        interval_sec=interval,
    )

    # 6. Initialize UI Dashboard
    dashboard = TerminalDashboard(
        target_dist_m=target_dist,
        target_laps=target_laps,
        route_name=os.path.basename(route_file),
    )

    dashboard.start()
    status = "RUNNING"
    is_paused = False

    backend = cfg.get("mumu.backend", "mumu_manager")

    try:
        while True:
            loop_start = time.time()

            # Handle interactive user input
            key = check_keyboard_input()
            if key:
                if key in [" ", "p"]:
                    is_paused = not is_paused
                    status = "PAUSED" if is_paused else "RUNNING"
                elif key in ["+", "="]:
                    simulator.base_speed += 0.2
                elif key in ["-", "_"]:
                    simulator.base_speed = max(0.8, simulator.base_speed - 0.2)
                elif key in ["q", "\x03"]:  # 'q' or Ctrl+C
                    break

            if not is_paused:
                # Step the motion simulator
                state = simulator.step()

                # Convert coordinate for emulator backend:
                # MuMuManager's internal LocationPresenter expects BD-09 (Baidu) coordinates
                # and runs convertDB09ToWGS84_ before passing to Android GPS kernel.
                if backend == "mumu_manager":
                    inject_lng, inject_lat = convert_coordinates(state["lng"], state["lat"], source_coord, "bd09")
                else:
                    inject_lng, inject_lat = convert_coordinates(state["lng"], state["lat"], source_coord, "wgs84")

                # Inject coordinates into MuMu hardware layer
                ok, err = driver.set_location(inject_lng, inject_lat, vm_index)
                mumu_status = "正常" if ok else f"异常({err})"

                # Render dashboard
                dashboard.render(state, status=status, mumu_status=mumu_status)

                # Check completion conditions
                if target_dist > 0 and state["total_distance_m"] >= target_dist:
                    status = "COMPLETED"
                    dashboard.render(state, status=status, mumu_status=mumu_status)
                    break
                if target_laps > 0 and state["lap"] > target_laps:
                    status = "COMPLETED"
                    dashboard.render(state, status=status, mumu_status=mumu_status)
                    break
            else:
                # Paused state display update
                state = {
                    "total_distance_m": simulator.total_distance_traveled,
                    "total_elapsed_sec": simulator.total_elapsed_time,
                    "speed_kmh": 0.0,
                    "speed_mps": 0.0,
                    "pace_str": "--'--\"",
                    "avg_pace_str": "--'--\"",
                    "lap": simulator.lap_count,
                    "steps": simulator.total_steps,
                    "lng": simulator.current_lng,
                    "lat": simulator.current_lat,
                }
                dashboard.render(state, status=status, mumu_status="已暂停")

            elapsed = time.time() - loop_start
            sleep_time = max(0.01, interval - elapsed)
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        dashboard.stop()
        print("\n" + "=" * 55)
        print("🏁 运动模拟已结束！本次跑步统计:")
        print(f"   - 总耗时: {format_seconds(simulator.total_elapsed_time)}")
        print(f"   - 总里程: {simulator.total_distance_traveled:.1f} 米 ({simulator.total_distance_traveled / 1000.0:.2f} km)")
        print(f"   - 总圈数: 第 {simulator.lap_count} 圈")
        print(f"   - 总步数: 约 {simulator.total_steps} 步")
        avg_v = (simulator.total_distance_traveled / simulator.total_elapsed_time) if simulator.total_elapsed_time > 0 else 0
        if avg_v > 0:
            pace_sec = 1000.0 / avg_v
            print(f"   - 平均速度: {avg_v * 3.6:.1f} km/h (配速 {int(pace_sec // 60)}'{int(pace_sec % 60):02d}\"/km)")
        print("=" * 55)

        if is_interactive:
            try:
                input("\n按回车键退出程序...")
            except Exception:
                pass


if __name__ == "__main__":
    main()

