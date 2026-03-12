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
    """使用『雙重確認比對法』：底部(銷售額+稅額=總計) + 頂部(總計) 交互印證"""
    # 清除雜訊
    text_clean = text.replace(" ", "").replace(",", "").replace("元", "").replace("ㄦ", "")
    
    amounts_list = []
    taxes_list = []
    details_list =[] # 用來記錄比對成功的詳細過程給使用者看
    used_indices = set()
    
    # 將所有 OCR 抓到的數字全部列出來
    all_numbers =[int(x) for x in re.findall(r'\d+', text_clean)]
    
    # 核心邏輯：在數字串中尋找連續的三個數字 A(銷售額) B(稅額) C(底部總計)
    for i in range(len(all_numbers) - 2):
        if i in used_indices or i+1 in used_indices or i+2 in used_indices:
            continue
            
        n1 = all_numbers[i]   # 疑似銷售額
        n2 = all_numbers[i+1] # 疑似稅額
        n3 = all_numbers[i+2] # 疑似底部總計
        
        # 條件一：底部算式相符 (銷售額 + 稅額 == 總計)
        if n1 + n2 == n3 and 100 <= n3 <= 20000:
            # 條件二：符合台灣 5% 營業稅規則
            expected_tax = n3 - round(n3 / 1.05)
            if abs(n2 - expected_tax) <= 1:
                
                # 🎯 條件三：【多重確認比對】
                # 往回頭找，看看這張發票「頂部」是不是也出現過一模一樣的總計數字
                top_total_found = False
                # 往前尋找最近的 30 個數字
                for j in range(i-1, max(-1, i-30), -1):
                    if all_numbers[j] == n3:
                        top_total_found = True
                        break
                
                # 記錄結果
                amounts_list.append(n3)
                taxes_list.append(n2)
                
                # 根據比對結果，顯示不同的提示
                if top_total_found:
                    details_list.append(f"✅ **{n3}元** (雙重比對成功：頂部相符，且底部明細 {n1} + {n2} = {n3})")
                else:
                    details_list.append(f"⚠️ **{n3}元** (單一比對成功：僅確認底部明細 {n1} + {n2} = {n3})")
                    
                used_indices.update([i, i+1, i+2])
                
    return sum(amounts_list), sum(taxes_list), amounts_list, taxes_list, details_list, text

# 3. 執行按鈕
if st.button("🚀 開始辨識與多重比對", type="primary"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    if not uploaded_files:
        st.warning("⚠️ 請先上傳至少一份發票檔案！")
    else:
        st.write("### 🧾 發票辨識明細")
        
        with st.spinner('啟動多重比對引擎辨識中，請稍候...'):
            for file in uploaded_files:
                try:
                    # 【處理 PDF 檔案】
                    if file.name.lower().endswith('.pdf'):
                        pdf_bytes = file.read()
                        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                        
                        st.markdown(f"**📄 處理 PDF 檔案：`{file.name}` (共 {len(doc)} 頁)**")
                        
                        for page_num in range(len(doc)):
                            page = doc.load_page(page_num)
                            pix = page.get_pixmap(dpi=300) # 高畫質轉換
                            image = Image.frombytes("RGB",[pix.width, pix.height], pix.samples)
                            
                            text = pytesseract.image_to_string(image, lang='chi_tra')
                            amount, tax, amounts_list, taxes_list, details_list, raw_text = extract_invoice_data(text)
                            
                            if amount > 0:
                                st.success(f" - 第 {page_num + 1} 頁：精準抓到 **{len(amounts_list)}** 張發票！本頁總計 **{amount}** 元 / 稅額 **{tax}** 元")
                                # 顯示多重比對的結果
                                for detail in details_list:
                                    st.info(detail)
                                total_gas_amount += amount
                                total_tax_amount += tax
                            else:
                                st.error(f" - 第 {page_num + 1} 頁：自動辨識失敗，可能是圖片不夠清晰或排版特殊。")
                                
                    # 【處理一般圖片檔案】
                    else:
                        image = Image.open(file)
                        text = pytesseract.image_to_string(image, lang='chi_tra')
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
