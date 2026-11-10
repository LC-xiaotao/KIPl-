# KiPI 电源完整性 — 嘉立创EDA专业版扩展

在嘉立创EDA专业版（EasyEDA Pro）的 PCB 编辑器中，把当前 PCB 一键导出为 ODB++，
交给 [KiPI](https://github.com/drewsum/KiPI) 做电源完整性分析。

## 安装

1. 生成扩展包（只需一次）：

   ```powershell
   cd easyeda_extension
   npm install
   npm run build
   ```

   产物：`build/kipi-power-integrity_v1.0.0.eext`。

2. 在嘉立创EDA专业版中导入：**高级 → 扩展管理器… → 导入**，选择上面的 `.eext` 文件。
   （旧版本客户端在 **设置 → 扩展 → 扩展管理器… → 导入扩展**。）

3. 打开一个 PCB 文档，顶部菜单会出现 **KiPI**。

## 使用

1. 点击 **KiPI → 导出 ODB++ 到 KiPI…**，选择保存位置，得到 `<工程名>_KiPI.tgz`。
2. 启动 KiPI（`python kipi_launcher.pyw`，或安装后的 `kipi` 命令）。
3. 在 KiPI 中点击 **打开**，选择刚才的 `.tgz` 文件。

KiPI 的 ODB++ 读取器会读取网络、铜层、焊盘、过孔、板框和叠层。之后即可进行
DC 压降、电流密度、过孔电流、铜温与 PDN 阻抗分析。

## 说明

- 嘉立创EDA专业版的扩展运行在 JavaScript 沙箱中，不能直接启动本地程序，
  因此流程是“扩展导出 ODB++ → KiPI 打开”。ODB++ 是嘉立创EDA专业版自带的
  制造数据导出格式，数据完整且不依赖第三方转换。
- ODB++ 不包含元件的 3D 模型；KiPI 的 3D 视图仍会显示铜皮、过孔、焊盘和板框。
- 扩展源码：`src/index.ts`；菜单在 `extension.json` 的 `headerMenus.pcb` 中注册。
