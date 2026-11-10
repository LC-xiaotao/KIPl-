<p align="center">
  <img src="resources/kipi.gif" alt="KiPI logo" width="128">
</p>

# KiPI — 电源完整性仿真器（独立版 / KiCad 插件 / 嘉立创EDA专业版）

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![KiCad 9.0.3+](https://img.shields.io/badge/KiCad-9.0.3%2B-314cb0.svg?logo=kicad&logoColor=white)](#安装与运行)
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#安装与运行)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776ab.svg?logo=python&logoColor=white)](#安装与运行)

**第一次接触电源完整性？先看 [求解器指南](docs/solver-guide.html)：它介绍了什么是 PI、为什么重要，以及 KiPI 的网格、DC、热、AC 和耦合噪声求解器如何工作。**

KiPI 是一款电源完整性分析工具，支持三种运行方式：独立运行、作为 KiCad 9/10 的 IPC 插件，或配合 **嘉立创EDA专业版（EasyEDA Pro）** 通过 ODB++ 导出使用。包含三种分析模式：

* **DC：压降与电流密度。** 定义 VRM、负载（引脚电流）和串联器件（磁珠、电阻、负载开关），逐网络、逐铜层计算压降；在可旋转的 3D 视图中查看电压、电流密度、过孔电流、铜损和（可选的）板温，并对负载、VRM、过孔和温度做 PASS/FAIL 判定，导出交互式 HTML 或 PDF 报告。
* **AC：PDN 阻抗。** 为去耦电容建立 RLC 模型，在器件电源引脚放置探针，在频域扫描电源分配网络（平面、过孔、安装孔和电容）的阻抗；对照平坦或自定义目标阻抗检查，并可根据负载瞬态指标计算目标阻抗。
* **耦合噪声：开关电源对信号网络的串扰。** 把 buck/boost 电源当作干扰源，KiPI 根据布局构建开关节点、电感和电容的纹波波形，计算它们通过电容、互感与共地耦合到指定受害网络上的噪声；按逻辑电平的噪声容限检查接收端（高电平和低电平两种状态），并在 3D 视图中显示噪声耦合位置。

第一次使用？**[用户指南](docs/help.html)**（KiPI 内的 **Help** 按钮或 **F1**）逐步介绍每个按钮、工作流和结果含义。KiPI 中每个控件都有工具提示。

![Current density with flow arrows through the +12V input path and the U201 eFuse, with the Series links table](docs/images/current_density.png)

**状态：1.0.0（稳定版）**（[更新日志](docs/CHANGELOG.md)）。原项目地址：<https://github.com/drewsum/KiPI>。

## 最新特性

* **嘉立创EDA专业版集成**：扩展一键把当前 PCB 导出为 ODB++，KiPI 直接打开；修复了 EasyEDA ODB++ 的单位与铜厚读取，0.48 mm 介质 + 35 µm 铜可得到正确的 1.58 mm 四层叠层。
* **简体中文界面与中文报告**：菜单、工具栏、设置面板、3D 控件、叠层图、容差图和 Qt 标准按钮均已汉化；DC、AC、耦合噪声和容差报告（HTML 与 PDF）跟随界面语言，图表使用中文字体。
* **AI 助手**：支持多家模型供应商，可用自然语言读取板卡、修改仿真设置、运行 DC/AC/耦合噪声求解并导出报告；支持模型列表拉取、思考过程折叠、Markdown 渲染、附件上传和按工程保存的对话。
* **窄窗口适配**：右侧设置面板最小宽度从 420 px 降到 300 px，表单自动换行、表格横向滚动，窗口变窄时优先压缩面板而不是挤掉 3D 视图。
* **波形与阻抗视图缩放**：Coupled Noise 的 **Waveforms** 与 AC 的 **Impedance** 视图新增导航工具栏，支持平移、框选缩放、复位和保存图片；波形图还支持滚轮缩放、Shift+滚轮调纵轴、双击复位。
* **3D 视图修复**：解决 Qt 6 下中文界面事件过滤器导致 3D 标签页黑屏的问题。

## 安装与运行

KiPI 可以用三种方式运行：

* **作为 KiCad 插件（主要方式）**：在 PCB 编辑器点击 **KiPI** 按钮，KiPI 读取当前打开的板卡。KiPI 文件夹必须位于 KiCad 的插件目录中；首次点击会自动安装依赖。
* **独立运行**：用自带的启动器启动，不依赖 KiCad。文件夹可以放在任意位置，启动器首次运行时安装依赖。支持 KiCad 7–10 板卡（`.kicad_pcb`）、ODB++、HyperLynx（`.hyp`）和 KiPI 快照（`.kipi.json.gz`）。
* **配合嘉立创EDA专业版**：安装扩展后一键导出 ODB++，再用 KiPI 独立版打开。

### 嘉立创EDA专业版

1. 构建扩展（需要 Node.js 20+）：

   ```powershell
   cd easyeda_extension
   npm install
   npm run build
   ```

   产物为 `easyeda_extension/build/kipi-power-integrity_v1.0.0.eext`。

2. 在嘉立创EDA专业版中导入：**高级 → 扩展管理器… → 导入**（旧版客户端：**设置 → 扩展 → 扩展管理器… → 导入扩展**）。

3. 打开 PCB，使用 **KiPI → 导出 ODB++ 到 KiPI…**，保存 `.tgz` 文件。文件包含铜皮、网络、焊盘、过孔、板框和叠层。

4. 启动 KiPI 独立版（`python kipi_launcher.pyw`，或安装后的 `kipi` 命令），点击 **打开** 选择刚才的 `.tgz`。KiPI 会标记为 *EasyEDA Pro (ODB++)*。

ODB++ 不包含元件 3D 模型，因此嘉立创EDA专业版的板卡在 3D 视图中显示铜皮、过孔、焊盘和板框，不显示元件本体。扩展源码和说明见 [`easyeda_extension/`](easyeda_extension/README.md)。

### 简体中文界面与报告

KiPI 默认跟随电脑语言：中文系统显示中文，其他系统显示英文。工具栏的 **Language / 语言** 菜单可选择 **跟随系统**、**简体中文** 或 **English**；切换会立即应用到当前界面并保存到 KiPI 设置，下次启动保持不变。`KIPI_LANG=zh_CN` 强制中文，`KIPI_LANG=en` 强制英文（优先级最高）。界面词条位于 [`kipi/gui/translations/`](kipi/gui/translations/)，`KIPI_I18N_LOG=<file>` 会记录尚未翻译的字符串。

导出的 DC、AC、耦合噪声和容差报告（HTML 与 PDF）与界面语言一致，图表使用中文字体（微软雅黑 / PingFang SC / Noto Sans CJK）。报告词条位于 [`kipi/core/translations/`](kipi/core/translations/)。网络名、位号、层名、单位和代码保持原样。AI 助手面板的界面文字目前固定为中文。

### AI 助手

KiPI 内置 AI 助手，可以用自然语言操作插件：读取当前板卡、列出网络和元件、添加 VRM/负载、运行 DC/AC/耦合噪声求解、读取结果并导出报告。从工具栏 **AI 助手** 打开（与设置面板同区域），点击 **设置…** 配置。

**模型供应商**

- 内置供应商：OpenAI、Anthropic、DeepSeek、通义千问、智谱 GLM、Kimi、Gemini、Ollama、自定义。
- 自定义接口支持 **OpenAI 兼容（chat/completions）** 或 **Anthropic Messages（原生）**。
- 支持填写 **配置名称**、接口地址、模型和 API Key；接口地址可填根地址（如 `https://api.example.com/v1`），也可粘贴完整端点，KiPI 会自动修正。
- 填好地址和 Key 后自动拉取模型列表（也可点 **拉取模型** 手动刷新）；选择模型后自动填入已知的最大输出 token，仍可手动修改。
- API Key 只保存在本机 KiPI 设置中（明文），建议使用受限 Key，或在共享机器上使用本地模型。

**对话与显示**

- 回复按 Markdown 渲染：标题、粗体、斜体、列表、表格、引用、代码块和链接；点击链接用系统浏览器打开。
- 模型返回思考内容时，以折叠的 **▶ 思考过程（N 字）** 显示，点击展开、再点收起；思考内容不会回传给模型。
- **每个工程/板卡有独立对话**：切换板卡自动保存当前对话并加载目标工程的对话，重新打开工程可恢复历史；对话保存在 KiPI 数据目录（`KIPI_HOME`，Windows 默认 `%LOCALAPPDATA%\KiPI`）。
- 默认最多 **30 轮**工具调用（设置中可调 1–200）；达到上限会暂停并显示 **继续**，保留完整上下文，不会直接终止任务。
- **快速** 复选框：放粗 DC/AC 网格、减少 AC 扫频点、关闭噪声板级模型并减少谐波，适合先快速判断；结果会标注为近似值，需要精确结果时关闭后重算。
- 模型思考时状态栏会显示已用时间；求解工具结果包含 `elapsed_s`，便于判断时间花在模型还是求解上。请求只发送最近的对话和精简后的工具结果，避免历史过长拖慢响应。
- 支持 **附件…** 上传 PDF、Word（`.docx`）、Excel/CSV/TSV、文本、Markdown、JSON、HTML、YAML、XML；本地提取文字，文件本身不会上传。长附件只随消息发送前约 3 万字符（单条消息约 6 万字符），完整文本保存在当前对话中，助手可用 `list_attachments` / `search_attachment` / `read_attachment` 按关键词或页码读取全文，并注明页码；扫描版 PDF 需要先 OCR。
- 工具调用记录、JSON 结果和思考内容保持纯文本，避免被 Markdown 改写。

**能力范围**

助手通过工具操作插件，而不是凭空回答：读取板卡、网络、元件和已有设置；添加/删除 VRM、负载、AC 探针、噪声干扰源和受害网络；运行 `solve_dc`、`solve_ac`、`solve_noise`；返回负载压降、VRM、网络组、探针阻抗、受害网络噪声与裕量；配置 **DC 热分析**（`set_thermal`：环境温度、气流、迭代次数、负载发热和温度限值），求解后返回各铜层峰值温度、温升和 PASS/FAIL；导出 DC/AC/噪声报告（HTML 或 PDF）。系统提示要求助手先核对网络/位号、明确标注假设，并且只报告工具返回的数据。

## KiCad 插件安装

### 要求

* **KiCad 9.0.3 或更高版本**。在 KiCad 10 上开发，已在 KiCad 9 验证。
* **Python 3.10–3.13**，即 KiCad 运行插件所用的 Python。
  * **Windows**：使用 KiCad 自带的 Python 3.11，无需额外安装。
  * **Linux**：使用系统 Python。如果发行版默认 Python 3.14，pip 需要编译部分包，请安装 `build-essential`、`python3-dev` 等编译依赖。
  * **macOS**：KiCad 自带的 Python 3.9 太旧，请安装 Python 3.12，并在 *Preferences → Plugins* 中选择它作为 **Python interpreter**。

### 通过 Plugin and Content Manager 安装

1. 在 KiCad 中启用 **Preferences → Plugins → Enable KiCad API**。
2. 打开 **Plugin and Content Manager**，在 *Plugins* 中找到 **KiPI** 并点击 **Install**。如果列表中还没有本版本，请使用下面的手动安装。
3. 重启 PCB 编辑器并点击 **KiPI**；首次点击会安装依赖。PCM 会随新版本提供更新。

### 手动安装

1. 在 KiCad 中启用 **Preferences → Plugins → Enable KiCad API**。
2. 将本仓库克隆、链接或复制到 KiCad 插件目录。下面以 KiCad 10 为例；KiCad 9 把 `10.0` 换成 `9.0`。Windows 的 *Documents* 可能被重定向到 OneDrive：

   ```powershell
   $plug = "$([Environment]::GetFolderPath('MyDocuments'))\KiCad\10.0\plugins"
   New-Item -ItemType Junction -Path "$plug\KiPI" -Target "<path to this repo>"
   ```

   macOS 的目录是 `~/Documents/KiCad/10.0/plugins`，Linux 是 `~/.local/share/kicad/10.0/plugins`：

   ```sh
   ln -s "<path to this repo>" ~/Documents/KiCad/10.0/plugins/KiPI          # macOS
   ln -s "<path to this repo>" ~/.local/share/kicad/10.0/plugins/KiPI       # Linux
   ```

3. 重启 PCB 编辑器。KiCad 会在后台创建插件的 Python 环境，只安装 KiPI 启动所需的 `kicad-python`，因此 **KiPI** 工具栏按钮几秒内就会出现。如果一直没有出现，在 *Preferences → Plugins* 中右键该动作并选择 *Recreate Plugin Environment*。
4. 点击 **KiPI**。首次会打开设置窗口，列出要安装的包及大小（Windows 约 254 MB 下载），以及可选的 PARDISO 求解器；点击 **Install** 前不会安装任何东西，完成后 KiPI 自动打开。之后点击会直接打开。

## 独立版安装

1. 安装 **Python 3.10–3.13**。Linux 还需要 `python3-venv`（Debian/Ubuntu），以及设置窗口所需的 `python3-tk`。
2. 将本仓库放在任意位置。
3. 启动 KiPI：

   ```sh
   python kipi_launcher.py                      # 也可以带一个板卡文件
   python kipi_launcher.py <board>.kipi.json.gz
   ```

   Windows 上也可以双击 **`kipi_launcher.pyw`**，或直接双击项目根目录的 **`KiPI.exe`**（与 `kipi_launcher.pyw` 同目录），无需打开终端。首次启动会显示依赖安装窗口，点击 **Install** 后开始安装；完成后启动 KiPI。

   `KiPI.exe` 是一个轻量启动器，不包含 KiPI 本体：它使用已安装的 KiPI 环境启动，首次运行仍会创建环境。重新打包：

   ```powershell
   python -m pip install pyinstaller
   python tools/build_windows_exe.py
   ```

4. 依赖环境位于 KiPI 文件夹之外，`KIPI_HOME` 可以改到别处：

   | 系统 | KiPI 环境目录 |
   |---|---|
   | Windows | `%LOCALAPPDATA%\KiPI` |
   | macOS | `~/Library/Application Support/KiPI` |
   | Linux | `~/.local/share/kipi` |

   如果 KiPI 是从 KiCad 插件安装的，独立版会复用 KiCad 为插件创建的环境，依赖只安装一次。`--own-env` 可强制使用独立环境。

常用启动器参数：

```sh
python kipi_launcher.py --setup              # 重新打开依赖设置窗口
python kipi_launcher.py --add-pardiso        # 安装 PARDISO（或 --remove-pardiso）
python kipi_launcher.py --repair             # 重新安装全部依赖
python kipi_launcher.py --reset              # 删除 KiPI 环境
python kipi_launcher.py --own-env            # 使用 KiPI 自己的环境
python kipi_launcher.py --create-shortcut    # 添加到开始菜单 / 应用菜单
```

安装失败时，启动器会说明原因；安装器输出在环境目录旁的 `logs` 文件夹中。

### 可选：PARDISO 加速

安装 [`pypardiso`](https://pypi.org/project/pypardiso/) 后，KiPI 使用 Intel MKL 的多线程 PARDISO 求解器替代 SciPy 的单线程求解器。大型电源轨的求解时间可显著缩短（例如 645k 未知量从约 8 秒降到 1.2 秒）。Windows 下载约 210 MB，Linux 约 320 MB；macOS 和 ARM 没有可用的 MKL 包。

启动器首次安装时会默认尝试安装 PARDISO，可取消；也可以在 **About → Manage dependencies…** 中随时添加或删除。PARDISO 无法加载时，KiPI 会自动回退到 SciPy 并在日志中说明。

## 使用流程

### 1. 打开板卡

在 KiCad PCB 编辑器中点击 **KiPI**，或在独立版中点击 **Open…** 选择板卡文件。KiPI 会读取铜皮、网络、焊盘、过孔、板框和叠层。

* **Reload / Load from KiCad**：在编辑器中修改板卡后重新读取，并保留已保存的 PI 设置。
* **Refill zones**：默认开启，读取前先在 KiCad 中重新填充区域，保证 KiPI 看到的是最新铜皮。
* **Save snapshot… / Open snapshot…**：把提取后的板卡保存为文件，之后无需 KiCad 即可打开。
* **Mode: DC / AC / Noise**：切换分析模式（`Ctrl+1` / `Ctrl+2` / `Ctrl+3`）。
* **Help / F1**：打开离线用户指南。

### 2. 选择电源网络

左侧 **Board** 面板列出设计中的所有网络。只有勾选的网络才参与仿真，也会出现在 PI 设置的引脚选择器中。可使用 **Power & ground only**、**All power** 和 **None** 快速选择；勾选状态随设置保存。

下方是 **Copper layers**、**Display**（按层/网络着色、Z 轴比例、过孔、焊盘、阻焊、丝印、元件 3D 模型）和 **PI Models**（在 3D 中标记当前分析涉及的器件）。

### 3. 建立电源分配模型

右侧 **PI setup** 面板保存电源树，每一项都有 **Add**、**Duplicate** 和 **Remove** 按钮，所有字段都有工具提示。

* **VRMs**：每个稳压器/电源输入/理想源一项，类型可选 **Source**、**LDO**、**Switcher** 或 **Isolated**；填写输出引脚、目标电压、输入引脚、效率或静态电流，以及可选的远程采样、地引脚、负载线、压差、输入范围、DC 精度、限流和多相。
* **Loads**：每个负载一项，填写电源引脚、电流、可选地引脚和 PASS/FAIL 容差。
* **Series links**：跨越两个网络的器件（采样电阻、磁珠、保险丝、负载开关、0 Ω 连接），填写 A 侧、B 侧和电阻；两侧网络都必须是已勾选的电源网络。
* **Solve**：勾选要求解的电源轨组合。
* **Mesh**：`Max edge` 控制 FEA 网格最大边长，越小越准也越慢；**Via plating** 设置各类过孔的镀铜厚度和填充。
* **Thermal**（默认关闭）：勾选 **Electro-thermal co-simulation** 后，损耗会加热板卡，温度升高又改变铜电阻。

设置会在点击 **Save** 和每次求解时保存为板卡旁的 `<board>.kipi-setup.yml`，可以随工程一起提交到版本库。

### 4. 求解 DC

点击 **Solve all**。KiPI 按下游优先的顺序逐条电源轨网格化并求解，每个 VRM 的输入电流包含其下游全部负载。进度显示在日志中，**Cancel** 可中止。

点击 **Report** 生成 HTML 报告，或选择 **PDF**。HTML 报告是单个可移植文件，包含汇总、全部结果表、每条电源轨的交互式 3D 视图、逐层电压/电流密度图和可选的温度图。

### 5. 查看结果

在 **Results** 面板选择网络组和 3D 显示字段：**Voltage**、**Current density**（勾选 **Arrows** 显示流向）、**Power density**、**Via current** 或 **Temperature**。点击任意点可在 Info 面板查看数值，并调整 **Color scale**。

结果标签页包括 **Loads**（有效电压、压降和 PASS/FAIL）、**VRMs**、**Series links**（I²R 损耗）、**Vias**（按电流排序）、**Losses**、**Thermal** 和 **Notes**。**Export ▾** 可写 CSV 或 ParaView 文件，**Save results…** 保存结果，**Open results…** 无需重新求解即可打开。

### 6. AC：PDN 阻抗

把 **Mode** 切到 **AC**。AC 设置与 DC 共享 VRM 和串联器件，并增加：

* **Capacitors**：去耦电容的 RLC 模型（电容、ESL、ESR），或厂商 SPICE 模型；可按 DC 偏置、温度、老化和容差降额。不同封装尺寸的同容值电容请分别建模。
* **Probes**：PDN 阻抗的观测点，通常是器件的电源和地引脚，可设置平坦或自定义目标阻抗；目标阻抗计算器可根据电压容差和负载阶跃计算目标。
* **Sweep**：频率范围、分辨率和电容降额。
* **Mesh**：网格尺寸和镀通孔处的最小边长。

选择 **Rail** 和 **Ground**，点击 **Solve rail**。铜皮和地会做场求解，平面电阻、扩展电感、平面电容、腔体谐振和过孔电感都来自实际布局；电容和串联器件在每个频点接入。AC 分析计算量较大，探针多、网格细会显著增加时间。

**Impedance** 标签绘制每个探针的 |Z| 与频率，并显示目标；**Board map** 显示网格、探针和电容；**Transient** 估算每个探针在负载阶跃下的下冲/过冲。

### 7. 耦合噪声

把 **Mode** 切到 **Noise**。耦合噪声设置把一个 **Switcher** VRM 当作干扰源，把指定的信号网络当作受害网络。

* **Aggressors**：从 switcher VRM 创建干扰源，自动填入开关器件、电感、开关节点和电容；填写开关频率和边沿时间，Coss、Qrr 等数据手册参数可选。
* **Victims**：每个受害网络填写驱动端、接收端、类型（CMOS、开漏、端接、LVDS、模拟输入或未驱动）和逻辑电平，用于计算负载和噪声容限。
* **Capacitors**：与 AC 模式相同的电容模型。
* **Settings**：谐波数、阻尼、受害网络分辨率和 **Board model**（更慢但更准确的变换器铜皮场模型）。

选择 **Aggressor** 后点击 **Solve**。勾选 **Scan nearby nets** 可同时检查干扰源附近的全部信号网络。**Waveforms** 显示开关节点振铃、电感和电容电流以及电源纹波（时域或频谱）；**Results** 列出每个受害网络的峰值噪声、裕量、主导机制和 PASS/FAIL。

**Victim noise** 可按机制（电容、电感、共地）分解；**Victim held high and low** 显示噪声叠加在高/低电平上的情况；**Coupling in 3D** 按噪声贡献给受害网络走线着色；**Hot loops in 3D** 和 **Fields in 3D** 显示电流环路与 H/E 场。

### 常见问题

* **负载显示 DISCONNECTED**：通常是铜皮未布通、区域未填充，或两个电源网络之间缺少串联器件。
* **压降异常**：热焊盘、颈缩走线、过孔数量和平面反焊盘通常是主因；打开 **Current density + Arrows** 查看瓶颈。
* **求解慢**：增大 **Max edge**，减少一次分析的网络数；Windows/Linux x86-64 可安装 PARDISO。
* **“KiPI works with one KiCad at a time”**：可能有未正常退出的 KiCad 进程，请在任务管理器中结束。
* **日志**：每次会话在临时目录写入 `kipi/kipi-<日期>-<时间>-<pid>.log` 和对应的 `.crash.log`；反馈问题时附上日志和 **About → Copy version info**。

## 开发与测试

从源码运行：

```powershell
python -m venv --system-site-packages .venv   # 使用 KiCad 自带的 python.exe
.venv\Scripts\pip install -r requirements.txt -r requirements-standalone.txt -r requirements-dev.txt
.venv\Scripts\python -m kipi tests\data\synthetic.kipi.json   # 独立运行并打开板卡
$env:KIPI_HOST = "plugin"; .venv\Scripts\python -m kipi        # 作为插件连接 KiCad
.venv\Scripts\python -m kipi --dump board.kipi.json.gz         # 只提取板卡，不打开窗口
.venv\Scripts\python -m pytest tests
.venv\Scripts\ruff check .
```

`requirements.txt` 是 KiCad 插件环境启动所需的最小依赖（`kicad-python`）；`requirements-standalone.txt` 是 KiPI 首次安装时补齐的依赖；`tests/core/test_requirements.py` 保证它们与 `pyproject.toml` 一致。

测试按包组织：`tests/core`、`tests/dc`、`tests/ac`、`tests/noise`、`tests/sources`、`tests/gui`、`tests/scripts`。`tests/accuracy` 会对 `examples/validation` 中的板卡做手算对比，用于验证开源实现与专业工具的一致性。

## 代码结构

| 路径 | 作用 |
|---|---|
| `kipi_entry.py`、`plugin.json` | KiCad IPC 插件入口（以插件方式运行 KiPI） |
| `kipi/__main__.py` | `python -m kipi` / `kipi`：独立运行，或设置 `KIPI_HOST=plugin` 作为插件运行 |
| `kipi_launcher.py`、`.pyw` | 独立版启动器：首次启动配置环境，然后在其中启动 KiPI |
| `tools/build_windows_exe.py`、`tools/kipi_shortcut.py` | 打包/实现 Windows 快捷启动 `KiPI.exe` |
| `kipi/launcher/` | 启动器实现：环境、Python 发现、包列表、安装器和设置界面 |
| `kipi/host.py` | 判断 KiPI 是以插件还是独立版启动 |
| `kipi/core/` | 各分析共享：板卡模型、铜皮几何、网格、稀疏求解器、3D 网格和进度报告 |
| `kipi/sources/` | 板卡来源：运行中的 KiCad（IPC）、`.kicad_pcb`、ODB++、HyperLynx 和快照 |
| `kipi/dc/` | DC 分析：传导 FEM、电源树设置与求解、热分析、报告和结果视图 |
| `kipi/ac/` | AC 分析：PDN 阻抗扫频、场求解、目标阻抗、瞬态、报告和面板 |
| `kipi/noise/` | 耦合噪声：波形、热环路寄生、耦合提取、受害网络求解、报告和面板 |
| `kipi/gui/` | PySide6 应用外壳：主窗口、模式切换、3D 视图、工作线程、About 和 Help |
| `kipi/gui/assistant/` | AI 助手：供应商、工具、附件、按工程对话和面板 |
| `docs/help.html` | **Help** 打开的离线用户指南 |
| `docs/solver-guide.html` | 求解器指南：PI 背景和求解原理 |
| `examples/` | 示例板卡快照、PI 设置和生成脚本 |

## 许可证

KiPI 是自由软件：你可以按照 [GNU General Public License](LICENSE)（GPL-3.0-or-later）的条款重新发布和修改它。它不提供任何担保；详见许可证。Copyright © 2026 Drew Maatman。

**网格划分说明。** KiPI 通过 [`triangle`](https://pypi.org/project/triangle/) Python 包使用 Jonathan Shewchuk 的 [Triangle](https://www.cs.cmu.edu/~quake/triangle.html) 对铜皮划分网格。Triangle 并非 OSI 意义上的开源软件：其作者允许免费使用和再发布，但**未经作者许可不得销售或包含在商业产品中**。将 KiPI 用于自己的设计工作没有问题；网格代码隔离在 `kipi/core/mesh/`。

除 PySide6（LGPL-3.0）外，其余依赖均为宽松许可证，与 GPL 兼容。

原项目地址：<https://github.com/drewsum/KiPI>
