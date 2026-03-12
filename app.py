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

# 1. 輸入里程津貼
total_allowance = st.number_input("請輸入本月「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票區域
uploaded_files = st.file_uploader("請上傳加油發票 (支援 PDF, JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

def extract_invoice_data(text):
    """結合「台灣法定稅率公式」與「鄰近區塊法則」的終極校驗法"""
    text_clean = text.replace(" ", "").replace(",", "").replace("元", "").replace("ㄦ", "")
    
    amounts_list = []
    taxes_list =[]
    details_list =[]
    
    # 提取畫面上所有的數字，並記錄它們的先後順序
    number_matches =[int(m.group()) for m in re.finditer(r'\d+', text_clean)]
    used_indices = set()
    
    # 限制 A, B, C 這三個數字，必須在連續的 25 個數字之內 (防止跨行亂湊)
    WINDOW_SIZE = 25 
    
    # 【第一階段】：嚴格比對 A(銷售額) + B(稅額) = C(總計)
    for i in range(len(number_matches)):
        if i in used_indices: continue
        
        window = number_matches[i:i+WINDOW_SIZE]
        match_found = False
        
        for idx_c in range(len(window)):
            for idx_b in range(len(window)):
                for idx_a in range(len(window)):
                    # 必須是三個不同的數字
                    if len(set([idx_a, idx_b, idx_c])) == 3:
                        A = window[idx_a]
                        B = window[idx_b]
                        C = window[idx_c]
                        
                        # 條件一：加總正確且總計 >= 100 (過濾掉零星的小數字)
                        if C >= 100 and A + B == C:
                            # 條件二：【台灣發票絕對公式】 稅額必須完美等於 (總計 / 21) 的傳統四捨五入
                            expected_tax = math.floor(C / 21.0 + 0.5)
                            
                            if B == expected_tax:
                                global_a = i + idx_a
                                global_b = i + idx_b
                                global_c = i + idx_c
                                
                                if global_a not in used_indices and global_b not in used_indices and global_c not in used_indices:
                                    amounts_list.append(C)
                                    taxes_list.append(B)
                                    used_indices.update([global_a, global_b, global_c])
                                    details_list.append(f"✅ **{C}元** (精準區塊比對：明細 {A} + 稅額 {B} = 總計 {C})")
                                    match_found = True
                                    break
                if match_found: break
            if match_found: break

    # 【第二階段】：容錯比對 (如果 OCR 看不清楚銷售額 A，只要 B 和 C 完美符合公式也算對！)
    for i in range(len(number_matches)):
        if i in used_indices: continue
        
        window = number_matches[i:i+WINDOW_SIZE]
        match_found = False
        
        for idx_c in range(len(window)):
            for idx_b in range(len(window)):
                if idx_c != idx_b:
                    B = window[idx_b]
                    C = window[idx_c]
                    
                    if C >= 100:
                        expected_tax = math.floor(C / 21.0 + 0.5)
                        if B == expected_tax:
                            global_b = i + idx_b
                            global_c = i + idx_c
                            
                            if global_b not in used_indices and global_c not in used_indices:
                                amounts_list.append(C)
                                taxes_list.append(B)
                                used_indices.update([global_b, global_c])
                                details_list.append(f"⚠️ **{C}元** (容錯區塊比對：找到相鄰稅額 {B} 與總計 {C})")
                                match_found = True
                                break
            if match_found: break

    return sum(amounts_list), sum(taxes_list), amounts_list, taxes_list, details_list, text

# 3. 執行按鈕
if st.button("🚀 開始辨識與結算", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
        with st.spinner('啟動智慧引擎解析中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 處理 PDF 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            
                            # 優先嘗試：原生 PDF 文字提取 (速度最快、0 誤差)
                            text = page.get_text("text")
                            
                            # 若抓不到文字 (代表是掃描圖片檔)，啟動 OCR 視覺辨識
                            if len(text.strip()) < 50:
                                pix = page.get_pixmap(dpi=300)
                                image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                                text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                                ocr_used = True
                            else:
                                ocr_used = False
                                
                            amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：成功抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                if ocr_used:
                                    st.caption("🔍 解析模式：AI 視覺辨識 (OCR)")
                                else:
                                    st.caption("⚡ 解析模式：原生 PDF 數位解析 (100%精準)")
                                    
                                for detail in details_list:
                                    st.info(detail)
                                total_gas_amount += amount
                                total_tax_amount += tax
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：自動辨識失敗。")
                                
                    # 【處理一般圖片檔案】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                        amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                        
                        if amount > 0:
                            st.success(f"📄 圖片 `{file.name}`：成功抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                            for detail in details_list:
                                st.info(detail)
                            total_gas_amount += amount
                            total_tax_amount += tax
                        else:
                            st.error(f"📄 圖片 `{file.name}`：自動辨識失敗。")
                            
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
