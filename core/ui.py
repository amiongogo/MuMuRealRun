"""
Interactive Terminal UI and Dashboard for MuMuRealRun.
Renders real-time statistics, progress bars, and handles non-blocking keyboard controls.
"""

import sys
import time
from typing import Dict, Any, Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.progress_bar import ProgressBar
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


def format_seconds(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    s = int(round(seconds))
    hrs = s // 3600
    mins = (s % 3600) // 60
    secs = s % 60
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


class TerminalDashboard:
    """Renders real-time running simulation dashboard in the terminal."""

    def __init__(self, target_dist_m: float = 0.0, target_laps: int = 0, route_name: str = ""):
        self.target_dist_m = target_dist_m
        self.target_laps = target_laps
        self.route_name = route_name
        self.console = Console() if RICH_AVAILABLE else None
        self.live: Optional[Any] = None

    def start(self):
        if RICH_AVAILABLE and self.console:
            self.live = Live(console=self.console, refresh_per_second=4, transient=False)
            self.live.start()

    def stop(self):
        if self.live:
            self.live.stop()
            self.live = None

    def render(self, state: Dict[str, Any], status: str = "RUNNING", mumu_status: str = "Connected"):
        """Update dashboard state."""
        if not RICH_AVAILABLE or not self.live:
            # Fallback simple line
            dist = state.get("total_distance_m", 0)
            spd = state.get("speed_kmh", 0)
            pace = state.get("pace_str", "")
            lap = state.get("lap", 1)
            t = format_seconds(state.get("total_elapsed_sec", 0))
            print(f"[{status}] 里程: {dist:.1f}m | 速度: {spd:.1f}km/h | 配速: {pace} | 圈数: {lap} | 耗时: {t}\r", end="")
            return

        dist = state.get("total_distance_m", 0.0)
        elapsed = state.get("total_elapsed_sec", 0.0)
        speed_kmh = state.get("speed_kmh", 0.0)
        speed_mps = state.get("speed_mps", 0.0)
        pace = state.get("pace_str", "0'00\"")
        avg_pace = state.get("avg_pace_str", "0'00\"")
        lap = state.get("lap", 1)
        steps = state.get("steps", 0)
        lng = state.get("lng", 0.0)
        lat = state.get("lat", 0.0)

        # Progress calculation
        pct = 0.0
        eta_str = "--:--"
        if self.target_dist_m > 0:
            pct = min(1.0, dist / self.target_dist_m)
            remaining_m = max(0.0, self.target_dist_m - dist)
            if speed_mps > 0.1:
                eta_str = format_seconds(remaining_m / speed_mps)
            else:
                eta_str = "N/A"
        elif self.target_laps > 0:
            pct = min(1.0, lap / max(1, self.target_laps))

        # Status badge
        if status == "RUNNING":
            status_text = "[bold green]▶ 正在模拟跑步中 (RUNNING)[/bold green]"
        elif status == "PAUSED":
            status_text = "[bold yellow]⏸ 已暂停 (PAUSED)[/bold yellow]"
        elif status == "COMPLETED":
            status_text = "[bold cyan]✔ 目标已达成 (COMPLETED)[/bold cyan]"
        else:
            status_text = f"[bold white]{status}[/bold white]"

        # Metrics Table
        table = Table.grid(expand=True, padding=(0, 2))
        table.add_column(ratio=1)
        table.add_column(ratio=1)

        col1_text = (
            f"[cyan]跑步里程:[/cyan] [bold white]{dist:.1f} m[/bold white]"
            + (f" / {self.target_dist_m:.0f} m" if self.target_dist_m > 0 else "") + "\n"
            f"[cyan]实时配速:[/cyan] [bold green]{pace}/km[/bold green] (均配: {avg_pace})\n"
            f"[cyan]瞬时时速:[/cyan] [bold white]{speed_kmh:.1f} km/h[/bold white] ({speed_mps:.2f} m/s)\n"
            f"[cyan]当前圈数:[/cyan] [bold magenta]第 {lap} 圈[/bold magenta]"
            + (f" / 共 {self.target_laps} 圈" if self.target_laps > 0 else "")
        )

        lat_offset = state.get("lateral_offset_m", 0.0)
        lat_offset_str = f"{lat_offset:+.1f}m"

        col2_text = (
            f"[cyan]累计耗时:[/cyan] [bold white]{format_seconds(elapsed)}[/bold white]\n"
            f"[cyan]预估剩余:[/cyan] [bold yellow]{eta_str}[/bold yellow]\n"
            f"[cyan]估算步数:[/cyan] [bold white]{steps} 步[/bold white] (~170 spm)\n"
            f"[cyan]当前坐标:[/cyan] [bold dim]{lng:.6f}, {lat:.6f}[/bold dim] [dim]({lat_offset_str})[/dim]"
        )

        table.add_row(col1_text, col2_text)

        # Progress bar
        bar = ProgressBar(total=100, completed=pct * 100, width=55)

        footer_text = (
            f"[dim]路线: {self.route_name} | 模拟器: {mumu_status}\n"
            f"快捷键: [bold white][空格/P][/bold white] 暂停/继续 | [bold white][+][/bold white] 加速 | [bold white][-][/bold white] 减速 | [bold white][Ctrl+C / Q][/bold white] 退出[/dim]"
        )

        content = Table.grid(expand=True, padding=(0, 0))
        content.add_row(status_text)
        content.add_row("")
        content.add_row(table)
        content.add_row("")
        if self.target_dist_m > 0:
            content.add_row(Text.assemble(("完成进度: ", "cyan"), (f"{pct * 100:.1f}%  ", "bold green")))
            content.add_row(bar)
            content.add_row("")
        content.add_row(footer_text)

        panel = Panel(
            content,
            title="[bold blue]MuMuRealRun 运动模拟控制台[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )

        self.live.update(panel)


def check_keyboard_input() -> Optional[str]:
    """Check non-blocking keyboard input on Windows and Unix."""
    if sys.platform == "win32":
        import msvcrt
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Handle special characters / decoding
            try:
                char = ch.decode("utf-8", errors="ignore").lower()
                return char
            except Exception:
                return None
    return None
