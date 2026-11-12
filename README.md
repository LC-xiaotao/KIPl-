# KiPI 电源完整性仿真工具

KiPI 是一款面向 PCB 设计的开源电源完整性分析工具，支持独立运行、KiCad 插件以及嘉立创 EDA 专业版工程导入，帮助工程师在设计阶段评估供电质量、定位薄弱环节，为布局布线和电源网络优化提供依据。

## 主要功能

- **直流压降与电热分析**：计算供电路径中的电压降、电流密度、过孔电流和铜损，支持电热耦合分析，识别供电不足与局部发热问题。
- **PDN 阻抗分析**：分析电源分配网络的频率响应，结合去耦电容模型和目标阻抗，评估去耦方案。
- **开关电源耦合噪声分析**：评估开关节点、电感及回流路径对信号网络的干扰，辅助检查噪声裕量。
- **结果展示与报告**：通过交互式 3D 视图查看分析结果，支持导出 HTML 或 PDF 报告。
- **简体中文与 AI 助手**：提供中文界面，可通过自然语言辅助读取板卡、配置参数、运行分析和整理结果。AI 助手需要自行配置模型服务。

## 文件格式

支持 KiCad 板卡（`.kicad_pcb`）、嘉立创 EDA 专业版工程归档（`.epro2`）、ODB++、HyperLynx（`.hyp`）和 KiPI 快照（`.kipi.json.gz`）。

`.epro2` 支持原生读取网络、走线、铜皮、焊盘、过孔、元件、板框和叠层，无需先转换为 ODB++。工程需包含 PCB 数据且未加密；`.eprj2`、`.eprj3` 暂不支持。

## Windows 启动

安装 Python 3.10–3.13 后，在项目目录运行：

```powershell
python kipi_launcher.py
```

也可双击 `kipi_launcher.pyw`。首次运行会显示依赖安装窗口，按提示安装后打开软件。首次加载 3D 组件可能较慢，请等待主窗口出现。

### 生成 EXE 启动工具

```powershell
python -m pip install pyinstaller
python tools/build_windows_exe.py
```

生成的 `KiPI.exe` 位于项目根目录和 `dist/`。它是轻量启动工具，需与项目文件一起使用，并与 `kipi_launcher.pyw` 保持在同一目录。双击后无需打开命令行；已启动时会唤回现有窗口。EXE 和构建目录不纳入源码版本控制。

## 文档与许可证

- [用户指南](docs/help.html)
- [求解器指南](docs/solver-guide.html)
- [更新日志](docs/CHANGELOG.md)

本项目基于 [Drew Maatman 的 KiPI](https://github.com/drewsum/KiPI) 开发，采用 [GPL v3](LICENSE) 开源许可证，适用于 PCB 电源设计验证、方案比较、教学研究与二次开发。
