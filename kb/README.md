# TCC ESG Bot 知識庫建議

此資料夾用於存放長期 ESG 知識庫文件。

## 推薦結構

```
kb/
├── 永續報告/
│   ├── TCC_ESG_Report_2024.pdf
│   ├── TCC_ESG_Report_2023.pdf
│   └── TCC_ESG_Report_2022.pdf
│
├── 框架文件/
│   ├── IFRS_S1_General_Requirements.pdf
│   ├── IFRS_S2_Climate_Disclosures.pdf
│   ├── GRI_Standards_2021.pdf
│   ├── SASB_EM-CM_Construction_Materials.pdf
│   └── TCFD_Recommendations.pdf
│
├── 碳盤查/
│   ├── Carbon_Inventory_2024.xlsx
│   ├── Carbon_Inventory_2023.xlsx
│   └── Scope123_Methodology.docx
│
├── 政策文件/
│   ├── TCC_Climate_Policy.pdf
│   ├── Energy_Management_Policy.docx
│   └── Supplier_ESG_Guidelines.pdf
│
└── 法規/
    ├── EU_CBAM_Regulation.pdf
    ├── Taiwan_Climate_Act.pdf
    └── ISO_14064_Standard.pdf
```

## 檔名最佳實踐

包含年份以自動提取 metadata：
- ✅ `TCC_ESG_Report_2024.pdf`
- ✅ `Carbon_Inventory_2024_v1.0.xlsx`
- ❌ `report.pdf` (無年份)

## 啟動時自動載入

系統會在啟動時自動掃描此資料夾（包含子資料夾）並載入所有：
- CSV
- Excel (.xlsx)
- PDF
- Word (.docx)
- PowerPoint (.pptx)
