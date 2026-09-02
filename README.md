# 分析学

R. EverStarine 编写的三卷本分析学教材项目。全书依照 [计划纲要](计划纲要.md) 分为三卷，每卷均可独立编译为 PDF。

## 三卷结构

- 第一卷：[实分析：测度、几何测度与 Sobolev 空间](Book1/Book1.tex)，成品见 [Book1.pdf](Book1.pdf)。
- 第二卷：[Fourier 分析、偏微分方程与调和分析](Book2/Book2.tex)，成品见 [Book2.pdf](Book2.pdf)。
- 第三卷：[复分析、共形几何与解析数论](Book3/Book3.tex)，成品见 [Book3.pdf](Book3.pdf)。

三卷共享 [基础排版文件](Shared/Preamble.tex)，各卷分别维护自己的书前、正文、附录和书后内容。

## 编译

使用 XeLaTeX，在相应卷目录中编译该卷主文件，例如：

```powershell
cd Book1
xelatex Book1.tex
xelatex Book1.tex
```

建议把辅助文件输出到临时构建目录，只将最终的三份 PDF 放在项目根目录。

## 编辑规范

- [版权声明](版权声明.md)
- [格式规范](格式规范.md)
- [术语规范](术语规范.md)
- [写作规范](写作规范.md)

## 权利说明

本项目当前未授予开放源代码或开放内容许可证。公开访问本仓库不等于获得改编、再许可或商业使用授权，具体以 [版权声明](版权声明.md) 为准。
