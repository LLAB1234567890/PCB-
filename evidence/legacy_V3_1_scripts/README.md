# V3.1 可复现脚本

脚本以自身交付目录解析相对路径，不要单独搬走。实际工具版本在 `../validation/toolchain_versions.json`：KiCad 10.0.6 Python 提供 pcbnew，分析环境使用 requirements-analysis.txt，报告环境使用 requirements-report.txt，CAD 使用 FreeCAD Python。中文图/报告需要 Windows 微软雅黑，PDF 渲染需要 Poppler。

在交付根目录，以 KiCad Python 执行 `scripts/replay_accepted.py --output <全新目录>`，即可原始 PCB → 9 个局部补丁 → 版本元数据/对象排序重放。不会覆盖现有目录；实际重放字节一致证明在 `validation/ACCEPTED_replay_byte_parity.json`。排序清单只有语义哈希，不复制最终几何。

完整重建先复制工程、在 KiCad 填铜保存，再运行 `scripts/REBUILD_ALL.ps1`。指定 KiCadCLI/KiCadPython/AnalysisPython/ReportPython/FreeCADPython。此机分析解释器为 `C:\Users\AAA\Documents\Codex\2026-09-30\eda\work\thermal_env\Scripts\python.exe`，报告解释器为 `C:\Users\AAA\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

顺序：原生网表/ERC/DRC和全类别 ERC → 原生对象/实际填铜/独立连接 → 回流/DC 网格/故障契约 → 热/质量/支撑/CAD → 制造解析 → 三轮 PCB、三轮原理图、两轮一致性 → 比较图/报告。完整重建不自动签发新版本；之后运行 render_pdf_qa.py，实际查看全部四份 PDF 的 31 页并更新视觉记录，再运行 production_zip.py 和 offline_acceptance.py。源、制造、PDF 或固定边界变化时，旧 PASS 失效。

Check_design.ps1 只读源，在 validation/recheck 输出数量核对结果，不把命令退出 0 当零违规。REBUILD_models.ps1 复算实际铜/质量/固定支撑、重建并回读 FreeCAD/STEP/STL 和六热工况。Rebuild_manufacture.ps1 原生导出后解析 Gerber/Excellon/BOM/CPL。review_erc_categories.py 在受控临时副本启用全部忽略类别，不改源工程设置。

thermal/inputs.json 与 mechanical/design_parameters.json 是已授权可调参数。更改算法、负载或边界后应同时重算可比基线，刷新装配/支撑；不能混用新旧工况宣称改善。DevKit 合并热源、PA12 参考物性、线长、SET 灯电流及实物适配仍需测量。固件和样机未执行状态不因重建而改变。
