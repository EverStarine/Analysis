# 分析学

> **总则**：所有规则都必须写明设立的原因；当规则的原因失效时，规则也应同步失效并删除或修订。所有工作记录都必须服务于后续工作效率的提升；仅记录流水账、对后续工作无意义的内容没有保留必要，评估为无用时应清理。

**用途与有效性**：本文件提供源码、现行规范、待办和成品的入口，减少寻找文件及重复说明。状态由主管台账维护；链接、构建方式或成品位置改变时更新对应入口，不在这里积累按日工作流水。

R. EverStarine 编写的三卷本分析学教材项目。全书依照 [计划纲要](工作记录/计划纲要.md) 分为三卷，每卷均可独立编译为 PDF。

## 三卷结构

- 第一卷：[实分析：测度、函数空间与几何分析](Book1/Book1.tex)，成品见 [Book1.pdf](Book1.pdf)。
- 第二卷：[Fourier 分析、偏微分方程与调和分析](Book2/Book2.tex)，成品见 [Book2.pdf](Book2.pdf)。
- 第三卷：[复分析、共形几何与解析数论](Book3/Book3.tex)，成品见 [Book3.pdf](Book3.pdf)。

三卷共享 [基础排版文件](Shared/Preamble.tex)，各卷分别维护自己的书前、正文、附录和书后内容。

## 当前工作定位

三卷80章、18篇附录已有完整初稿。第二卷已按整卷结构与逻辑意见修订衔接、先修和附录安排；第一至七章、第九章及第十一至十二章第1轮“小修后再审”意见已修订，待复审；第八、十、十三至十六章第1轮“小修后接受”意见已闭环，尚未达到至少两轮的定稿条件，其余章节继续待审核。后续修订范围和正式审核状态以[审核进度](工作记录/审核进度.md)为准；专项检查和构建成功不代表数学定稿，避免据旧检查结果跳过新改写内容。

第二卷第17—25章及附录A—H已完成逐章、逐篇扩写。附录A—D保持基础工具补充类定位；附录E《Strichartz估计与色散型偏微分方程》按高阶选讲类处理，完整证明所述非端点线性估计与一维质量次临界应用：先建立T*再由对偶推出自由演化估计，一般混合范数外力经连续延拓定义Duhamel项；半波估计由频带核及平方函数合成，一维立方方程以保质量截断和统一逼近建立全局解。五节及8题完整解答保留，端点仍是标源深层证明概要。附录F《集中紧性原理》按基础变分工具补充类处理，六节与8题全解已展开：质量三分法、Sobolev消失、质量次临界能量和模平移强紧性在所述条件下完整证明，主变分模型限定d≥3；一般曲面轮廓分解未建立，末节只证明有限平移解耦及已给分解下的单轮廓结论。附录D的一般无界自伴谱定理保持外部先修，附录C的原子分解等价、完整T1判据及加权奇异积分仍属进一步阅读，第25章的BCT与解耦仍是标源证明概要。附录G为高阶选讲类，六节与8题全解已展开；符号与分布作用、紧位置及局部有限合成、常系数椭圆磨光、波前集基本性质及仿射运输模型完整证明，渐近求和、一般参数逆和实主型传播保留标源深层输入。锥内余项只在指定方向磨光，不误称全局光滑核。附录H按基础工具补充类完成两节与8题全解；合法弱测试、线性Moser上界至Harnack桥接、一般p增长的局部有界、凸能量解与稳定性、径向通量及点源对偶阈值已展开。一般非线性Harnack与梯度正则性仍为进一步理论。第二卷逐篇扩写阶段完成，下一章为第三卷第一章《全纯函数与幂级数》，随后按第2—27章及附录A—F推进；剩余6篇附录均在第三卷，须逐篇复读。第二卷尚未定稿，写作与自检不增加正式审核轮数，第17—25章及附录A—H仍待首次审核。按实际讲解缺口保留、补充或重组，不整批推倒、不按页数均摊；前后文风对照、规范落实重点与后续问题见[读者视角清单](工作记录/2026-10-11-读者视角逐章检查.md)。

- 内容与目录：查[计划纲要](工作记录/计划纲要.md)，便于确定本章应覆盖的对象和深度。
- 数学与读者难点：查[读者视角检查](工作记录/2026-10-11-读者视角逐章检查.md)、[条件自足检查](工作记录/2026-10-11-陈述条件自足检查.md)和[跨卷引用表](工作记录/跨卷引用表.md)，便于保留必要条件、正文证明与调用位置。
- 图表解释任务：查[图表维护定位](工作记录/图表候选清单.md)，避免重新加入已判定无帮助的导航图表。
- 成品是否对应源码：查[当前PDF身份与书签维护依据](工作记录/2026-10-12-标题修订与PDF书签检查.md)；改动相应卷或共享源码后，该快照的通过结果即需重新核验。

各项现行规则及其设立原因集中在下列主管规范，减少多份副本日后漂移。新增规则须说明解决的实际问题与适用条件；原因消失时撤销或修订。记录仅保留可定位的待办、正式审核依据、真实来源或可复用处理办法；完成流水不另建文件。

开始工作前检查临时积压，发现长期未评估的旧产物时先建议优先清理，以免挤占空间并误用旧结果。清理按[工作流程第10节](写作规范/工作流程说明.md#10-临时文件与记录清理)先隔离、确认安全后再移除；提醒阈值及其原因由该主管条款维护。

## 编译

**设立原因与适用条件**：以下分卷、隔离输出、书目/三类索引及稳定轮次要求分别避免编译错入口、辅助文件污染源码、书目索引未实际生成和引用不稳定；PDF与SyncTeX同批复制避免编辑定位错版。工具、目录或输出方式改变时同步修改示例，工具失败时保留上一份有效成品。具体规则由[工作流程说明](写作规范/工作流程说明.md)维护。

使用 XeLaTeX，在相应卷目录中编译该卷主文件。辅助文件统一写入根目录的 `tmp/build/BookN/`；成功构建后，同名 PDF 与 SyncTeX 文件复制到卷目录供 TeXstudio 预览和双向定位，PDF 另复制到项目根目录作为验收成品。以下 PowerShell 示例从项目根目录执行；索引样式先解析为绝对路径，切换构建目录后仍能正确找到：

在 TeXstudio 中直接打开相应的 `BookN.tex`，按“编译”即可。主文件顶部的 `TXS-program:compile` 会调用同目录的 `build-BookN.bat -NoPause`，完整执行 XeLaTeX、Biber、三类索引和后续稳定轮次；“构建并查看”打开与根文档同目录的 `BookN.pdf`，同目录的 `BookN.synctex.gz` 负责源码与 PDF 的正向、反向定位。刚修改过魔法注释时须重新打开根文档。若脚本报告某类索引“当前源码未登记条目”，表示该卷的 `.idx` 确实为空，并非 `makeindex` 执行失败。

```powershell
$analysisIndexStyle = (Resolve-Path -LiteralPath './Shared/analysis.ist' -ErrorAction Stop).Path
Push-Location -LiteralPath './Book1' -ErrorAction Stop
try {
    New-Item -ItemType Directory -Force '../tmp/build/Book1' -ErrorAction Stop | Out-Null
    xelatex -interaction=nonstopmode -halt-on-error -synctex=1 '--output-directory=../tmp/build/Book1' Book1.tex
    if ($LASTEXITCODE -ne 0) { throw '首轮 XeLaTeX 失败。' }
    biber '--output-directory=../tmp/build/Book1' '../tmp/build/Book1/Book1'
    if ($LASTEXITCODE -ne 0) { throw 'Biber 失败。' }
    Push-Location -LiteralPath '../tmp/build/Book1' -ErrorAction Stop
    try {
        foreach ($analysisIndex in @('chinese', 'foreign', 'symbols')) {
            makeindex -q -s $analysisIndexStyle "$analysisIndex.idx"
            if ($LASTEXITCODE -ne 0) { throw "索引处理失败：$analysisIndex" }
            $analysisIndexLog = Get-Content -Raw -LiteralPath "$analysisIndex.ilg" -ErrorAction Stop
            if ($analysisIndexLog -notmatch '\b0 rejected\b' -or $analysisIndexLog -notmatch '\b0 warnings\b') {
                throw "索引存在拒收条目或警告：$analysisIndex；请检查对应 .ilg。"
            }
        }
    } finally {
        Pop-Location
    }
    foreach ($analysisPass in 1..2) {
        xelatex -interaction=nonstopmode -halt-on-error -synctex=1 '--output-directory=../tmp/build/Book1' Book1.tex
        if ($LASTEXITCODE -ne 0) { throw "后续第 $analysisPass 轮 XeLaTeX 失败。" }
    }
    Copy-Item -LiteralPath '../tmp/build/Book1/Book1.pdf' -Destination './Book1.pdf' -ErrorAction Stop
    Copy-Item -LiteralPath '../tmp/build/Book1/Book1.synctex.gz' -Destination './Book1.synctex.gz' -ErrorAction Stop
    Copy-Item -LiteralPath '../tmp/build/Book1/Book1.pdf' -Destination '../Book1.pdf' -ErrorAction Stop
} finally {
    Pop-Location
}
```

首轮 XeLaTeX 收集引文与索引条目，Biber 生成本卷实际引用的参考文献，循环中的三次 `makeindex` 分别处理一个 `.idx`，并以 `-s` 载入右对齐样式；不可省略样式或将三个索引名并入一次调用。随后两轮 XeLaTeX 排入书目和索引，并稳定目录、交叉引用与书签。任一步骤失败都会中止，不用旧构建结果覆盖成品。其他两卷相应替换卷号；尚无引文或索引条目的卷可以暂不执行相应的 Biber 或 `makeindex` 命令。项目根目录只保留三份供验收的 PDF，不存放辅助文件；各卷目录中的同名 PDF 与 `.synctex.gz` 只供本地编辑，均由 Git 忽略。具体见工作流程说明第 5 节。

标题与书签的可复用检查工具位于 [scripts/make_inventory.py](scripts/make_inventory.py) 和 [scripts/audit_bookmarks.py](scripts/audit_bookmarks.py)：先从当前源码生成标题清单，再核对选定PDF的题名、编号、层级和目标，输出目录须显式指定。工具从临时目录移出，是为了让后续核验不依赖已清理的旧任务脚本；标题宏或项目布局改变后须重新核对解析方式。中文PDF抽取所需的 [字体映射辅助](scripts/pdf_text_mapping.py) 只作用于读取器内存。各工具的命令行参数见 `--help`，输出随当前构建管理，不保留重复成功流水。

隔离构建的成品可用 [scripts/deliver_build.py](scripts/deliver_build.py) 核验并交付：默认只读检查当前源码、构建清单、严格标题书签检查、日志、索引和 SyncTeX；加 `--deliver` 才在指定临时目录备份后更新所选卷的根目录PDF、编辑预览与源码定位文件，并在当前构建中保存交付身份。连续写作时若按《工作流程说明》第6节暂缓轻微竖直溢出，可显式指定 `--allow-overfull-vbox PT`，交付记录保留实际警告及允许上限；缺字、横向溢出、引用或构建错误仍会阻止交付。这一选项避免为已决定后置的排版问题反复构建，不表示版式验收通过。清单、检查结构或项目布局改变时须先调整工具。只覆盖构建清单所选卷，不提高数学审核状态。

## 编辑规范

- [版权声明](版权声明.md)
- [格式规范](写作规范/格式规范.md)
- [术语规范](写作规范/术语规范.md)
- [写作规范](写作规范/写作规范.md)
- [工作流程说明](写作规范/工作流程说明.md)
- [审核进度](工作记录/审核进度.md)
- [跨卷引用表](工作记录/跨卷引用表.md)
- [书目维护注意事项](写作规范/书目维护注意事项.md)

## 权利说明

本项目当前未授予开放源代码或开放内容许可证。公开访问本仓库不等于获得改编、再许可或商业使用授权，具体以 [版权声明](版权声明.md) 为准。
