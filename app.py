import streamlit as st
import pandas as pd
import os
import base64
from datetime import date
import streamlit.components.v1 as components

# ページ設定
st.set_page_config(page_title="交通費精算システム", layout="wide")

# --- フォント・CSS設定 ---
def get_base64_font(font_file):
    if os.path.exists(font_file):
        with open(font_file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

font_base64 = get_base64_font("MochiyPopOne-Regular.ttf")

css_code = f"""
<style>
    @font-face {{
        font-family: 'Mochiy Pop One';
        src: url(data:font/ttf;base64,{font_base64}) format('truetype');
    }}
    * {{ font-family: 'Mochiy Pop One', sans-serif !important; }}
    
    header, [data-testid="stHeader"], [data-testid="collapsedControl"] {{
        display: none !important;
        height: 0px !important;
    }}

    .stApp {{ background-color: #E3F2FD !important; }}
    .header-box {{ border-bottom: 3px solid #1A237E; padding: 10px 0; margin-bottom: 20px; }}
    .total-label {{ font-size: 1.1rem; color: #444; margin-bottom: 5px; font-weight: bold; }}
    .total-a {{ font-size: 2.2rem; font-weight: bold; color: #1A237E; margin: 0; }}
    .form-title {{ background: #1A237E; color: white; padding: 8px 15px; border-radius: 5px; margin-bottom: 15px; }}
    .gas-settings {{ background: #f0f2f6; padding: 15px; border-radius: 10px; border: 2px solid #1A237E; margin-bottom: 20px; }}
    .stButton>button {{ background-color: #1A237E !important; color: white !important; border-radius: 25px !important; font-weight: bold !important; }}
    
    .table-style {{ width: 100%; border-collapse: collapse; background-color: white; border-radius: 5px; table-layout: fixed; }}
    .table-style th {{ background: #1A237E; color: white; padding: 8px 5px; text-align: left; font-size: 0.8rem; }}
    .table-style td {{ border-bottom: 1px solid #eee; padding: 10px 5px; color: #333; font-size: 0.8rem; word-wrap: break-word; }}
</style>
"""
st.markdown(css_code, unsafe_allow_html=True)

# --- データ・設定処理 ---
CSV_FILE = "expenses.csv"
CONFIG_FILE = "config.txt"
COLS = ["名前", "日付", "区間", "走行距離", "高速道路料金", "合計金額"]

def load_data():
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if "名前" not in df.columns: df.insert(0, "名前", "石原")
            df["日付"] = pd.to_datetime(df["日付"]).dt.date
            return df.fillna("")
        except: return pd.DataFrame(columns=COLS)
    return pd.DataFrame(columns=COLS)

def get_gas_price():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try: return float(f.read())
            except: return 15.0
    return 15.0

df_all = load_data()
gas_price = get_gas_price()
ADMIN_PASS = "1234"
USER_PASS = "0000"

# --- 画面構成 ---
is_admin = st.toggle("🛠️ 管理者モード")

if is_admin:
    pwd = st.text_input("管理者パスワード", type="password")
    if pwd == ADMIN_PASS:
        # ガソリン単価設定
        st.markdown('<div class="form-title">⛽ ガソリン単価設定</div>', unsafe_allow_html=True)
        st.markdown('<div class="gas-settings">', unsafe_allow_html=True)
        new_gas_price = st.number_input("1kmあたりのガソリン代 (円)", value=gas_price, step=0.1)
        if st.button("単価を更新する"):
            with open(CONFIG_FILE, "w") as f: f.write(str(new_gas_price))
            st.success(f"単価を {new_gas_price}円 に更新しました")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-title">📊 交通費全体集計</div>', unsafe_allow_html=True)
        if not df_all.empty:
            df_all['年月'] = df_all['日付'].apply(lambda x: x.strftime('%Y年%m月'))
            target_month = st.selectbox("集計月", sorted(df_all['年月'].unique(), reverse=True))
            admin_df = df_all[df_all['年月'] == target_month].copy()
            total_admin = admin_df["合計金額"].sum()
            st.markdown(f'<div class="header-box"><p class="total-label">{target_month} 全員合計</p><p class="total-a">{int(total_admin):,} 円</p></div>', unsafe_allow_html=True)
            
            # --- ここから個人別明細表示 (seisan1の機能を移植) ---
            user_summary = admin_df.groupby("名前")["合計金額"].sum().reset_index()
            for idx, row in user_summary.iterrows():
                c_switch, c_name, c_amt = st.columns([1, 2, 2])
                with c_switch:
                    # 個別の明細トグル
                    show_detail = st.toggle("明細", key=f"details_{idx}")
                with c_name:
                    st.write(f"**{row['名前']}**")
                with c_amt:
                    st.write(f"{int(row['合計金額']):,} 円")
                
                if show_detail:
                    u_detail = admin_df[admin_df["名前"] == row["名前"]].copy()
                    rows_html = "".join([f"<tr><td>{r['日付'].strftime('%m-%d')}</td><td>{r['区間']}</td><td>{r['走行距離']}km</td><td>{int(r['高速道路料金']):,}円</td><td>{int(r['合計金額']):,}円</td></tr>" for _, r in u_detail.iterrows()])
                    st.markdown(f'<table class="table-style"><thead><tr><th style="width:55px;">日付</th><th>区間</th><th style="width:15%;">距離</th><th style="width:15%;">高速代</th><th style="width:85px;">合計</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)
                st.markdown("<hr style='margin:5px 0; border:0.5px solid #eee;'>", unsafe_allow_html=True)
            
            csv_data = admin_df.drop(columns=['年月']).to_csv(index=False).encode('utf_8_sig')
            st.download_button(label="📥 CSVダウンロード", data=csv_data, file_name=f"集計_{target_month}.csv")
else:
    # --- 個人申請モード ---
    name_list = ["石原", "斎藤", "中村", "鎌田", "山本大", "山本和", "松山", "乱", "虎", "横井", "大宮"] 
    selected_user = st.selectbox("申請者を選択", ["選択してください"] + name_list)
    
    if selected_user != "選択してください":
        user_pwd = st.text_input("パスワード", type="password")
        if user_pwd == USER_PASS:
            df_all['年月'] = df_all['日付'].apply(lambda x: x.strftime('%Y年%m月')) if not df_all.empty else ""
            month_list = sorted(df_all['年月'].unique(), reverse=True) if not df_all.empty else []
            selected_month = st.selectbox("表示月", month_list) if month_list else ""
            filtered_df = df_all[(df_all['年月'] == selected_month) & (df_all['名前'] == selected_user)].copy() if selected_month else pd.DataFrame(columns=COLS)
            st.markdown(f'<div class="header-box"><p class="total-label">{selected_user} さんの合計</p><p class="total-a">{int(filtered_df["合計金額"].sum()):,} 円</p></div>', unsafe_allow_html=True)

            st.markdown(f'<div class="form-title">🚗 走行データ入力 (単価: {gas_price}円/km)</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                input_date = st.date_input("日付", date.today())
                route = st.text_input("区間", placeholder="例：事務所〜現場")
            with c2:
                dist_str = st.text_input("走行距離 (km)", placeholder="例: 10.5")
                highway_str = st.text_input("高速道路料金 (円)", placeholder="数字のみ", value="0")

            def get_clean_float(s):
                try:
                    val = "".join(c for c in s if c.isdigit() or c == '.')
                    return float(val) if val else 0.0
                except: return 0.0

            dist_val = get_clean_float(dist_str)
            highway_val = get_clean_float(highway_str)
            auto_total = int((dist_val * gas_price) + highway_val)

            st.markdown(f"**合計金額（自動計算）: {auto_total:,} 円**")

            if st.button("登録する", use_container_width=True):
                if dist_val > 0 or highway_val > 0:
                    new_row = pd.DataFrame([[selected_user, input_date, route, dist_val, highway_val, auto_total]], columns=COLS)
                    pd.concat([df_all.drop(columns=['年月'], errors='ignore'), new_row], ignore_index=True).to_csv(CSV_FILE, index=False)
                    st.success("登録完了！")
                    st.rerun()

            if not filtered_df.empty:
                st.markdown("---")
                st.write("### 🗓️ 走行明細履歴")
                delete_mode = st.toggle("🗑️ 編集・削除モード")
                if delete_mode:
                    for idx, row in filtered_df.iterrows():
                        cols = st.columns([5, 1])
                        with cols[0]: st.write(f"【{row['日付'].strftime('%m-%d')}】 {row['区間']} / {int(row['合計金額']):,}円")
                        with cols[1]:
                            if st.button("🗑️", key=f"del_{idx}"):
                                df_all.drop(idx).drop(columns=['年月'], errors='ignore').to_csv(CSV_FILE, index=False)
                                st.rerun()
                else:
                    rows_html = "".join([f"<tr><td>{r['日付'].strftime('%m-%d')}</td><td>{r['区間']}</td><td>{r['走行距離']}km</td><td>{int(r['高速道路料金']):,}円</td><td>{int(r['合計金額']):,}円</td></tr>" for _, r in filtered_df.iterrows()])
                    st.markdown(f'<table class="table-style"><thead><tr><th>日付</th><th>区間</th><th>距離</th><th>高速代</th><th>合計</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)

# JavaScript (テンキー対応)
components.html("""
    <script>
    const doc = window.parent.document;
    setInterval(() => {
        const inputs = doc.querySelectorAll('input');
        inputs.forEach(input => {
            if (input.ariaLabel && (input.ariaLabel.includes('距離') || input.ariaLabel.includes('料金'))) {
                input.type = 'number'; input.inputMode = 'numeric';
            }
        });
    }, 1000);
    </script>
""", height=0)
