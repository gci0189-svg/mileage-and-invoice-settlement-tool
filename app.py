import streamlit as st
import math
import re
import pytesseract
from PIL import Image
import fitz  # PyMuPDF 套件，用來處理 PDF

# --- 網頁基本設定 ---
st.set_page_config(page_title="🚗 公司里程津貼與發票結算工具", page_icon="🧾", layout="centered")

st.title("🚗 里程津貼與加油發票結算工具")
st.write("請上傳加油發票 (支援 PDF 或圖片)，並輸入本月總里程津貼。系統會自動辨識並計算撥款金額。")

# 1. 輸入里程津貼 (預設帶入您常用的 7119)
total_allowance = st.number_input("請輸入本月「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票區域
uploaded_files = st.file_uploader("請上傳加油發票 (支援 PDF, JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

def extract_invoice_data(text):
    """從 OCR 辨識出的文字中抓取『總計』與『稅額』"""
    # 清理多餘的空白與符號，增加辨識率
    text = text.replace(" ", "").replace(",", "")
    
    # 使用正則表達式尋找金額
    amount_match = re.search(r'總計[:：]?(\d+)', text)
    tax_match = re.search(r'稅額[:：]?(\d+)', text)
    
    amount = int(amount_match.group(1)) if amount_match else 0
    tax = int(tax_match.group(1)) if tax_match else 0
    return amount, tax

# 3. 執行按鈕
if st.button("🚀 開始辨識與計算", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
        # 加入等待動畫，讓使用者知道系統正在處理
        with st.spinner('發票文字辨識中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 處理 PDF 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            # 設定 dpi=200 讓 PDF 轉圖片時文字更清晰，提升 OCR 準確率
                            pix = page.get_pixmap(dpi=200)
                            image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                            
                            # 進行繁體中文 OCR 辨識
                            text = pytesseract.image_to_string(image, lang='chi_tra')
                            amount, tax = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：成功辨識！總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                total_gas_amount += amount
                                total_tax_amount += tax
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：自動辨識失敗，請確認圖片清晰度或手動核對。")
                                
                    # 【處理一般圖片檔案 JPG, PNG】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra')
                        amount, tax = extract_invoice_data(text)
                        
                        if amount > 0:
                            st.success(f"📄 圖片 `{file.name}`：成功辨識！總計 **{amount}** 元 / 稅額 **{tax}** 元")
                            total_gas_amount += amount
                            total_tax_amount += tax
                        else:
                            st.error(f"📄 圖片 `{file.name}`：自動辨識失敗，請確認圖片清晰度或手動核對。")
                            
                except Exception as e:
                    st.error(f"❌ 處理檔案 {file.name} 時發生系統錯誤：{e}")

        st.divider()
        
        # 4. 結算與公式計算結果
        st.write("### 📊 本月結算總表")
        
        # 使用 Streamlit 的並排數據卡片顯示
        col1, col2 = st.columns(2)
        col1.metric(label="發票總加油金額", value=f"{total_gas_amount} 元")
        col2.metric(label="發票總稅額", value=f"{total_tax_amount} 元")
        
        # 核心計算邏輯：CEILING((總津貼 - 總加油金額)/7)
        if total_allowance > 0:
            # 確保不會出現負數的計算 (若加油金額大於津貼，剩餘津貼為 0)
            remainder = max(0, total_allowance - total_gas_amount)
            # 無條件進位計算 Personal Car 補貼
            personal_car = math.ceil(remainder / 7)
            
            st.write("---")
            st.write("#### 💡 撥款計算結果")
            st.write(f"**第一部分：總加油金額 ➡️ {total_gas_amount} 元**")
            
            st.write(f"**第二部分：Personal Car 里程津貼換算**")
            st.code(f"公式：無條件進位( ({total_allowance} - {total_gas_amount}) / 7 )")
            
            st.success(f"🎉 第二部分應撥款金額： **{personal_car} 元**")
            
            # 最終總撥款核對
            final_total = total_gas_amount + (personal_car * 7)
            st.caption(f"📝 驗算參考：加油金額 {total_gas_amount} + (Personal Car {personal_car} × 7) = 相當於總津貼額度 {final_total} 元")
