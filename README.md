# MuMuRealRun - 安卓模拟器控制与轨迹仿真学习项目

[![Release](https://img.shields.io/github/v/release/amiongogo/MuMuRealRun?color=green)](https://github.com/amiongogo/MuMuRealRun/releases)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows-brightgreen.svg)](https://windows.microsoft.com/)
[![MuMu Version](https://img.shields.io/badge/MuMu%20Player-12.0%2B-orange.svg)](https://mumu.163.com/)

**MuMuRealRun** 是一个用于**探索与学习安卓模拟器自动化控制、ADB 调试协议以及地理信息系统（GIS）轨迹数学仿真**的开源学习项目。

项目参考了部分开源虚拟定位与运动仿真的设计思想，基于网易 MuMu 模拟器提供的命令行管理工具与 ADB 桥接接口构建，展示了如何在模拟器环境进行硬件级传感器控制、平滑路径插值以及多坐标系无缝换算。

---

## 📚 学习与技术研究内容

本项目主要涵盖以下技术点的实践与探索：

1. **模拟器底层控制与接口封装**
   - 探索通过网易官方提供的管理工具 `MuMuManager.exe` 与安卓内核进行底层通信，实现模拟器状态监控、多开实例管理与定位数据同步。
   - 结合 ADB（Android Debug Bridge）进行前台应用监控与辅助调试。

2. **地理坐标系转换与数学纠偏**
   - 深入研究 **WGS-84**（国际标准 GPS）、**GCJ-02**（国内火星坐标系）与 **BD-09**（百度坐标系）之间的非线性加偏与逆向迭代还原算法，避免不同地图数据源之间的坐标漂移。

3. **人体运动动力学与平滑轨迹仿真**
   - **速度连续随机波动**：使用奥恩斯坦-乌伦贝克 (Ornstein-Uhlenbeck) 随机过程模拟自然运动速度的渐进起伏。
   - **大圆航线与折线插值**：利用 Haversine 球面距离公式与方位角（Bearing）计算，在离散路径点间实现均匀时间步长的平滑坐标推演。
   - **曲率减速与扰动模拟**：根据航向角突变自适应施加弯道降速，模拟自然转弯减速物理现象。

4. **Web 可视化与参数化几何拟合**
   - 基于 Leaflet.js 与 Python 标准库 `http.server` 构建轻量级 Web 交互工具。
   - 实现**标准 400 米椭圆田径场跑道的解析几何拟合算法**，只需给定 3 个约束点即可数学生成两条平行直道与两端半圆弯道。

5. **环境自适应与跨机器部署**
   - 通过 Windows 注册表、系统运行进程表及环境变量实现多级自动探测，摆脱对本机固定路径的依赖。

---

## 🚀 使用指南

### 1. 环境准备
- 操作系统：Windows 10 / 11 (64位)
- 模拟器：[网易 MuMu 模拟器 12](https://mumu.163.com/)
- Python：Python 3.8 及以上版本

### 2. 依赖安装
本项目仅依赖 `rich`（终端美化）和 `PyYAML`（配置解析）：
```bash
pip install -r requirements.txt
# 或使用 uv:
uv pip install -r requirements.txt
```

---

### 3. 运行方式

#### 方式一：一键脚本运行（推荐）
直接双击运行项目根目录下的 **[`start.bat`](file:///c:/MyTools/playground/runningMIGU/start.bat)**：
- 脚本会自动检测 Python 环境与依赖库（缺失时自动补齐）；
- 弹出交互式控制台菜单，支持直接开始模拟、环境自检、设置自定义里程或圈数。

*(PowerShell 用户可直接执行 `.\run.ps1`)*

#### 方式二：命令行启动
```bash
# 1. 环境自检 (Doctor): 检查 MuMu 模拟器、MuMuManager 与 ADB 端口就绪情况
python main.py --doctor

# 2. 默认启动 (按照 config.yaml 配置无限循环模拟运行)
python main.py

# 3. 指定目标里程 (例如 3000 米，基础速度 3.5 m/s)
python main.py --distance 3000 --speed 3.5

# 4. 指定目标圈数 (例如 5 圈)
python main.py --laps 5
```

---

## ⌨️ 运行时实时交互快捷键

在终端运行模拟期间，支持以下非阻塞键盘操作：
- **`[空格 / P]`**：暂停 / 继续模拟
- **`[+]`**：实时增加基准速度 (+0.2 m/s)
- **`[-]`**：实时降低基准速度 (-0.2 m/s)
- **`[Q / Ctrl+C]`**：平稳停止运行并输出本次运动统计数据

---

## 🗺️ 路线生成与可视化工具

本项目内置了 **Web 地图可视化路线生成器**，支持在卫星地图上看线并自动生成轨迹文件。

### 启动编辑器
- **双击快捷启动**：双击运行 **[`draw_route.bat`](file:///c:/MyTools/playground/runningMIGU/draw_route.bat)**；
- **菜单启动**：双击 `start.bat` 后在菜单中选择 `[5]`；
- **命令行启动**：`python route_editor.py` 或 `python main.py --editor`。

### 两种轨迹制作模式
1. **操场跑道智能拟合**：
   - 放大卫星地图找到跑道；
   - 依次在跑道上点击 **3 个约束点**（直道起点、直道终点、对向直道点）；
   - 系统将自动计算几何参数并拟合出光滑闭合的标准跑道。
2. **自由绘制模式**：
   - 在地图上依次点击道路节点；
   - 点击“闭合回路”与“曲线平滑插值”即可生成平滑多边形路线。
3. **一键保存**：
   - 在右侧输入文件名（如 `ZJGroute.txt`），点击 **【💾 直接保存至项目文件】** 即可供主程序调用。

---

## ⚙️ 配置文件参数说明 (`config.yaml`)

```yaml
# 模拟器设置
mumu:
  path: ""             # 模拟器安装路径。留空 "" 时将自动通过注册表与进程探测
  vm_index: 0          # 多开模拟器序号，单开默认为 0
  auto_launch: true    # 若模拟器未启动，是否自动拉起
  backend: "mumu_manager"

# 运动与仿真动力学配置
run:
  route_file: "ZJGroute.txt"  # 路线文件
  coord_type: "gcj02"        # 输入路线坐标系: gcj02(高德), wgs84(GPS), bd09(百度)
  speed_mps: 3.2             # 基础速度 (米/秒)
  speed_jitter_pct: 0.10     # 速度随机波动比例 (±10%)
  gps_jitter_meters: 0.6     # GPS 自然微弱高频抖动 (米)
  lateral_variance_meters: 2.2 # 轨迹横向方差/跑道宽度 (米，建议 1.5~3.5 米，模拟多道次扩散)
  lane_drift_per_lap: true   # 是否启用多圈道次自然漂移（跨圈时平滑变换内外道分布）
  slow_down_on_turns: true   # 弯道自动减速
  interval_sec: 1.0          # 定位刷新间隔(秒)

# 目标控制
target:
  distance_meters: 0         # 目标总里程 (米)，0 表示不限制
  laps: 0                    # 目标圈数，0 表示不限制
  infinite_loop: true        # 是否无限循环运行（默认 true，按 Q 停止）

# ADB 辅助监控
adb:
  auto_connect: true         # 启动时是否自动连接 ADB
  target_package: ""         # 可选：需要监控前台状态的目标应用包名
```

---

## ⌨️ 常用命令行参数表

| 参数 | 缩写 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `--route` | `-r` | 指定路径文件 | `-r ZJGroute.txt` |
| `--speed` | `-s` | 设定基础速度 (m/s) | `-s 3.2` |
| `--distance` | `-d` | 设定目标里程 (米) | `-d 2500` |
| `--laps` | `-l` | 设定目标圈数 | `-l 5` |
| `--coord-type` | `-c` | 输入路线坐标系 (`gcj02`/`wgs84`/`bd09`) | `-c gcj02` |
| `--lateral-variance` | `-lv` | 设定横向方差与道次扩散范围 (米) | `-lv 2.5` |
| `--vm-index` | `-v` | MuMu 模拟器实例编号 (默认 0) | `-v 0` |
| `--mumu-path` | `-m` | 手动指定 MuMu 安装路径 | `-m "D:\Games\MuMu Player 12"` |
| `--doctor` | | 运行环境诊断与接口自检 | `python main.py --doctor` |
| `--editor` | | 启动 Web 路线可视化编辑器 | `python main.py --editor` |

---

## 📄 免责声明与使用条款

本项目仅供计算机软件工程、安卓模拟器自动化控制及地理信息系统（GIS）算法的学习、教学与技术研究使用。请合理使用模拟工具，遵守相关软件的使用协议与规定。
