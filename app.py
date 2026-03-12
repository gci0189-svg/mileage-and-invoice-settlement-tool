import streamlit as st
import math
import re
import pytesseract
from PIL import Image
import fitz  # PyMuPDF 套件，用來處理 PDF
from collections import Counter # 新增：用來統計數字池

# --- 網頁基本設定 ---
st.set_page_config(page_title="🚗 公司里程津貼與發票結算工具", page_icon="🧾", layout="centered")

st.title("🚗 里程津貼與加油發票結算工具")
st.write("請上傳加油發票 (支援 PDF 或圖片)，並輸入本月總里程津貼。系統會自動辨識並計算撥款金額。")

# 1. 輸入里程津貼
total_allowance = st.number_input("請輸入本月「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票區域
uploaded_files = st.file_uploader("請上傳加油發票 (支援 PDF, JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

def extract_invoice_data(text):
    """無視排版的『數字池 (Number Pool)』校驗法"""
    # 清除雜訊
    text_clean = text.replace(" ", "").replace(",", "").replace("元", "").replace("ㄦ", "")
    
    amounts_list = []
    taxes_list =[]
    details_list =[]
    
    # 【超級核心】：將畫面上「所有」的數字抓出來，丟進數字池
    all_numbers =[int(x) for x in re.findall(r'\d+', text_clean)]
    num_counts = Counter(all_numbers) # 計算每個數字出現的次數
    
    # 假設合理的發票總計在 50 ~ 50000 之間
    potential_totals =[n for n in all_numbers if 50 <= n <= 50000]
    potential_totals.sort(reverse=True) # 從大金額開始核對
    
    for C in potential_totals:
        if num_counts[C] <= 0:
            continue # 這個數字已經被用掉了
            
        # 計算這筆總計「應有」的稅額 (台灣營業稅 5%)
        expected_tax_exact = C - (C / 1.05)
        
        # 容許 1 元的進位誤差 (四捨五入、無條件進位/捨去)
        possible_taxes = list(set([math.floor(expected_tax_exact), math.ceil(expected_tax_exact), round(expected_tax_exact)]))
        
        match_found = False
        for B in possible_taxes:
            if match_found: break
            A = C - B # 推算出應有的銷售額
            
            # 模擬從池子裡拿出 A, B, C 這三個數字
            temp_counts = num_counts.copy()
            temp_counts[C] -= 1
            
            # 如果池子裡同時存在對應的 A(銷售額) 跟 B(稅額)，這就是一張發票！
            if temp_counts.get(A, 0) > 0:
                temp_counts[A] -= 1
                if temp_counts.get(B, 0) > 0:
                    temp_counts[B] -= 1
                    
                    # 成功拼湊出一張發票！正式消耗掉這三個數字
                    num_counts = temp_counts 
                    amounts_list.append(C)
                    taxes_list.append(B)
                    
                    # 檢查頂部有沒有出現過一模一樣的總計 (雙重確認)
                    if Counter(all_numbers)[C] >= 2:
                        details_list.append(f"✅ **{C}元** (雙重比對成功：找到明細 {A} + {B} = {C}，且頂部總額吻合)")
                    else:
                        details_list.append(f"✅ **{C}元** (比對成功：找到明細 {A} + {B} = {C})")
                        
                    match_found = True

    # 備用防呆：如果稅額真的糊到讀不出來，退回使用中文字抓取
    fallback_matches = re.findall(r'(?:總[計部額]|合計)[:：\.\s]*(\d{3,5})', text_clean)
    for m in fallback_matches:
        val = int(m)
        if 50 <= val <= 50000 and val not in amounts_list:
            tax = val - round(val / 1.05)
            amounts_list.append(val)
            taxes_list.append(tax)
            details_list.append(f"⚠️ **{val}元** (備用機制：僅找到總計字樣，稅額為公式反推)")

    return sum(amounts_list), sum(taxes_list), amounts_list, taxes_list, details_list, text

# 3. 執行按鈕
if st.button("🚀 開始辨識與結算", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
        with st.spinner('啟動智慧數字池引擎辨識中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 處理 PDF 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            pix = page.get_pixmap(dpi=300)
                            image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                            
                            # 加上 config='--psm 11' 強迫 AI 把文字切成一塊一塊看，專治並排排版
                            text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                            amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：精準抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                for detail in details_list:
                                    st.info(detail)
                                total_gas_amount += amount
                                total_tax_amount += tax
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：自動辨識失敗，請確認圖片清晰度。")
                                
                    # 【處理一般圖片檔案】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                        amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                        
                        if amount > 0:
                            st.success(f"📄 圖片 `{file.name}`：精準抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
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
