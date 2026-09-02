# 弹性碰撞仿真器

基于 Python 和 pygame 的物理竞赛教学仿真程序，包含：

- 两自由质点一维弹性碰撞
- 质点与定轴细杆碰撞（失重环境）

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
