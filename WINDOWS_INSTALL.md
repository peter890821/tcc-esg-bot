# Windows 安裝指南

## 遇到編譯錯誤？

如果你看到 "ERROR: Unknown compiler(s)" 或 "Failed to activate VS environment"，這是因為 Windows 缺少 C/C++ 編譯器。

### 解決方法（已處理）

我已經移除了需要編譯的 `unstructured` 套件。系統會自動使用 fallback 模式：

**功能影響**：
- ✅ 向量檢索：完全正常
- ✅ Metadata 篩選：完全正常  
- ✅ 框架引用：完全正常
- ⚠️ 表格解析：使用基本 PDF 解析（可能不如 Unstructured 精確）

### 現在請執行：

```powershell
# 清除之前失敗的安裝
pip cache purge

# 重新安裝（應該很快）
pip install -r requirements.txt

# 啟動
streamlit run app.py
```

### 如果你想要完整的表格解析功能

需要安裝 Visual Studio Build Tools：
1. 下載：https://visualstudio.microsoft.com/downloads/
2. 選擇 "C++ build tools"
3. 重新執行 `pip install unstructured[pdf]`

**但對大多數使用情況，基本 PDF 解析已足夠。**
