# 弹性碰撞仿真器

基于 Python 和 pygame 的物理竞赛教学仿真程序，包含：

- 两自由质点一维弹性碰撞
- 重力场中质点与定轴细杆碰撞，并按目标碰撞点速度反算初始摆角/角速度

## 运行

本项目固定使用 Conda 的 `agent` 环境，不要安装到全局 `base` 环境。

```bash
conda activate agent
conda install -c conda-forge pygame-ce=2.5.8
python main.py
```

如果当前终端不方便执行 `conda activate`，可以直接使用环境解释器：

```bash
D:\APPS\anaconda\envs\agent\python.exe -m pip install -r requirements.txt
D:\APPS\anaconda\envs\agent\python.exe main.py
```

`agent` 使用 Python 3.14；项目依赖声明为 `pygame-ce`，它提供兼容的
`import pygame` 接口，并有适用于该 Python 版本的 Windows 二进制包。

也可以继续使用旧入口：

```bash
D:\APPS\anaconda\envs\agent\python.exe collision_simulator.py
```

## 目录结构

- `config.py`：窗口、布局和颜色配置
- `utils.py`：通用工具函数
- `core/`：pygame 显示资源和字体
- `render/`：通用绘图原语
- `ui/`：滑块、按钮、输入框
- `effects/`：粒子和冲击波效果
- `models/`：模型基类及两个碰撞模型
- `main.py`：应用程序入口和事件循环

## 质点—细杆模型约定

第二个模型中，小球静止在杆的碰撞高度，输入的 `vc` 是距转轴 `h` 处
碰撞点的线速度，不是小球入射速度，也不是杆尖端速度。碰撞前细杆在重力
场中从初始位置摆到竖直向下位置，程序使用

```text
I = M L^2 / 3                 vc = h * wc
1/2 I wc^2 = 1/2 I w0^2 + MgL/2 * (1 - sin(theta0))
```

自动反解初始状态。可由重力从静止释放达到的目标速度对应 `0°--90°`
的初始摆角（角度从竖直向下方向量起）；若目标速度超过该范围，则固定从
`90°` 出发并补充初始角速度。将 `g` 设为 `0` 时，模型自动使用纯初始角
速度分支。碰撞瞬间采用完全弹性冲量模型，验证绕转轴的角动量守恒；碰后
细杆继续在重力场中按物理摆运动，小球按碰撞后的速度做水平运动。
