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
    """從 OCR 辨識出的文字中抓取『所有』的『總計』與『稅額』"""
    # 清理多餘的空白與符號
    text_clean = text.replace(" ", "").replace(",", "")
    
    # 使用 findall 抓取同一頁中【所有】的金額
    # \d{2,} 代表限定數字至少要 2 位數以上，這樣可以避開「合計 1 項」的 1
    amount_matches = re.findall(r'(?:總計|合計)[:：]?(\d{2,})', text_clean)
    tax_matches = re.findall(r'稅額[:：]?(\d+)', text_clean)
    
    # 將找到的文字轉換成整數清單
    amounts =[int(a) for a in amount_matches]
    taxes =[int(t) for t in tax_matches]
    
    # 回傳：總額加總、稅額加總、各別金額清單、各別稅額清單、原始 OCR 文字
    return sum(amounts), sum(taxes), amounts, taxes, text

# 3. 執行按鈕
if st.button("🚀 開始辨識與計算", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
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
                            # 將 DPI 提升到 300，讓發票上的小字更清晰
                            pix = page.get_pixmap(dpi=300)
                            image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                            
                            text = pytesseract.image_to_string(image, lang='chi_tra')
                            amount, tax, amounts_list, taxes_list, raw_text = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：找到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                st.caption(f"🔍 成功抓取金額：{amounts_list} | 稅額：{taxes_list}")
                                total_gas_amount += amount
                                total_tax_amount += tax
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：自動辨識失敗，可能是圖片不夠清晰或排版特殊。")
                            
                            # 除錯工具：折疊式的原始文字檢視區
                            with st.expander(f"🛠️ 查看第 {page_num + 1} 頁的 OCR 原始文字 (若抓錯可展開核對)"):
                                st.text(raw_text)
                                
                    # 【處理一般圖片檔案 JPG, PNG】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra')
                        amount, tax, amounts_list, taxes_list, raw_text = extract_invoice_data(text)
                        
                        if amount > 0:
                            st.success(f"📄 圖片 `{file.name}`：找到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                            st.caption(f"🔍 成功抓取金額：{amounts_list} | 稅額：{taxes_list}")
                            total_gas_amount += amount
                            total_tax_amount += tax
                        else:
                            st.error(f"📄 圖片 `{file.name}`：自動辨識失敗，可能是圖片不夠清晰或排版特殊。")
                            
                        with st.expander(f"🛠️ 查看圖片的 OCR 原始文字 (若抓錯可展開核對)"):
                            st.text(raw_text)
                            
                except Exception as e:
                    st.error(f"❌ 處理檔案 {file.name} 時發生系統錯誤：{e}")

        st.divider()
        
        # 4. 結算與公式計算結果
        st.write("### 📊 本月結算總表")
        
        col1, col2 = st.columns(2)
        col1.metric(label="發票總加油金額", value=f"{total_gas_amount} 元")
        col2.metric(label="發票總稅額", value=f"{total_tax_amount} 元")
        
        if total_allowance > 0:
            remainder = max(0, total_allowance - total_gas_amount)
            personal_car = math.ceil(remainder / 7)
            
            st.write("---")
            st.write("#### 💡 撥款計算結果")
            st.write(f"**第一部分：總加油金額 ➡️ {total_gas_amount} 元**")
            
            st.write(f"**第二部分：Personal Car 里程津貼換算**")
            st.code(f"公式：無條件進位( ({total_allowance} - {total_gas_amount}) / 7 )")
            
            st.success(f"🎉 第二部分應撥款金額： **{personal_car} 元**")
            
            final_total = total_gas_amount + (personal_car * 7)
            st.caption(f"📝 驗算參考：加油金額 {total_gas_amount} + (Personal Car {personal_car} × 7) = 相當於總津貼額度 {final_total} 元")
