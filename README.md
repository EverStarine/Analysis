# 分析学

R. EverStarine 编写的三卷本分析学教材。

| 卷 | 内容 | PDF | 源码入口 |
|---|---|---|---|
| 第一卷 | 实分析：测度、函数空间与几何分析 | [Book1.pdf](Book1.pdf) | [Book1.tex](Book1/Book1.tex) |
| 第二卷 | Fourier 分析、偏微分方程与调和分析 | [Book2.pdf](Book2.pdf) | [Book2.tex](Book2/Book2.tex) |
| 第三卷 | 复分析、共形几何与解析数论 | [Book3.pdf](Book3.pdf) | [Book3.tex](Book3/Book3.tex) |

全书现有89章、20篇附录，已形成初稿，仍在审校与修订。

## 文件结构

各卷按“编—章—节”组织，书前材料、附录、书后材料及图表分别存放于对应卷目录。`Shared/` 保存三卷共用的排版设置、书目数据库与索引样式。项目根目录的三份 PDF 为整卷成品。

## 编译

需要已安装的 XeLaTeX、Biber 和 makeindex（例如 TeX Live 2025）。每卷可以独立编译；Windows 下从项目根目录执行：

```powershell
& ./Book1/build-Book1.ps1 -NoPause
& ./Book2/build-Book2.ps1 -NoPause
& ./Book3/build-Book3.ps1 -NoPause
```

脚本依次执行 XeLaTeX、Biber、三类索引处理及后续稳定轮次，辅助文件输出至 `tmp/build/BookN/`。成功后更新根目录与卷目录的 PDF，并在卷目录生成 SyncTeX 文件，供编辑器双向定位。运行失败时保留上一份有效成品。

使用 TeXstudio 时，打开相应的 `BookN/BookN.tex`，主文件的编译指令会调用同目录脚本。若 TeX 工具未加入 PATH，可先把现有 TeX Live 的 `bin/windows` 目录加入当前终端的 PATH。

## 权利说明

本项目当前未授予开放源代码或开放内容许可证。公开访问本仓库不等于获得改编、再许可或商业使用授权，具体以[版权声明](版权声明.md)为准。
