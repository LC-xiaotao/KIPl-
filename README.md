<p align="center">
  <img src="resources/kipi.gif" alt="KiPI logo" width="128">
</p>

# KiPI — 电源完整性仿真器（独立版 / KiCad 插件 / 嘉立创EDA专业版）

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![KiCad 9.0.3+](https://img.shields.io/badge/KiCad-9.0.3%2B-314cb0.svg?logo=kicad&logoColor=white)](#requirements)
[![Platform: Windows | Linux | macOS](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#requirements)
[![Python 3.10–3.13](https://img.shields.io/badge/python-3.10%E2%80%933.13-3776ab.svg?logo=python&logoColor=white)](#requirements)

**第一次接触电源完整性？先看 [求解器指南](https://drewsum.github.io/KiPI/solver-guide.html)（[源文件](docs/solver-guide.html)）：它介绍了什么是 PI、为什么重要，以及 KiPI 的网格、DC、热、AC 和耦合噪声求解器如何工作。**

KiPI 是一款电源完整性分析工具，支持三种运行方式：独立运行、作为 KiCad 9/10 的 IPC 插件，或配合 **嘉立创EDA专业版（EasyEDA Pro）** 通过 ODB++ 导出使用。包含三种分析模式：

* **DC：压降与电流密度。** 定义 VRM、负载（引脚电流）和串联器件（磁珠、电阻、负载开关），逐网络、逐铜层计算压降；在可旋转的 3D 视图中查看电压、电流密度、过孔电流、铜损和（可选的）板温，并对负载、VRM、过孔和温度做 PASS/FAIL 判定，导出交互式 HTML 或 PDF 报告。
* **AC：PDN 阻抗。** 为去耦电容建立 RLC 模型，在器件电源引脚放置探针，在频域扫描电源分配网络（平面、过孔、安装孔和电容）的阻抗；对照平坦或自定义目标阻抗检查，并可根据负载瞬态指标计算目标阻抗。
* **耦合噪声：开关电源对信号网络的串扰。** 把 buck/boost 电源当作干扰源，KiPI 根据布局构建开关节点、电感和电容的纹波波形，计算它们通过电容、互感与共地耦合到指定受害网络上的噪声；按逻辑电平的噪声容限检查接收端（高电平和低电平两种状态），并在 3D 视图中显示噪声耦合位置。

第一次使用？**[用户指南](docs/help.html)**（KiPI 内的 **Help** 按钮或 **F1**）逐步介绍每个按钮、工作流和结果含义。KiPI 中每个控件都有工具提示。

![Current density with flow arrows through the +12V input path and the U201 eFuse, with the Series links table](docs/images/current_density.png)

**状态：1.0.0（稳定版）**（[更新日志](docs/CHANGELOG.md)）。本仓库是面向 **嘉立创EDA专业版** 的定制版本，保留上游 KiPI 的 GPL-3.0 许可证与提交历史。仓库地址：[gitee.com/liu-xiaotao/kiplpdndianyuan](https://gitee.com/liu-xiaotao/kiplpdndianyuan)。

## 最新特性

* **嘉立创EDA专业版集成**：扩展一键把当前 PCB 导出为 ODB++，KiPI 直接打开；修复了 EasyEDA ODB++ 的单位与铜厚读取，0.48 mm 介质 + 35 µm 铜可得到正确的 1.58 mm 四层叠层。
* **简体中文界面与中文报告**：菜单、工具栏、设置面板、3D 控件、叠层图、容差图和 Qt 标准按钮均已汉化；DC、AC、耦合噪声和容差报告（HTML 与 PDF）跟随界面语言，图表使用中文字体。
* **AI 助手**：支持多家模型供应商，可用自然语言读取板卡、修改仿真设置、运行 DC/AC/耦合噪声求解并导出报告；支持模型列表拉取、思考过程折叠、Markdown 渲染、附件上传和按工程保存的对话。
* **窄窗口适配**：右侧设置面板最小宽度从 420 px 降到 300 px，表单自动换行、表格横向滚动，窗口变窄时优先压缩面板而不是挤掉 3D 视图。
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

KiPI 的 Qt 界面跟随系统语言：中文系统显示中文，其他系统显示英文；`KIPI_LANG=zh_CN` 强制中文，`KIPI_LANG=en` 强制英文。界面词条位于 [`kipi/gui/translations/`](kipi/gui/translations/)，`KIPI_I18N_LOG=<file>` 会记录尚未翻译的字符串。

导出的 DC、AC、耦合噪声和容差报告（HTML 与 PDF）与界面语言一致，图表使用中文字体（微软雅黑 / PingFang SC / Noto Sans CJK）。报告词条位于 [`kipi/core/translations/`](kipi/core/translations/)。网络名、位号、层名、单位和代码保持原样。

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
- 支持 **附件…** 上传 PDF、Word（`.docx`）、Excel/CSV/TSV、文本、Markdown、JSON、HTML、YAML、XML；本地提取文字后随消息发送，文件本身不会上传。每个文件约 3 万字符、单条消息约 6 万字符，超出会截断并提示；扫描版 PDF 需要先 OCR。
- 工具调用记录、JSON 结果和思考内容保持纯文本，避免被 Markdown 改写。

**能力范围**

助手通过工具操作插件，而不是凭空回答：读取板卡、网络、元件和已有设置；添加/删除 VRM、负载、AC 探针、噪声干扰源和受害网络；运行 `solve_dc`、`solve_ac`、`solve_noise`；返回负载压降、VRM、网络组、探针阻抗、受害网络噪声与裕量；导出 DC/AC/噪声报告（HTML 或 PDF）。系统提示要求助手先核对网络/位号、明确标注假设，并且只报告工具返回的数据。

## 详细安装与使用（English）

> 以下保留上游英文说明，包含 KiCad 插件要求、PCM/手动安装、独立运行、详细使用步骤、开发和许可证信息。


### As a KiCad plugin

#### Requirements

* **KiCad 9.0.3 or later.** Developed on KiCad 10 and confirmed on KiCad 9. The Plugin and
  Content Manager offers KiPI from 9.0.3. A manual install still runs on 9.0.0 to 9.0.2,
  with less: KiCad cannot say which layers a plated pad has copper on there, so pads are
  kept on every layer (KiPI warns in its log), and 9.0.0 cannot report net classes.
* **Python 3.10 to 3.13**, the one KiCad runs plugins with (some dependencies have no
  prebuilt packages for Python 3.14 yet).
  * **Windows:** KiCad's own Python 3.11. Nothing to do.
  * **Linux:** KiCad uses the system Python. On a distribution with Python 3.14 (Ubuntu
    26.04, Fedora 43), pip has to compile some packages, which needs
    `sudo apt install build-essential python3-dev` or similar.
  * **macOS:** KiCad bundles Python 3.9, which is too old. Install Python 3.12 (for
    example from python.org or Homebrew) and select it as the **Python interpreter** in
    *Preferences → Plugins*.

#### From the Plugin and Content Manager

1. In KiCad, enable **Preferences → Plugins → Enable KiCad API**.
2. Open **Plugin and Content Manager** from the KiCad project window, find **KiPI** under
   *Plugins*, and click **Install**. Until KiPI is listed in KiCad's repository, download
   `KiPI-<version>-pcm.zip` from the
   [latest release](https://github.com/drewsum/KiPI/releases/latest) and use
   **Install from File…** instead.
3. Restart the PCB editor and click **KiPI**, as in steps 3 and 4 below: the first click
   sets up KiPI's packages. PCM offers each new release as an update.

PCM keeps KiPI in its own folder (`3rdparty/plugins/com_github_drewsum_kipi` beside the
plugins folder) and replaces it on update. If you also have a manual copy in
`plugins/KiPI`, remove it first, or KiCad shows two KiPI buttons. Shortcuts made by the
standalone launcher from a PCM install point into that folder, so they stop working if
you uninstall KiPI in PCM.

#### Manually

1. In KiCad, enable **Preferences → Plugins → Enable KiCad API**.
2. Clone, link (or copy) this repo into your KiCad plugins folder, or uncompress the release source zip. The examples use KiCad 10's
   folder: for KiCad 9, put `9.0` in place of `10.0`. On Windows, KiCad uses your
   *Documents* folder, which may be redirected to OneDrive:

   ```powershell
   $plug = "$([Environment]::GetFolderPath('MyDocuments'))\KiCad\10.0\plugins"
   New-Item -ItemType Junction -Path "$plug\KiPI" -Target "<path to this repo>"
   ```

   On macOS the folder is `~/Documents/KiCad/10.0/plugins`, and on Linux
   `~/.local/share/kicad/10.0/plugins`:

   ```sh
   ln -s "<path to this repo>" ~/Documents/KiCad/10.0/plugins/KiPI          # macOS
   ln -s "<path to this repo>" ~/.local/share/kicad/10.0/plugins/KiPI       # Linux
   ```

   Or, without git, download `KiPI-<version>.zip` from the
   [latest release](https://github.com/drewsum/KiPI/releases/latest) and unzip it into the
   plugins folder, which gives `plugins/KiPI`.

3. Restart the PCB editor. KiCad makes the plugin's Python environment in the background
   with only what KiPI needs to start (kicad-python), so the **KiPI** toolbar button appears
   within seconds. If it never appears, right-click the action in *Preferences → Plugins*
   and choose *Recreate Plugin Environment*.
4. Click **KiPI**. The first time, KiPI shows its setup window: every package it will install
   into KiCad's environment for it, with sizes (about 254 MB to download on Windows), and
   the optional [PARDISO](#optional-faster-solves-on-large-boards-windows-and-linux-x86-64)
   solver. Nothing is installed until you click **Install**, and KiPI opens once it is done.
   Later clicks open KiPI straight away. The window uses wxPython, which KiCad's Python
   has; where it has neither wx nor Tk, KiPI asks with the desktop's own dialogs (macOS,
   or Linux with `zenity` or `kdialog`), and with none of those it installs without asking.
   The packages stay through plugin reloads; *Recreate Plugin Environment* removes them, and
   the next click sets up again.

### Standalone

1. Install **Python 3.10 to 3.13** if you do not have one (from
   [python.org](https://www.python.org/downloads/), or your package manager). On Linux, add
   `python3-venv` (Debian, Ubuntu) and, for the setup window, `python3-tk`.
2. Put the KiPI folder anywhere: clone this repo, or unzip `KiPI-<version>.zip` from the
   [latest release](https://github.com/drewsum/KiPI/releases/latest).
3. Start KiPI with its launcher: double-click **`kipi_launcher.pyw`** (Windows), or run

   ```sh
   python kipi_launcher.py                      # or: python kipi_launcher.py <board>.kipi.json.gz
   ```

   On Windows the first start leaves a **KiPI** shortcut next to it. On Linux and macOS, run
   `python3 kipi_launcher.py --create-shortcut` once to add KiPI to the applications menu
   (Linux) or `~/Applications` (macOS).

The first start sets up KiPI. The setup window lists every package KiPI will install with
its size (about 254 MB to download on Windows), and nothing is installed until you click
**Install**. On Windows and Linux x86-64 it also offers
[PARDISO](#optional-faster-solves-on-large-boards-windows-and-linux-x86-64). Everything goes
into an environment of KiPI's own, outside the KiPI folder (`KIPI_HOME` puts it elsewhere):

| | KiPI's environment |
|---|---|
| Windows | `%LOCALAPPDATA%\KiPI` |
| macOS | `~/Library/Application Support/KiPI` |
| Linux | `~/.local/share/kipi` |

A KiPI that KiCad installed (from the Plugin and Content Manager, or copied into KiCad's
`plugins` folder) runs standalone in the environment KiCad made for its plugin instead,
so the packages are installed once for both. The launcher adds what is missing there, and
uses an environment of its own when KiCad has not made one yet, the Python it was made
from is gone, or it is not Python 3.10 to 3.13. `--own-env` always uses KiPI's own.

![The launcher's setup window on a first start: every package with its size, and the optional PARDISO solver](docs/images/launcher_setup.png)

Use **Open…** to open a board and **Reload** to read it again. KiCad boards keep the same
setup file standalone and in the plugin. KiPI uses the zone fills saved in the file, so
**fill the zones in KiCad (B) and save** before opening a `.kicad_pcb`. ODB++ jobs and
HyperLynx files share a board's setup when exported next to it with the same name
(`Board.zip`, `Board.hyp`). The [user guide](docs/help.html) lists what each format does
and does not carry.

To change the setup later, use **About → Manage dependencies…** in KiPI, or the launcher:

```sh
python kipi_launcher.py --setup              # the setup window again (add or remove PARDISO)
python kipi_launcher.py --add-pardiso        # or --remove-pardiso, without questions
python kipi_launcher.py --repair             # reinstall everything from scratch
python kipi_launcher.py --reset              # delete KiPI's environment
python kipi_launcher.py --own-env            # KiPI's own environment, not KiCad's plugin one
python kipi_launcher.py --create-shortcut    # add KiPI to the Start menu / app menu / ~/Applications
```

If setup fails, the launcher says why; everything the installer printed is in the `logs`
folder next to the environment.

### Optional: faster solves on large boards (Windows and Linux, x86-64)

If the optional [`pypardiso`](https://pypi.org/project/pypardiso/) package is installed,
KiPI solves with Intel MKL's multithreaded PARDISO solver in place of SciPy's
single-threaded one. On a 645k-unknown rail one solve drops from about 8 s to 1.2 s. Small
boards gain little. It costs about 210 MB of download on Windows (320 MB on Linux) and
there are no MKL packages for macOS or ARM.

KiPI installs it by default where it can, with an opt-out: in the launcher's first setup
standalone, or in a prompt the first time the plugin opens. *About → Manage dependencies…*
adds or removes it later, and *About → Copy version info* shows which solver is in use. If
PARDISO cannot load, KiPI falls back to SciPy and says so in the log.

## Using KiPI

### 1. Open your board in KiCad

Open your board in the PCB editor and click the **KiPI** toolbar button. KiPI opens in its
own window and reads the board through the KiCad API; the log at the bottom streams each
stage as it runs.

* **Load from KiCad** re-reads the board after you edit it in KiCad, and reloads the saved PI setup.
* **Refill zones** (on by default) refills every zone in KiCad before reading, so the zone
  fills KiPI sees match your current routing. KiPI analyzes filled copper only.
* **Save snapshot… / Open snapshot…** store the extracted board as a file that KiPI can open
  later without KiCad. See example snapshots in the repo to experiment!
* **Mode: DC / AC / Noise** (right end of the toolbar, or **Ctrl+1** / **Ctrl+2** / **Ctrl+3**)
  picks the analysis mode. Readme sections 2 to 5 are DC, the default;
  [section 6](#6-ac-pdn-impedance) covers AC and [section 7](#7-coupled-noise) Coupled Noise.
  The VRMs, series links and capacitor models are shared by all three.
* **Help** (or **F1**) opens the [user guide](docs/help.html) in your browser.

### 2. Pick Power Nets from Netlist

The **Board** panel on the left lists every net in the extracted design. Tick the nets you
want to analyze: only ticked nets can be simulated, and they are offered in the PI setup pin
pickers. **Power & ground only**, **All power** and **None** help pick them, and the ticks
are saved with the setup.

Below that are the **Copper layers**, the **Display** options (color by layer or net, Z
scale, vias, pads, mask, silkscreen, part **3D Models**), and **PI Models**, which marks the
parts of the current analysis in 3D. Clicking a part in 3D selects it in the setup, and the
**Info** box shows whatever you last clicked, with **Select in KiCad** to find it in the PCB
editor.

![PI Models marking the parts of the analysis, snapped to the selected +3.3V switcher](docs/images/pi_models.png)

The **Power tree** toolbar button opens a block diagram of the modelled power network, left
to right in the direction power flows, and can be saved as a PNG.

![The power tree of the multiphase buck example: a 12 V source, the 4-phase switcher, the 0.9 V core rail, its load and capacitor models](docs/images/power_tree.png)

The **Stackup** toolbar button lists every copper and dielectric layer with its thickness,
material, εr, thermal conductivity and resistivity, with a cross-section drawn to scale.
Untick **Lock to imported values** to try other thicknesses and materials: every analysis
uses the edited stackup.

![The Stackup window: copper and dielectric layers with thickness, material, εr, thermal conductivity and resistivity](docs/images/stackup.png)

Drag to rotate, scroll to zoom and shift-drag (or middle-drag) to pan; the
[user guide](docs/help.html#keys) lists every keyboard shortcut.

### 3. Model the Power Distribution System

The **PI setup** panel on the right holds the power tree. Each list has **Add**,
**Duplicate** and **Remove** buttons, and every field has a tooltip. Pins are chosen with a
picker: the net, then the part, then optionally the pin numbers. As you pick pins, KiPI
pre-fills what usually follows from them (a VRM's target voltage from the net name, ground
pins, a series link's other side and a resistor's value), and problems are shown in red.
**Import…** fills the power tree from a Tomachie power-tree file (`<design>.pdn.json`).
It also reads a HyperLynx BoardSim session file (`.bud`): its power nets are ticked, and its
`DC_CONN` series links, decoupling capacitor groups, VRMs (as ideal sources, with their
remote sense) and DC sinks (as loads) are added to the setup.

**VRMs tab**: one entry per regulator, power input, or ideal supply. A VRM is a **Source**,
**LDO**, **Switcher** or **Isolated** converter, with its output pins and target voltage,
its input pins (which link it to the rail upstream), efficiency or quiescent current, and
optional remote sense, ground pins, load line, dropout, input range, DC accuracy, current
limit and multiple **Phases**. KiPI works out each VRM's input current from what it feeds.

To try it without a design of your own, open the example board in
[`examples/multiphase_buck`](examples/multiphase_buck): a 4-phase 12 V → 0.9 V, 40 A core rail
(`python -m kipi --snapshot examples/multiphase_buck/multiphase_buck.kipi.json.gz`).

**Loads tab**: one entry per consumer: its **Supply pins**, **Current** (split evenly or by
pin group), optional **Ground pins** and a **Tolerance** for PASS/FAIL. **Load models**
(**Model ▾**) save and apply a part's supplies as a YAML file. They also read a
HyperLynx PI model (`.hlpimodel`): its DC sink currents, pin by pin, as a load on each net
the pins are on, on as many parts as you tick.

![Load editor](docs/images/setup_loads.png)

**Series links tab**: parts that pass DC from one net to another, such as sense
resistors, ferrite beads, fuses, load switches and 0 Ω links: **Side A pins**, **Side B
pins** and a **Resistance**. **Import SPICE model…** uses the maker's SPICE model of the part
for both DC and AC, including diodes and multi-pin parts such as common-mode chokes.
**In order to assign a series link, the nets on either side must both be defined as power
nets in the net selection pane.**

**Solve tab**: every combined rail, with a checkbox. Untick the rails that are not modeled or
routed yet to solve the rest.

![The Solve tab: tick the net groups to solve](docs/images/dc_solve_tab.png)

**Mesh tab**: **Max edge** is the largest FEA mesh triangle edge in mm; smaller is more
accurate and slower. **Via plating** sets each kind of via's plating thickness and fill.

![The Mesh tab with the via plating rules](docs/images/setup_mesh.png)

**Thermal tab** (off by default): tick **Electro-thermal co-simulation** to make losses heat
the board and the warmer copper become more resistive. Each copper layer has its own
temperature, with heat crossing the laminate and running down vias. Inspired by
[KiCad Thermal Sim](https://github.com/PoeAlex/KiCad_Thermal_Sim) by
[PoeAlex](https://github.com/PoeAlex).

![Thermal settings](docs/images/setup_thermal.png)

The setup is saved as `<board>.kipi-setup.yml` next to the board when you click **Save** and
every time you solve. It travels with the project and can go into version control. AI agents
can make quick work of power tree modelling by editing this file directly.

### 4. Solve

Click **Solve all**. Every rail is meshed and solved, downstream loads first, so each VRM's
input current includes everything it feeds. Progress streams into the log; **Cancel** stops
the run.

Click **Report** to write an HTML report next to the board, or choose **PDF**. The HTML
report is a single portable file with the summary and every results table, an interactive 3D
view per rail, per-layer voltage and current-density maps, the board temperature map when
thermal is on, and a **User notes** box.

| Summary tables | Interactive 3D per net group |
|---|---|
| ![Report summary tables](docs/images/report_tables.png) | ![Report 3D voltage view](docs/images/report_3d.png) |

### 5. Read the results

In the **Results** pane, choose a **net group** and a **field** to show in 3D: **Voltage**,
**Current density** (tick **Arrows** to see the flow), **Power density**, **Via current**
or **Temperature**. Click any point to probe it in the Info box, and set the **Color
scale** to look closer.

![Voltage drop along the +12V input plane, from the input connector to the two loads, with the Loads results table](docs/images/voltage.png)

![Current density with flow arrows through the +12V input path and the U201 eFuse, with the Series links table](docs/images/current_density.png)

| Via current | Temperature |
|---|---|
| ![Via current, with the Vias table ranked by current](docs/images/via_current.png) | ![Board temperature from the electro-thermal solve, with the Thermal results tab](docs/images/temperature.png) |

The result tabs give **Loads** (effective voltage, drop and PASS/FAIL), **VRMs**, **Series
links** (I²R losses), **Vias** ranked by current, **Losses**, **Thermal** and **Notes**.
**Export ▾** writes CSV or ParaView files, and **Save results…** writes a results file that
**Open results…** reloads without solving again.

### 6. AC: PDN impedance

Switch **Mode** to **AC**. The **AC setup** shares the VRMs and series links with DC mode and
adds:

* **Capacitors tab**: RLC models (capacitance, ESL, ESR) for the decoupling capacitors, each
  shared by a group of identical parts, or the maker's SPICE model. **Models from values**
  starts one model per capacitor value, and **Import…** / **Export…** move a model between
  setups as a YAML file named after it. Models can be derated for DC bias, temperature,
  aging and tolerance. **Important**: model capacitors of the same value in different case
  sizes separately.
* **Probes tab**: where to plot the PDN impedance, usually a device's supply and ground pins,
  each with a **flat** or **custom** target. The **Target Impedance/Frequency Calculator**
  works out a flat target from the device's voltage tolerance and load step, following Smith
  et al., ["Power Distribution System Design Methodology and Capacitor Selection for Modern
  CMOS Technology"](https://doi.org/10.1109/6040.784476), IEEE Trans. Adv. Packaging, 1999.
  Targets apply above the VRM's **Control loop bandwidth**.
* **Sweep tab**: frequency range and resolution, and the capacitor deratings.
* **Mesh tab**: mesh size and minimum edge at plated holes. Ground far from the rail is
  meshed coarsely, every piece of copper that can carry current kept.

| Capacitor models | Target calculator |
|---|---|
| ![Capacitors tab](docs/images/ac_capacitors.png) | ![Target impedance calculator](docs/images/ac_target_calc.png) |

Pick the **Rail** and **Ground** and click **Solve rail**. The rail's copper and its ground
are field-solved, so plane resistance, spreading inductance, plane capacitance, cavity
resonances and via inductance all come from the layout; the capacitors and series links are
attached at every frequency. The VRM is not modeled as an impedance (the open-loop PDN).
**Important:** AC analysis is a massive compute problem. Many probes and a finer mesh
increase simulation time dramatically.

The **Impedance** tab plots |Z| against frequency for every probe, with its target, and a
cursor to read values. The **Board map** tab shows the mesh, probes and capacitors, and the
**Transient** tab estimates each probe's undershoot and overshoot for its load step.
**Report**, **Export CSV…** and **Save results…** work as in DC mode.

![The Board map of the core rail's solve: the VCORE and GND mesh, the probe and the capacitors by model](docs/images/ac_board_map.png)

![The impedance plot of the example's 0.9 V core rail against its custom target, with the cursor on the anti-resonance and its values in the Info box](docs/images/ac_impedance.png)

### 7. Coupled Noise

Switch **Mode** to **Noise**. The **Coupled Noise setup** treats one of the setup's
**Switcher** VRMs as an *aggressor* and the signal nets you name as *victims*. The
screenshots below are the `examples/validation/coupled_noise` example: a 12 V to 1.8 V,
1 MHz buck over a ground plane, with three victims. Open its snapshot to try it.

* **Aggressors tab**: **Add** makes an aggressor from a switcher VRM and fills it in from the
  board: the switching device, inductor, switch node and capacitors. Give the switching
  frequency and edge times; datasheet values such as Coss and Qrr are optional. KiPI traces
  each capacitor's hot loop through the copper for its inductance and its coupling.
* **Victims tab**: each victim is a net with its driver and receiver pins and a **Type**
  (CMOS, open drain, terminated, LVDS, analog input or undriven) and **Logic level**, which
  set its loading and noise margin.
* **Capacitors tab**: the same capacitor models as AC mode.
* **Settings tab**: harmonics, damping, victim resolution and the **Board model**, the slow
  but more accurate field model of the converter's copper (untick it for a quick look).

Pick the **Aggressor** and click **Solve**. Tick **Scan nearby nets** to also check every
signal net near the aggressor. The **Waveforms** tab plots the switch node with its ringing,
the inductor and capacitor currents and the rail ripple, in time or as a spectrum.

![The Waveforms tab: the buck's switch node over two periods, ringing at 179 MHz on each hard rising edge while the soft falling edge settles at once](docs/images/noise_waveforms.png)

The **Results** table lists each victim's peak noise at its receiver, its margin, the
dominant mechanism and PASS or FAIL. **Victim noise** plots the noise, as a whole or by
mechanism (capacitive, inductive, common ground).

![Victim noise for SIG_SW: the superposition at the receiver with its capacitive and inductive parts, and the results table](docs/images/noise_victim.png)

**Victim held high and low** draws the noise riding on the receiver's high and low levels
against its thresholds.

![SIG_SW held high and low, with the noise riding on each level](docs/images/noise_states.png)

**Coupling in 3D** colors the selected victim's traces by their share of the peak noise, so
the pieces to move stand out. **Hot loops in 3D** draws the capacitor loops' current, and
**Fields in 3D** the H and E fields over the board, with near-field hotspots and a first
radiated estimate against CISPR 32 class B. Victims crossing a split in their reference
plane are noted.

![Coupling in 3D for SIG_LOOP: the victim colored by its share of the 631 mV peak, beside the capacitor loops](docs/images/noise_coupling_3d.png)

The mechanisms point to different fixes: capacitive noise comes from the switch node's
dV/dt, inductive noise from the hot loop's dI/dt and common noise from the switching
current's return. **Report** and **Save results…** work as in the other modes.

### Tips and troubleshooting

* **A load shows DISCONNECTED** usually means unrouted copper, an unfilled zone, or a
  missing series link for a part between two power nets.
* **Unexpected voltage drop:** thermal reliefs, necked traces, via counts and anti-pads in
  planes dominate DC drop; the Current density view with Arrows shows the bottleneck.
* **Slow solves:** raise **Max edge**, or analyze fewer nets at a time. On Intel x86, install
  the PARDISO solver (above).
* **"KiPI works with one KiCad at a time"** although only one is open: a KiCad that did not
  exit cleanly may still be running; end it in the task manager.
* **Logs:** each session writes to `kipi/kipi-<date>-<time>-<pid>.log` in the temporary
  folder, with a matching `.crash.log`. Attach both, and **About → Copy version info**, to
  bug reports. The [user guide](docs/help.html) has more troubleshooting.
* **Have Fun:** The author asks that you share what projects this package has simulated, and what power integrity issues you have found with it. Conductor simulation gives incredible insight into how PCBs actually function in practice. See what happens when you pump 10 amps into a 5 mil trace with the temperature results view.

## Development

From a checkout, KiPI runs standalone, or as the plugin against the running PCB editor:

```powershell
python -m venv --system-site-packages .venv   # use KiCad's bundled python.exe
.venv\Scripts\pip install -r requirements.txt -r requirements-standalone.txt -r requirements-dev.txt
.venv\Scripts\python -m kipi tests\data\synthetic.kipi.json   # standalone, opening a board
$env:KIPI_HOST = "plugin"; .venv\Scripts\python -m kipi        # the plugin: connect to KiCad
.venv\Scripts\python -m kipi --dump board.kipi.json.gz   # extract from KiCad only, no window
.venv\Scripts\python -m pytest tests
.venv\Scripts\ruff check .                    # lint, as CI does (ruff check . --fix fixes most)
```

`requirements.txt` is what KiCad installs into the plugin's venv (kicad-python only), and
`requirements-standalone.txt` what KiPI installs on top on the first click, and the
launcher into its own environment; `tests/core/test_requirements.py`
keeps them in step with `pyproject.toml`. After changing them, run
`python .github/scripts/dep_sizes.py`.

The tests follow the package (`tests/core`, `tests/dc`, `tests/ac`, `tests/noise`,
`tests/sources`, `tests/gui`, `tests/scripts`). `tests/accuracy` solves the boards in
[`examples/validation`](examples/validation) and compares the results with hand
calculations, to help gain confidence that an open-source tool can compare to professional
tools:

| Board | Checks |
|---|---|
| `skinny_traces` | 0.15 mm and 0.1 mm tracks on outer and inner layers (ρL/wt), an arc track (annular sector) |
| `right_angle` | an L route and a Z route: 0.5587 squares per right-angle corner |
| `layer_change` | a strip dropping from F.Cu to In2.Cu through a row of vias: barrels in parallel, current crowding, equal sharing |
| `planes` | two pads on a disc-shaped inner plane (method of images); one strip on two layers of different weights |
| `power_chain` | source, switcher, ferrite series link and remote-sensed LDO over a ground strip: every voltage and current |
| `ac_plane` | plane-pair capacitance ε₀εrA/h and the first cavity resonance c/(2a√εr) |
| `ac_decap` | a mounted capacitor as a series RLC: low-frequency capacitance, mounted inductance, ESR at resonance |
| `ac_ferrite` | a ferrite (R + L link) feeding a small plane: lumped impedance and its LC resonance |

After changing a board there, rerun `python examples/validation/make_boards.py [name]` (or
`python examples/multiphase_buck/make_board.py` for the example) and commit its files.

CI runs ruff and the test suite for every push and pull request on Windows, Linux (Python
3.10 to 3.13) and macOS; the accuracy tests run for pull requests into `main`.
`tests/helpers/kicad_fake.py` stands in for each KiCad version from 9.0.0 to 10.0.6.

### Releases

Publishing a GitHub release runs `.github/workflows/release.yml`, which attaches three
files:
- `KiPI-<tag>.zip`, for manual installs.
- `KiPI-<tag>-pcm.zip`, the same files for KiCad's Plugin and Content Manager.
- `metadata.json`, that version's entry with its sha256 and sizes.

The PCM metadata that stays the same from release to release is in
`.github/pcm/metadata.json`. To publish a version in PCM, add its entry (the job summary
shows it too) to `packages/com.github.drewsum.kipi/metadata.json` in a merge request to
[KiCad's metadata repository](https://gitlab.com/kicad/addons/metadata). The first time,
add `resources/kipi_64.png` there as `icon.png` as well. Once a version is merged, its zip
can't change, so never replace a release's PCM zip. Tag a release `vX.Y.Z`: a tag like
`v1.0.0-rc1` gets the manual zip only, since PCM version numbers can't have suffixes.

### Codebase Layout

| Path | Purpose |
|---|---|
| `kipi_entry.py`, `plugin.json` | KiCad IPC plugin action (runs KiPI as the plugin) |
| `kipi/__main__.py` | `python -m kipi` / `kipi`: standalone, or the plugin with `KIPI_HOST=plugin` |
| `kipi_launcher.py`, `.pyw` | Standalone launcher: sets up KiPI's environment on the first start, then starts KiPI in it |
| `kipi/launcher/` | The launcher itself, standard library only: environment, Python discovery, package list, installer and setup screens (Tk, wx, console, the desktop's dialogs); the plugin's first-click setup and KiCad's plugin environment |
| `kipi/host.py` | Plugin or standalone: how KiPI was started |
| `kipi/core/` | Shared by every analysis: board model, copper geometry, meshing, sparse solvers, 3D meshes, progress reporting |
| `kipi/sources/` | Where boards come from: the running KiCad (IPC), `.kicad_pcb` files, ODB++, HyperLynx and snapshots |
| `kipi/dc/` | DC analysis: conduction FEM, power-tree setup and solve, thermal, reports, results views and panel |
| `kipi/ac/` | AC analysis: PDN impedance over frequency, field solver and sweep, targets, transient, report and panel |
| `kipi/noise/` | Coupled Noise analysis: waveforms, hot loop parasitics, coupling extraction, victim solves, report and panel |
| `kipi/gui/` | PySide6 application shell shared by every mode: main window, mode switch, 3D viewer, worker threads, About and Help |
| `docs/help.html` | The user guide opened by **Help**; a single offline HTML file |
| `docs/solver-guide.html` | The Solver Guide: PI background and how the solvers work |
| `kipi/compat.py` | Opens results files saved by earlier versions, from before modules moved |
| `examples/` | Example boards as snapshots with their PI setups, and the scripts that generate them |

## License

KiPI is free software: you can redistribute it and/or modify it under the terms of the
[GNU General Public License](LICENSE) as published by the Free Software Foundation, either
version 3 of the License, or (at your option) any later version. It is distributed WITHOUT
ANY WARRANTY; see the license for details. Copyright © 2026 Drew Maatman.

**Note on the mesher.** KiPI meshes copper with Jonathan Shewchuk's
[Triangle](https://www.cs.cmu.edu/~quake/triangle.html), through the
[`triangle`](https://pypi.org/project/triangle/) Python package. Triangle is not open source
in the OSI sense. Its author's terms allow free use and redistribution, but it **may not be
sold or included in commercial products without a license from its author**. Using KiPI for
your own design work is fine. The meshing code is isolated in `kipi/core/mesh/` for this reason.

The other dependencies are under permissive licenses, apart from PySide6 (LGPL-3.0). All of
them are compatible with the GPL.

The author of KiPI prohibits the package from inclusion in commercial software. Use it, fork it, and modify it to your heart's content.
