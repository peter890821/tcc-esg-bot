"""
測試向量檢索功能
運行方式: streamlit run app.py (手動測試)
"""

# 測試案例：驗證語義檢索能否理解同義詞

test_cases = [
    {
        "question": "脫碳路徑",
        "expected_keywords": ["減排", "低碳", "淨零", "碳中和", "decarbonization"],
        "description": "測試是否能找到同義詞：減排策略、低碳轉型"
    },
    {
        "question": "氣候風險揭露",
        "expected_keywords": ["TCFD", "氣候相關", "風險", "disclosure"],
        "description": "測試框架標準識別：TCFD"
    },
    {
        "question": "Scope 1 排放量",
        "expected_keywords": ["Scope 1", "直接排放", "溫室氣體"],
        "description": "測試專有名詞精確匹配"
    },
    {
        "question": "替代燃料使用率",
        "expected_keywords": ["替代燃料", "廢棄物", "生質能", "alternative fuel"],
        "description": "測試中英文混合查詢"
    },
    {
        "question": "IFRS S2 揭露要求",
        "expected_keywords": ["IFRS", "S2", "氣候", "揭露"],
        "description": "測試框架條文識別"
    }
]

print("=" * 60)
print("TCC ESG Bot - Vector Search Test Cases")
print("=" * 60)

for i, case in enumerate(test_cases, 1):
    print(f"\n測試 {i}: {case['description']}")
    print(f"查詢問題: {case['question']}")
    print(f"期望關鍵字: {', '.join(case['expected_keywords'])}")
    print("-" * 60)

print("\n請在 Streamlit 界面手動測試上述問題，驗證檢索準確度。")
print("評估標準：")
print("  ✓ Top-5 結果中至少 3 篇包含期望關鍵字")
print("  ✓ 相關度分數 > 50%")
print("  ✓ 能找到同義詞相關文件（非字面匹配）")
