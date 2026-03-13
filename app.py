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
st.write("請上傳加油發票 (支援 PDF 或圖片)，並輸入本月總里程津貼。系統會自動辨識並計算撥款金額。")

# 1. 輸入里程津貼
total_allowance = st.number_input("請輸入本月「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票區域
uploaded_files = st.file_uploader("請上傳加油發票 (支援 PDF, JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

def extract_invoice_data(text):
    """【終極無敵版】絕對數學池演算法：只相信 100% 吻合的台灣法定稅率組合"""
    # 清理所有文字雜訊與換行
    text_clean = text.replace(" ", "").replace(",", "").replace("元", "").replace("ㄦ", "").replace("\n", "")
    
    amounts_list = []
    taxes_list = []
    details_list =[]
    
    # 1. 將畫面上所有的獨立數字抓出來，丟進「數字池」
    all_numbers = [int(m.group()) for m in re.finditer(r'\d+', text_clean)]
    pool = Counter(all_numbers) # 計算每個數字出現的次數
    
    # 將所有可能的總計金額從大排到小 (過濾掉 100 以下的雜亂數字)
    potential_cs = sorted([n for n in all_numbers if 100 <= n <= 50000], reverse=True)
    
    # 【核心】：在數字池中尋找完美的 A + B = C
    for C in potential_cs:
        # 如果這個數字已經被其他發票用掉了，就跳過
        if pool[C] <= 0:
            continue
            
        # 依照台灣營業稅法規，計算絕對稅額 (總計 / 21 傳統四捨五入)
        expected_tax = math.floor(C / 21.0 + 0.5)
        B = expected_tax
        A = C - B
        
        # 暫時從池子裡拿走一個 C，看看能不能配對成功
        pool[C] -= 1
        
        # 奇蹟時刻：如果池子裡剛好有對應的銷售額 A 跟稅額 B
        if pool[A] > 0 and pool[B] > 0:
            # 完美配對！把 A 跟 B 也從池子裡消耗掉
            pool[A] -= 1
            pool[B] -= 1
            
            amounts_list.append(C)
            taxes_list.append(B)
            details_list.append(f"✅ **{C}元** (精準數學比對：銷售額 {A} + 稅額 {B} = 總計 {C})")
        else:
            # 配對失敗 (例如地址206找不到對應的196)，把 C 放回池子裡
            pool[C] += 1
            
    # 【防呆備用】：如果 PDF 是掃描圖檔導致銷售額糊掉，用明確的「總計」關鍵字撈回
    explicit_totals = re.findall(r'(?:總[計部額]|合計|金額)[:：\.\s]*(\d{3,5})', text_clean)
    for t_str in explicit_totals:
        val = int(t_str)
        # 確保不會跟已經算過的發票重複
        if 100 <= val <= 50000 and val not in amounts_list:
            tax = math.floor(val / 21.0 + 0.5)
            amounts_list.append(val)
            taxes_list.append(tax)
            details_list.append(f"⚠️ **{val}元** (關鍵字比對：發現未列入明細的總計 {val})")
            
    return sum(amounts_list), sum(taxes_list), amounts_list, taxes_list, details_list, text

# 3. 執行按鈕
if st.button("🚀 開始智慧結算", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
        with st.spinner('啟動終極數字池解析中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 處理 PDF 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            text = page.get_text("text") # 優先讀取原生 PDF 文字
                            
                            if len(text.strip()) < 50: # 如果是純圖片 PDF 才啟動 OCR
                                pix = page.get_pixmap(dpi=300)
                                image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                                text = pytesseract.image_to_string(image, lang='chi_tra', config='--psm 11')
                                ocr_used = True
                            else:
                                ocr_used = False
                                
                            amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：成功抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                if not ocr_used: st.caption("⚡ 解析模式：原生 PDF 數位解析 (100%精準)")
                                    
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
