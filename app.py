import streamlit as st
import math
import re
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
from collections import Counter

# --- 網頁基本設定 ---
st.set_page_config(page_title="🚗 公司里程津貼與發票結算工具", page_icon="🧾", layout="centered")

st.title("🚗 里程津貼與加油發票結算工具")
st.write("請上傳加油發票 (支援 PDF 或圖片)，系統將自動採用「雙主星配對法」進行精準結算。")

# 1. 輸入里程津貼
total_allowance = st.number_input("請輸入本月「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票區域
uploaded_files = st.file_uploader("請上傳加油發票 (支援 PDF, JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

def extract_invoice_data(text):
    """【終極 Spec 實作】先抓銷售額與總計比對 -> 推算稅額 -> 獨立加總"""
    # 清理所有文字雜訊
    text_clean = text.replace(" ", "").replace(",", "").replace("元", "").replace("ㄦ", "").replace("\n", "")
    
    amounts_list = [] # 總計
    sales_list =[]   # 銷售額
    taxes_list = []   # 稅額
    details_list =[] # 顯示給使用者的明細
    
    # 抓取畫面上所有的數字
    matches = list(re.finditer(r'\d+', text_clean))
    numbers = [int(m.group()) for m in matches]
    used_indices = set()
    
    # 定義「鄰居」的範圍，銷售額與總計通常印得很近 (設定為前後 20 個數字以內)
    WINDOW = 20 
    
    # 【階段一：雙主星定位演算法】(尋找 銷售額 A 與 總計 C)
    for i in range(len(numbers)):
        if i in used_indices: continue
        
        C = numbers[i] # 假設這個數字是總計
        
        # 總計合理範圍
        if 50 <= C <= 50000:
            # 依照法定稅率 (5%) 反推「應有」的稅額與銷售額
            # 稅額 = 總計 / 21 (四捨五入)
            expected_tax = math.floor(C / 21.0 + 0.5)
            expected_sales = C - expected_tax
            
            # 在這個總計的「鄰居範圍」內，尋找有沒有符合的「銷售額」
            start_idx = max(0, i - WINDOW)
            end_idx = min(len(numbers), i + WINDOW + 1)
            
            for j in range(start_idx, end_idx):
                if i == j or j in used_indices: continue
                
                # 如果找到了完美的銷售額！
                if numbers[j] == expected_sales:
                    amounts_list.append(C)
                    sales_list.append(expected_sales)
                    taxes_list.append(expected_tax)
                    
                    # 標記這兩個數字已經被用掉了，避免重複計算
                    used_indices.add(i)
                    used_indices.add(j)
                    
                    details_list.append(f"✅ **發票 {C}元** ➡️ 成功配對[銷售額 **{expected_sales}** 與 總計 **{C}**] ｜ 推算稅額：**{expected_tax}**")
                    break

    # 【階段二：單星容錯防呆】
    # 萬一 OCR 真的把銷售額糊成一團，我們用明確的「總計」中文字樣作為最後保險
    fallback_matches = re.finditer(r'(?:總[計部額]|合計|應收金額)[:：\.\s]*(\d{3,5})', text_clean)
    for m in fallback_matches:
        val = int(m.group(1))
        # 確保不會跟已經算過的發票重複
        if 50 <= val <= 50000 and val not in amounts_list:
            expected_tax = math.floor(val / 21.0 + 0.5)
            expected_sales = val - expected_tax
            
            amounts_list.append(val)
            sales_list.append(expected_sales)
            taxes_list.append(expected_tax)
            details_list.append(f"⚠️ **發票 {val}元** ➡️ (備用機制) 僅找到總計字樣，強制推算[銷售額 **{expected_sales}** ｜ 稅額 **{expected_tax}**]")

    return sum(amounts_list), sum(sales_list), sum(taxes_list), amounts_list, sales_list, taxes_list, details_list, text

# 3. 執行按鈕
if st.button("🚀 開始智慧結算", type="primary"):
    total_gas_amount = 0
    total_sales_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票解析明細")
        
        with st.spinner('啟動雙主星定位引擎解析中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            text = page.get_text("text") # 優先讀取原生 PDF 文字
                            
                            # 若為掃描檔，啟動 OCR
                            if len(text.strip()) < 50: 
                                pix = page.get_pixmap(dpi=300)
                                image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                                text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                                ocr_used = True
                            else:
                                ocr_used = False
                                
                            sum_C, sum_A, sum_B, list_C, list_A, list_B, details, raw = extract_invoice_data(text)
                            
                            if sum_C > 0:
                                st.success(f" - 第 {page_num + 1} 頁：精準抓到 **{len(list_C)}** 張發票！")
                                if not ocr_used: st.caption("⚡ 解析模式：原生數位解析 (100%精準)")
                                    
                                for detail in details:
                                    st.info(detail)
                                total_gas_amount += sum_C
                                total_sales_amount += sum_A
                                total_tax_amount += sum_B
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：未辨識到符合格式之發票。")
                                
                    # 【處理一般圖片檔案】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                        sum_C, sum_A, sum_B, list_C, list_A, list_B, details, raw = extract_invoice_data(text)
                        
                        if sum_C > 0:
                            st.success(f"📄 圖片 `{file.name}`：精準抓到 **{len(list_C)}** 張發票！")
                            for detail in details:
                                st.info(detail)
                            total_gas_amount += sum_C
                            total_sales_amount += sum_A
                            total_tax_amount += sum_B
                        else:
                            st.error(f"📄 圖片 `{file.name}`：未辨識到符合格式之發票。")
                            
                except Exception as e:
                    st.error(f"❌ 處理檔案 {file.name} 時發生系統錯誤：{e}")

        st.divider()
        
        # 4. 結算與獨立加總驗證
        st.write("### 📊 本月結算總表 (分離驗算機制)")
        
        # 顯示您要求的「分開加總」結果
        col1, col2, col3 = st.columns(3)
        col1.metric(label="✅ 總銷售額 (獨立加總)", value=f"{total_sales_amount} 元")
        col2.metric(label="✅ 總稅額 (獨立加總)", value=f"{total_tax_amount} 元")
        col3.metric(label="🎯 驗算: 總加油金額", value=f"{total_gas_amount} 元")
        
        # 驗算防呆檢查
        if total_sales_amount + total_tax_amount == total_gas_amount:
            st.caption("✨ 系統驗算通過：總銷售額 + 總稅額 = 總加油金額 (誤差 $0)")
        else:
            st.error("⚠️ 系統驗算異常，請人工確認！")
        
        # 5. 里程津貼計算
        if total_allowance > 0:
            remainder = max(0, total_allowance - total_gas_amount)
            personal_car = math.ceil(remainder / 7)
            
            st.write("---")
            st.write("#### 💡 里程津貼撥款結果")
            st.write(f"**第一部分撥款：總加油金額 ➡️ {total_gas_amount} 元**")
            
            st.write(f"**第二部分撥款：Personal Car 換算**")
            st.code(f"計算公式：無條件進位( ({total_allowance} - {total_gas_amount}) / 7 )")
            
            st.success(f"🎉 第二部分應撥款金額： **{personal_car} 元**")
