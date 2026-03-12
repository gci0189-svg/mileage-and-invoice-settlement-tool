import streamlit as st
import math
import re
import pytesseract
from PIL import Image

# --- Windows 用戶請注意 ---
# 如果您是 Windows，請把下面這行的註解(#)拿掉，並確認路徑正確
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# -------------------------

st.set_page_config(page_title="🚗 公司里程津貼與發票結算工具", page_icon="🧾")

st.title("🚗 里程津貼與加油發票結算工具")
st.write("請上傳加油發票影像，並輸入本月總里程津貼。系統將自動辨識並計算撥款金額。")

# 1. 輸入里程津貼
total_allowance = st.number_input("請輸入「總里程津貼」金額：", min_value=0, value=7119, step=1)

# 2. 上傳發票
uploaded_files = st.file_uploader("請上傳加油發票照片 (支援 JPG, PNG)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("開始辨識與計算"):
    total_gas_amount = 0
    total_tax_amount = 0
    
    st.write("### 🧾 發票辨識明細")
    
    if not uploaded_files:
        st.warning("請先上傳至少一張發票照片！")
    else:
        for file in uploaded_files:
            try:
                # 讀取圖片
                image = Image.open(file)
                # 進行繁體中文 OCR 辨識
                text = pytesseract.image_to_string(image, lang='chi_tra')
                
                # 使用正則表達式尋找「總計」與「稅額」旁邊的數字
                # 這邊的規則可以根據您發票的實際排版微調
                amount_match = re.search(r'總\s*計\s*[:：]?\s*(\d+)', text)
                tax_match = re.search(r'稅\s*額\s*[:：]?\s*(\d+)', text)
                
                amount = int(amount_match.group(1)) if amount_match else 0
                tax = int(tax_match.group(1)) if tax_match else 0
                
                # 如果 OCR 沒抓到，提供手動輸入提示
                if amount == 0:
                    st.error(f"📄 檔案 `{file.name}`：辨識失敗，圖片可能不夠清晰，或排版無法判讀。")
                else:
                    st.success(f"📄 檔案 `{file.name}`：成功辨識！總計 **{amount}** 元 / 稅額 **{tax}** 元")
                    total_gas_amount += amount
                    total_tax_amount += tax
                    
            except Exception as e:
                st.error(f"處理檔案 {file.name} 時發生錯誤：{e}")

        st.divider()
        
        # 3. 結算與公式計算
        st.write("### 📊 本月結算總表")
        col1, col2 = st.columns(2)
        col1.metric(label="發票總加油金額", value=f"{total_gas_amount} 元")
        col2.metric(label="發票總稅額", value=f"{total_tax_amount} 元")
        
        # 計算公式: CEILING((總津貼 - 總加油金額)/7)
        if total_allowance > 0 and total_gas_amount > 0:
            # 確保不會出現負數的計算
            remainder = max(0, total_allowance - total_gas_amount)
            personal_car = math.ceil(remainder / 7)
            
            st.write("---")
            st.write("#### 💡 第一部分：總加油金額")
            st.info(f"**{total_gas_amount}** 元")
            
            st.write("#### 💡 第二部分：總里程津貼扣除加油金額的換算 (Personal Car)")
            st.write(f"計算公式： `無條件進位( ({total_allowance} - {total_gas_amount}) / 7 )`")
            st.success(f"📌 第二部分應撥款金額： **{personal_car}** 元")
