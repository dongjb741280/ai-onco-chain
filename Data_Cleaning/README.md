# Data_Cleaning — 指南 PDF 转 Markdown

把乳腺癌诊疗指南 PDF（扫描版 / 文本版）转成结构化 Markdown，供下游知识库与决策系统使用。

## 目录结构

```
Data_Cleaning/
├── doc/                          # 原始输入（已 gitignore：源 PDF + 病例数据）
│   ├── csco/                     # CSCO 指南 PDF（扫描版）
│   │   └── 2026CSCO乳腺癌诊疗指南.pdf
│   ├── caca/                     # CACA 指南 PDF（文本版，双栏）
│   │   └── 中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.pdf
│   ├── HER2决策系统-病例评测表-V1-虚构与真实分开.xlsx
│   └── 系统输入/                 # 病例 JSON（HER2 决策系统输入，非本流水线）
├── process/                  # PDF → Markdown 处理程序
│   ├── csco_ocr.py               # CSCO：PaddleOCR（PP-OCRv5）文字识别 + 启发式表格
│   ├── csco_normalize.py         # CSCO：后处理（推荐等级 Ⅰ/Ⅱ/Ⅲ 归一化）
│   ├── caca_ocr.py               # CACA：PP-StructureV3 版面 + 表格结构识别
│   ├── caca_extract.py           # CACA：fitz 文本抽取（双栏版式）
│   ├── output/                   # 产物 Markdown
│   │   ├── guide_csco.md
│   │   └── guide_caca.md
│   ├── pages_csco/               # CSCO 页面渲染（gitignore，pdftoppm 可再生）
│   └── .venv/                    # paddleocr / paddlex / PyMuPDF 环境
└── PDF转Markdown方案对比.md      # 三种 OCR 方案对比（历史参考，旧命名）
```

## 流水线

命名约定：脚本按 `{指南}_{动作}.py` 组织，`csco` = 中国临床肿瘤学会，`caca` = 中国抗癌协会；新增指南按同规则扩展（如 `nccn_*`）。

### CSCO（扫描版 PDF，需 OCR）

```bash
cd Data_Cleaning

# 1. 渲染 PDF → PNG
pdftoppm -r 300 -gray -png doc/csco/2026CSCO乳腺癌诊疗指南.pdf process/pages_csco/pg

# 2. OCR 成 Markdown
cd process
.venv/bin/python csco_ocr.py pages_csco output/guide_csco.md

# 3. 后处理（就地归一化推荐等级）
.venv/bin/python csco_normalize.py
```

### CACA（文本版双栏 PDF，两条路线）

- **fitz 文本抽取**（快，无版面 / 表格结构）：
  ```bash
  cd Data_Cleaning/process
  .venv/bin/python caca_extract.py   # 写 output/中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.md
  ```

- **PP-StructureV3 OCR**（慢，含版面 + 表格结构，表格转 Markdown 最干净）：
  ```bash
  cd Data_Cleaning
  pdftoppm -r 300 -gray -png doc/caca/中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.pdf process/pages_caca/pg
  cd process
  .venv/bin/python caca_ocr.py pages_caca output/guide_caca.md
  ```

## 产物

| 产物 | 来源 | 说明 |
| --- | --- | --- |
| `output/guide_csco.md` | `csco_ocr.py` + `csco_normalize.py` | CSCO 指南全文（OCR） |
| `output/guide_caca.md` | `caca_ocr.py` | CACA 指南全文（PP-StructureV3） |
| `output/中国抗癌协会乳腺癌诊治指南与规范（2026 年版）.md` | `caca_extract.py` | CACA 指南全文（fitz 文本） |

## 环境

依赖装在 `process/.venv`（Python 3.10 + paddleocr / paddlex / PyMuPDF）。首次运行 OCR 脚本会自动下载 PP-OCRv5 / PP-StructureV3 模型。CACA 的 PP-StructureV3 多模型推理内存占用高，脚本内已对长边 >2500px 的大图降采样防 OOM。

## 历史参考

`PDF转Markdown方案对比.md` 记录了 CSCO 指南的三种处理方式（macOS Vision / PaddleOCR / PP-StructureV3）对比；文中引用的目录/脚本名已过时（`process/`、`process_ocr/`、`ocr.py`、`guide.md` 等），仅供选型参考。
