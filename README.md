# Neo Circuit Racer（独立 EXE 版）

一个带有**简化物理引擎**（`pymunk`）与完整 UI（菜单、倒计时、HUD、暂停、结算）的 2D 赛车小游戏。

## 功能亮点

- 车辆物理：
  - 引擎推进力
  - 刹车力
  - 线性阻力 + 滚动阻力
  - 横向抓地力（减少“打滑感”）
  - 随速度变化的转向稳定性
- 比赛机制：
  - 起跑倒计时
  - 计圈与最佳圈速
  - 完赛判定（默认 3 圈）
- UI 设计：
  - 主菜单
  - 实时 HUD（速度、圈数、总时间、最佳圈速）
  - 暂停层与结算层

## 运行方式（开发环境）

```bash
python -m pip install -r requirements.txt
python racer_game.py
```

## 打包为单独 EXE（Windows）

### 方式 1：一键脚本

双击 `build_exe.bat`，打包完成后 EXE 在：

```text
dist\NeoCircuitRacer.exe
```

### 方式 2：手动命令

```bash
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --onefile --windowed --name NeoCircuitRacer racer_game.py
```

## 操作方式

- `W / ↑`：油门
- `S / ↓`：刹车
- `A,D / ←,→`：转向
- `ESC`：暂停/继续

## 目录

- `racer_game.py`：游戏主程序
- `requirements.txt`：依赖
- `build_exe.bat`：Windows 一键打包脚本


## 常见问题（Windows）

### 报错：`[Errno 2] No such file or directory: 'racer_game.py'`

这是因为你在 `C:\Users\Administrator>` 目录直接执行了：

```bat
python -m py_compile racer_game.py
```

但该目录下没有 `racer_game.py` 文件。这个命令会在**当前目录**找文件，所以会报找不到。

正确做法：先进入游戏项目目录，再执行命令。

```bat
cd /d D:\你的项目路径\Project_price
python -m py_compile racer_game.py
python racer_game.py
```

你也可以先用下面命令确认当前目录里是否有这个文件：

```bat
dir racer_game.py
```

如果你是双击 `build_exe.bat` 打包，也请确保是在项目目录内运行，或把脚本和 `racer_game.py` 放在同一目录。
