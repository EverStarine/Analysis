# 分析学

R. EverStarine 编写的三卷本分析学教材项目。全书依照 [计划纲要](计划纲要.md) 分为三卷，每卷均可独立编译为 PDF。

## 三卷结构

- 第一卷：[实分析：测度、函数空间与几何分析](Book1/Book1.tex)，成品见 [Book1.pdf](Book1.pdf)。
- 第二卷：[Fourier 分析、偏微分方程与调和分析](Book2/Book2.tex)，成品见 [Book2.pdf](Book2.pdf)。
- 第三卷：[复分析、共形几何与解析数论](Book3/Book3.tex)，成品见 [Book3.pdf](Book3.pdf)。

三卷共享 [基础排版文件](Shared/Preamble.tex)，各卷分别维护自己的书前、正文、附录和书后内容。

## 现行工作约定（2026-09-14）

- 第一卷的首次写作与第一轮系统编辑已经告一段落；这不等同于全章定稿，正式状态仍以 [审核进度](审核进度.md) 的逐章表和定稿门槛为准。
- 中文统一写作“弱\*拓扑、弱\*收敛、弱\*紧性”等，不加连字符；首次定义处说明“弱星”文字异名。英文原文继续保留 `weak-*`，数学记号与选读星号分别处理。
- 非数学西文字母统一为 Pagella 正体，保留粗细区别；定理正文、证明标题、术语原文及所有列表序号同样正体。每个术语首次正式定义或引入时都显示完整原文，简单人名结果也不例外；原文使用半角括号。行内、行间数学保留 Latin Modern Math，黑板粗体保留 AMS。
- 及时导出主目录 PDF，供人工验收。要求先导出或上传时，先交付已经完成且通过必要构建的内容，再做获准的扩展检查；不把阶段预览标成定稿。
- 只改规范且源码及 PDF 身份未变时，不重复编译；改一卷正文构建该卷，改共享排版构建三卷，不默认开展全书视觉检查。
- 七份版本化编辑文件统一为 3.0：格式规范、写作规范、术语规范、工作流程说明、书目维护注意事项、审核进度与版权声明。《计划纲要》和《跨卷引用表》是随正文持续更新的台账，不另设版本号。旧试排和历史审核记录不覆盖现行条款。

## 编译

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

## 编辑规范

- [版权声明](版权声明.md)
- [格式规范](格式规范.md)
- [术语规范](术语规范.md)
- [写作规范](写作规范.md)
- [工作流程说明](工作流程说明.md)
- [审核进度](审核进度.md)
- [跨卷引用表](跨卷引用表.md)
- [书目维护注意事项](书目维护注意事项.md)

## 权利说明

本项目当前未授予开放源代码或开放内容许可证。公开访问本仓库不等于获得改编、再许可或商业使用授权，具体以 [版权声明](版权声明.md) 为准。
