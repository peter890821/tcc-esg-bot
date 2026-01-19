import io
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st
from docx import Document
from pptx import Presentation
from pypdf import PdfReader

try:
    import google.generativeai as genai
except Exception:  # pragma: no cover
    genai = None


DEFAULT_CSV_PATH = "MSCI_Methodology_Full_KB.csv"
KB_DIRECTORY = "kb"  # 專門放長期知識庫檔案的資料夾
REQUIRED_COLUMNS = {"text_content", "source_file", "doc_type"}


@dataclass
class RetrievedChunk:
    text_content: str
    source_file: str
    doc_type: str
    score: int


def _safe_str(x) -> str:
    return "" if x is None else str(x)


def tokenize_question(question: str) -> List[str]:
    """
    Very simple tokenization:
    - Extract alphanumeric "words" (English/numbers)
    - Extract CJK sequences (Chinese/Japanese/Korean characters)
    """
    q = question.strip().lower()
    if not q:
        return []

    tokens: List[str] = []
    tokens += re.findall(r"[a-z0-9]+", q)
    tokens += re.findall(r"[\u4e00-\u9fff]+", q)

    # Keep unique tokens, preserve order
    seen = set()
    deduped = []
    for t in tokens:
        if t and t not in seen:
            seen.add(t)
            deduped.append(t)
    return deduped


def simple_retrieve_topk(df: pd.DataFrame, question: str, k: int = 5) -> List[RetrievedChunk]:
    """
    Simple string matching retrieval:
    score = sum(count(token in text_content)) + (bonus if full question is substring)
    """
    tokens = tokenize_question(question)
    if not tokens:
        return []

    q_lower = question.strip().lower()

    chunks: List[RetrievedChunk] = []
    for _, row in df.iterrows():
        text = _safe_str(row.get("text_content"))
        if not text:
            continue
        text_lower = text.lower()

        score = 0
        for t in tokens:
            score += text_lower.count(t)
        if q_lower and q_lower in text_lower:
            score += 5

        if score > 0:
            chunks.append(
                RetrievedChunk(
                    text_content=text,
                    source_file=_safe_str(row.get("source_file")),
                    doc_type=_safe_str(row.get("doc_type")),
                    score=score,
                )
            )

    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks[:k]


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    texts: List[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text:
            texts.append(page_text)
    return "\n\n".join(texts)


def _extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paras = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paras)


def _extract_text_from_pptx(file_bytes: bytes) -> str:
    pres = Presentation(io.BytesIO(file_bytes))
    texts: List[str] = []
    for slide in pres.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                texts.append(shape.text)
    return "\n\n".join(texts)


@st.cache_data(show_spinner=False)
def load_kb_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Load uploaded knowledge base file into a standardized DataFrame
    with columns: text_content, source_file, doc_type.

    支援類型：CSV、Excel、PDF、Word、PPT。
    - 對於非 CSV/Excel，我們會把整個檔案文字當成一個段落。
    """
    name = filename or "uploaded_file"
    lower = name.lower()
    ext = ""
    if "." in lower:
        ext = lower.rsplit(".", 1)[-1]

    buffer = io.BytesIO(file_bytes)

    # Structured: CSV / Excel
    if ext in {"csv", "xlsx"}:
        if ext == "xlsx":
            table = pd.read_excel(buffer)
        else:
            table = pd.read_csv(buffer)

        cols = set(str(c) for c in table.columns)
        # 若已經有標準欄位，就直接使用
        if REQUIRED_COLUMNS.issubset(cols):
            df = table.copy()
            for col in REQUIRED_COLUMNS:
                df[col] = df[col].fillna("").astype(str)
            return df[list(REQUIRED_COLUMNS)]

        # 否則：把整張表轉成一段文字
        text_repr = table.astype(str).to_csv(index=False)
        return pd.DataFrame(
            [
                {
                    "text_content": text_repr,
                    "source_file": name,
                    "doc_type": ext or "table",
                }
            ]
        )

    # Unstructured: PDF / DOCX / PPTX
    if ext == "pdf":
        text = _extract_text_from_pdf(file_bytes)
    elif ext in {"docx", "doc"}:
        text = _extract_text_from_docx(file_bytes)
    elif ext in {"pptx", "ppt"}:
        text = _extract_text_from_pptx(file_bytes)
    else:
        # Fallback：當作一般文字檔
        try:
            text = buffer.read().decode("utf-8")
        except Exception:
            text = ""

    return pd.DataFrame(
        [
            {
                "text_content": text,
                "source_file": name,
                "doc_type": ext or "file",
            }
        ]
    )


@st.cache_data(show_spinner=False)
def load_csv_from_path(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def get_kb_dataframe(uploaded_files) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Returns (df, error_message). error_message is None when success.

    知識來源優先順序：
    1. 專案內的 kb/ 資料夾（長期知識庫，啟動時自動載入）
    2. 使用者在網頁上臨時上傳的檔案
    3. 專案根目錄下的預設 CSV：MSCI_Methodology_Full_KB.csv
    """
    dfs: List[pd.DataFrame] = []

    # 1) 掃描本地 kb/ 資料夾（遞迴掃描所有子資料夾）
    if os.path.isdir(KB_DIRECTORY):
        for root, _, files in os.walk(KB_DIRECTORY):
            for name in files:
                lower = name.lower()
                if not lower.endswith((".csv", ".xlsx", ".pdf", ".docx", ".pptx")):
                    continue
                path = os.path.join(root, name)
                # 保留相對於 kb/ 的完整路徑（包含子資料夾），例如：環境相關/report.pdf
                rel_path = os.path.relpath(path, KB_DIRECTORY)
                try:
                    with open(path, "rb") as f:
                        file_bytes = f.read()
                    df_part = load_kb_from_bytes(file_bytes, rel_path)
                    dfs.append(df_part)
                except Exception:
                    # 若單一檔案失敗，不影響整體，可加日後 logging
                    continue

    # 2) 網頁上臨時上傳的檔案
    if uploaded_files:
        try:
            for f in uploaded_files:
                file_bytes = f.getvalue()
                df_part = load_kb_from_bytes(file_bytes, f.name)
                dfs.append(df_part)
        except Exception as e:
            return None, f"讀取上傳檔案失敗：{e}"

    # 3) 若前兩者都沒有資料，試著載入預設 CSV
    if not dfs:
        try:
            df = load_csv_from_path(DEFAULT_CSV_PATH)
        except FileNotFoundError:
            return None, (
                f"找不到任何知識庫資料。\n"
                f"- 若要使用預設檔案，請將 {DEFAULT_CSV_PATH} 放在專案根目錄。\n"
                f"- 或建立 `{KB_DIRECTORY}` 資料夾，放入 CSV/Excel/PDF/Word/PPT 檔案。\n"
                f"- 或直接在左側上傳 ESG 知識庫檔案。"
            )
        except pd.errors.EmptyDataError:
            return None, "預設 CSV 檔案是空的或格式不正確。"
        except UnicodeDecodeError:
            return None, "預設 CSV 編碼讀取失敗。請嘗試另存為 UTF-8 後重新放置。"
        except Exception as e:
            return None, f"讀取預設 CSV 失敗：{e}"

        missing = REQUIRED_COLUMNS - set(df.columns)
        if missing:
            return None, f"預設 CSV 缺少必要欄位：{', '.join(sorted(missing))}。需要欄位：{', '.join(sorted(REQUIRED_COLUMNS))}"

        for col in REQUIRED_COLUMNS:
            df[col] = df[col].fillna("").astype(str)

        return df[list(REQUIRED_COLUMNS)], None

    # 合併來自 kb/ 與上傳的所有資料
    df_all = pd.concat(dfs, ignore_index=True)
    for col in REQUIRED_COLUMNS:
        if col not in df_all.columns:
            df_all[col] = ""
        df_all[col] = df_all[col].fillna("").astype(str)

    return df_all[list(REQUIRED_COLUMNS)], None


def build_prompt(context: str, question: str) -> str:
    return (
        "你現在是台泥集團 (TCC) 的首席永續策略顧問。"
        f"請根據以下背景資料回答問題：{context}。"
        f"使用者問題：{question}。"
        "請用繁體中文，以專業、結構化的方式回答，並引用具體規則。"
    )


def generate_with_gemini(api_key: str, prompt: str) -> str:
    if genai is None:
        raise RuntimeError("找不到 google-generativeai 套件。請確認已安裝 requirements.txt 內的依賴。")

    genai.configure(api_key=api_key)

    # 先查出目前這個 API Key 可用的模型
    try:
        available_models = list(genai.list_models())
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Gemini 呼叫失敗：無法取得可用模型清單，請確認：\n"
            "1. 這支 API Key 是在 Google AI Studio 產生的，而不是 Google Cloud / 其他服務。\n"
            "2. 已在對應的帳號啟用 Gemini API，且網路可以連到 Google。\n"
            f"詳細錯誤：{e}"
        ) from e

    text_models = [
        m
        for m in available_models
        if hasattr(m, "supported_generation_methods")
        and "generateContent" in getattr(m, "supported_generation_methods", [])
    ]

    if not text_models:
        raise RuntimeError(
            "Gemini 呼叫失敗：這支 API Key 名下目前沒有支援 generateContent 的模型可用。\n"
            "請到 Google AI Studio 的 Models / API 頁面，確認帳號已開通 Gemini 1.5（例如 gemini-1.5-flash）後再試一次。"
        )

    # 優先挑選名稱中包含 1.5 的模型，其次任意可用模型
    preferred = [m for m in text_models if "1.5" in getattr(m, "name", "")]
    chosen = (preferred or text_models)[0]
    model_name = getattr(chosen, "name", "gemini-1.5-flash")

    try:
        model = genai.GenerativeModel(model_name)
        resp = model.generate_content(prompt)
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "Gemini 呼叫失敗：雖然成功找到可用模型 "
            f"`{model_name}`，但在呼叫 generateContent 時出現錯誤：{e}\n"
            "請到 Google AI Studio 測試同一支 API Key 是否可以正常呼叫相同模型。"
        ) from e

    text = getattr(resp, "text", None)
    if not text:
        # Fallback for some response shapes
        try:
            text = resp.candidates[0].content.parts[0].text  # type: ignore[attr-defined]
        except Exception:
            text = ""

    if not text.strip():
        raise RuntimeError("Gemini 未回傳有效文字內容，請稍後再試或確認 API Key/配額。")

    return text.strip()


def main() -> None:
    st.set_page_config(page_title="TCC ESG Intelligent Knowledge Base", layout="wide")

    st.title("🌿 台泥 (TCC) 企業 ESG 智能知識庫")
    st.caption("Powered by Google Gemini 1.5 Pro & MSCI Methodology")

    with st.sidebar:
        st.header("⚙️ 設定 (Settings)")
        api_key = st.text_input("Google Gemini API Key", type="password", value="")
        uploaded_files = st.file_uploader(
            "上傳 ESG 知識庫檔案（可多選：CSV / Excel / PDF / Word / PPT）",
            type=["csv", "xlsx", "pdf", "docx", "pptx"],
            accept_multiple_files=True,
        )

    df, kb_err = get_kb_dataframe(uploaded_files)
    if kb_err:
        st.error(kb_err)

    if not api_key.strip():
        st.info("請先在側邊欄輸入 **Google Gemini API Key** 才能開始分析。")

    question = st.text_area(
        "請輸入你的問題",
        placeholder="例如：MSCI 對於環境管理（E）在評等方法論中通常會如何衡量？",
        disabled=not api_key.strip(),
    )

    run = st.button("開始分析", type="primary", disabled=(not api_key.strip() or not question.strip() or df is None))

    if run:
        if df is None:
            st.error("知識庫尚未就緒：請上傳有效 CSV 或放置預設檔案於同目錄。")
            return

        with st.spinner("正在檢索相關段落 (top 5) ..."):
            chunks = simple_retrieve_topk(df, question, k=5)

        if not chunks:
            st.warning("找不到與問題相關的段落（以簡易字串比對）。你可以嘗試換個說法、加入更多關鍵字，或確認 CSV 的 `text_content` 內容。")
            return

        context = "\n\n---\n\n".join([c.text_content for c in chunks])
        prompt = build_prompt(context=context, question=question.strip())

        try:
            with st.spinner("正在呼叫 Gemini 1.5 Pro 生成回答 ..."):
                answer = generate_with_gemini(api_key.strip(), prompt)
        except Exception as e:
            st.error(str(e))
            return

        st.subheader("AI 回答")
        st.write(answer)

        with st.expander("查看參考來源 / References"):
            for i, c in enumerate(chunks, start=1):
                st.markdown(f"**#{i}** 來源檔案：`{c.source_file}`｜文件類型：`{c.doc_type}`｜匹配分數：`{c.score}`")
                st.write(c.text_content)
                st.divider()


if __name__ == "__main__":
    main()

