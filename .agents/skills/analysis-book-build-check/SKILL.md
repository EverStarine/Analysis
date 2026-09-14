---
name: analysis-book-build-check
description: 为《分析学》三卷教材按改动范围规划和执行隔离构建，核验书目、三类索引与交叉引用稳定性，并记录 PDF 对应的源码哈希。适用于构建验收、共享样式变更或成品是否过期的核对；普通文字编辑不触发全书视觉审计。
---

# 分析学教材构建与版本核对

以项目根目录的 `README.md`、`工作流程说明.md` 第 5–7 节和 `Shared/analysis.ist` 为当前依据；涉及书签、索引或附录才进一步读 `格式规范.md` 对应条款。此技能是项目级构建助手，不启动数学正式审稿，不更新审核轮数。

## 选择最小充分范围

- 改 `BookN/` 正文、图表、输入链：完整构建该卷。改 `Shared/`（含书目和索引样式）：三卷。迁移跨卷路径或修改卷级结构时按实际受影响卷扩大。
- 只改规范、记录或技能文档：核对示例和差异，通常无需编译。未知目录或无法判断的外部资源先报告范围未定，不能悄悄退回第一卷。
- 路径由当前任务的改动清单提供；脚本不会替你选择 Git 基线。可只读查看 `git diff --name-only`、暂存差异和新文件，避免遗漏尚未提交改动。

## 使用附带脚本

`scripts/build-book.ps1` 支持 PowerShell 5.1+，只使用已有 XeLaTeX、Biber、makeindex。默认仅输出 JSON 计划；`-Build` 才执行。`-Volume 1,2,3` 可显式定界，或传入项目相对路径数组 `-ChangedFiles` 自动选卷；两者不混用。

```powershell
# 在项目根执行；默认只读，不写快照或 PDF。
& ./.agents/skills/analysis-book-build-check/scripts/build-book.ps1 -ProjectRoot . -ChangedFiles 'Book1/Part01/Chapter07/Chapter07.tex'
& ./.agents/skills/analysis-book-build-check/scripts/build-book.ps1 -ProjectRoot . -ChangedFiles 'Shared/analysis.ist' -Build
& ./.agents/skills/analysis-book-build-check/scripts/build-book.ps1 -ProjectRoot . -Volume 1 -Build
# 核对某次成功构建是否仍对应当前源码及原 PDF；清单路径取自构建输出。
& ./.agents/skills/analysis-book-build-check/scripts/build-book.ps1 -ProjectRoot . -CheckManifest './tmp/build/skill-RUN/manifest.json'
```

每次执行创建唯一 `tmp/build/skill-时间-随机值/`，保存所选卷与 `Shared/` 的源文件快照、构建日志和 `manifest.json`；既有 `tmp/build-current.ps1` 不作为运行依赖。源码集合是这些目录下除已知辅助文件与各卷同名 TeXstudio 预览 PDF 之外的全部文件，含正文所用图片和样式；这是保守版本身份，未被输入的文件变化也会标为过期。卷目录中的 `BookN.pdf` 与 `BookN.synctex.gz` 由分卷脚本生成，只服务于编辑预览与源文定位，不属于源码或验收成品。快照前后核对哈希，构建期间继续写正文不会改变正在编译的版本。符号链接或不在所选目录内的项目依赖需先人工明确，脚本不声称覆盖任意 TeX 工程。

构建采用 XeLaTeX 的 `-recorder` 和 `-no-shell-escape`，首轮后按实际 `.bcf` 引文运行 Biber；分别处理非空 `chinese.idx`、`foreign.idx`、`symbols.idx`，每次传入快照中的绝对 `.ist` 路径。`.ilg` 必须零拒收、零警告。后续若索引输入或书目控制文件改变，重新处理；至少三轮、至多默认六轮 XeLaTeX，结合辅助文件哈希和 rerun 警告确认稳定。无引文或空索引可跳过相应处理。错误、未定义引用或引文、重复标签、未稳定均非成功。查看首次失败对应日志，保留失败快照。

脚本不修改根目录成品。已有阶段预览或验收授权时，在成功构建、身份核对和本次必要检查后复制相应 PDF，并保存清单及目标 PDF 哈希关联；无需重复询问同一授权。构建失败不能提升成品，`git commit/push` 也不属于本脚本。

## 按问题核对 PDF

先读编译日志、`.toc`、`.aux` 和 PDF 文本；书签结构变化时使用现有 PDF 解析工具的 outline、页标签和目标页信息动态定位封面、目录、附录及三类索引。不要采用旧记录里的“最后五页”、固定物理页或固定页数。

索引抽查从本轮 `.idx`/`.ind` 和书签找到目标，核对条目数、排序、页码链接与当前正文标签。附录需为唯一顶级节点；章习题书签通过现有 `\BookExercises` 唯一生成。封面入口和目录都需顶级书签且跳向真实页面，后记、参考文献、索引回到顶级。

连续写作期普通文字修改只做必要构建和相关错误检查；没有共享版式变化不重测全部页眉、字形与索引链接。有图表、复杂分页或结构化证据不足时，才用已有 `pdftoppm` 等局部渲染动态找到的页面。不要把 PDF 解析工具缺失变成自动安装或全卷视觉检查任务。

## 交付证据与边界

报告目标卷、成功/失败/未稳定、日志、构建 PDF 与清单位置，以及源码是否在构建后发生变化。清单包含相对路径和 SHA-256、工具绝对路径及版本（makeindex 用二进制哈希和 `.ilg` 版本信息）、实际参数与 PDF SHA-256。结果中的 `sourcesStillCurrent` 表示构建结束时的源码状态；`layoutWarningCount` 与样例列出缺字及溢出警告，属于待判断的版面问题，不能只因编译成功就略去。核对结果区分 `sourcesMatch` 与 `pdfMatches`；两份 PDF 字节相等不能证明对应当前源码。没有既有清单的旧 PDF 只能记为“来源未证实”，不能从修改时间倒推构建版本。

自动成功只说明此快照通过所述编译和稳定性检查，不说明数学正确或全部版式已验收；使用了未锁定系统字体、TeX 包或脚本范围外的外部资源时，说明重现限制。
