import streamlit as st
import pandas as pd
import os
import base64
import json
from datetime import date
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

# --- スプレッドシート設定 ---
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/18VfgMTeRiMegmOHAhmsmq41js_LHLJ-3DUlkOQkLVIY/edit?gid=0#gid=0"

def get_ss_client():
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    service_account_info = json.loads(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_url(SPREADSHEET_URL)

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
    header, [data-testid="stHeader"], [data-testid="collapsedControl"] {{ display: none !important; }}

    .stApp {{ background-color: #E3F2FD !important; }}
    .header-box {{ border-bottom: 3px solid #1A237E; padding: 10px 0; margin-bottom: 20px; }}
    .form-title {{ background: #1A237E; color: white; padding: 8px 15px; border-radius: 5px; margin-bottom: 15px; }}
    .stButton>button {{ background-color: #1A237E !important; color: white !important; border-radius: 25px !important; font-weight: bold !important; }}
    
    .summary-box {{
        background-color: #ffffff; padding: 15px; border-radius: 10px;
        border-left: 5px solid #1A237E; margin-top: 10px; margin-bottom: 20px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }}
    .summary-item {{ font-size: 0.8rem; color: #555; }}
    .summary-val {{ font-size: 1.1rem; font-weight: bold; color: #1A237E; }}

    .table-style {{ width: 100%; border-collapse: collapse; background-color: white; border-radius: 5px; table-layout: fixed; }}
    .table-style th {{ background: #1A237E; color: white; padding: 8px 5px; text-align: left; font-size: 0.8rem; }}
    .table-style td {{ border-bottom: 1px solid #eee; padding: 10px 5px; color: #333; font-size: 0.8rem; word-wrap: break-word; }}

    .col-date {{ width: 7% !important; }}
    .col-route {{ width: 30% !important; }}
    .col-dist {{ width: 20% !important; }}
    .col-high {{ width: 20% !important; }}
    .col-total {{ width: 23% !important; }}
</style>
"""
st.markdown(css_code, unsafe_allow_html=True)

# --- データ処理（キャッシュを利用して高速化） ---
@st.cache_data(ttl=60)
def load_data():
    try:
        ss = get_ss_client()
        sheet = ss.worksheet("kotsuhi_data")
        data = sheet.get_all_records()
        if not data: return pd.DataFrame(columns=COLS)
        df = pd.DataFrame(data)
        df["日付"] = pd.to_datetime(df["日付"]).dt.date
        return df.fillna("")
    except: return pd.DataFrame(columns=COLS)

@st.cache_data(ttl=60)
def get_gas_price():
    try:
        ss = get_ss_client()
        conf_sheet = ss.worksheet("config")
        val = conf_sheet.acell('A1').value
        return float(val) if val else 15.0
    except: return 15.0

def load_users():
    users = {}
    if os.path.exists(USER_FILE):
        with open(USER_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 2: users[parts[0]] = parts[1]
    return users

# 定数設定
USER_FILE = "namae.txt"
COLS = ["名前", "日付", "区間", "走行距離", "高速道路料金", "合計金額"]

# 初期ロード
df_all = load_data()
gas_price = get_gas_price()
user_dict = load_users()
ADMIN_PASS = "1234"

# --- 画面構成 ---
is_admin = st.toggle("🛠️ 管理者モード")

if is_admin:
    pwd = st.text_input("管理者パスワード", type="password")
    if pwd == ADMIN_PASS:
        st.markdown('<div class="form-title">⛽ ガソリン単価設定</div>', unsafe_allow_html=True)
        new_gas_price = st.number_input("1kmあたりのガソリン代 (円)", value=gas_price, step=0.1)
        if st.button("単価を更新する"):
            try:
                ss = get_ss_client()
                conf_sheet = ss.worksheet("config")
                conf_sheet.update_acell('A1', new_gas_price)
                st.cache_data.clear() # キャッシュをクリア
                st.success("スプレッドシートの単価を更新しました")
                st.rerun()
            except Exception as e:
                st.error(f"更新失敗: {e}")

        st.markdown('<div class="form-title">📊 交通費全体集計</div>', unsafe_allow_html=True)
        if not df_all.empty:
            df_all['年月'] = df_all['日付'].apply(lambda x: x.strftime('%Y年%m月'))
            target_month = st.selectbox("集計月", sorted(df_all['年月'].unique(), reverse=True))
            admin_df = df_all[df_all['年月'] == target_month].copy()
            st.markdown(f'<div style="margin-bottom:20px; font-weight:bold; color:#1A237E; font-size:1.5rem;">{target_month} 全員合計: {int(admin_df["合計金額"].sum()):,} 円</div>', unsafe_allow_html=True)
            
            user_summary = admin_df.groupby("名前")["合計金額"].sum().reset_index()
            for idx, row in user_summary.iterrows():
                c_sw, c_nm, c_at = st.columns([1, 2, 2])
                with c_sw: show_det = st.toggle("明細", key=f"det_{idx}")
                with c_nm: st.write(f"**{row['名前']}**")
                with c_at: st.write(f"{int(row['合計金額']):,} 円")
                if show_det:
                    u_det = admin_df[admin_df["名前"] == row["名前"]].copy()
                    rows_html = "".join([f"<tr><td>{r['日付'].strftime('%m-%d')}</td><td>{r['区間']}</td><td>{r['走行距離']}km</td><td>{int(r['高速道路料金']):,}円</td><td>{int(r['合計金額']):,}円</td></tr>" for _, r in u_det.iterrows()])
                    st.markdown(f'<table class="table-style"><thead><tr><th class="col-date">日付</th><th class="col-route">区間</th><th class="col-dist">距離</th><th class="col-high">高速</th><th class="col-total">合計</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)
                st.markdown("<hr style='margin:5px 0;'>", unsafe_allow_html=True)
else:
    name_list = list(user_dict.keys())
    selected_user = st.selectbox("申請者を選択", ["選択してください"] + name_list)
    
    if selected_user != "選択してください":
        user_pwd = st.text_input("パスワード", type="password")
        if user_pwd == user_dict.get(selected_user):
            # 表示用年月作成
            df_all['年月'] = df_all['日付'].apply(lambda x: x.strftime('%Y年%m月')) if not df_all.empty else ""
            month_list = sorted(df_all['年月'].unique(), reverse=True) if not df_all.empty else [date.today().strftime('%Y年%m月')]
            selected_month = st.selectbox("表示月", month_list)
            filtered_df = df_all[(df_all['年月'] == selected_month) & (df_all['名前'] == selected_user)].copy() if not df_all.empty else pd.DataFrame(columns=COLS)
            
            st.markdown(f'<div class="form-title">🚗 走行入力 (単価: {gas_price}円/km)</div>', unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                input_date = st.date_input("日付", date.today())
                route = st.text_input("区間", placeholder="事務所〜現場")
            with c2:
                dist_str = st.text_input("走行距離 (km)", placeholder="10.5")
                high_str = st.text_input("高速道路料金 (円)", placeholder="例: 1500")

            def get_clean_float(s):
                try:
                    val = "".join(c for c in s if c.isdigit() or c == '.')
                    return float(val) if val else 0.0
                except: return 0.0

            dist_val = get_clean_float(dist_str)
            highway_val = get_clean_float(high_str)
            auto_total = int((dist_val * gas_price) + highway_val)
            st.markdown(f"**合計計算: {auto_total:,} 円**")

            if st.button("登録する", use_container_width=True):
                if dist_val > 0 or highway_val > 0:
                    try:
                        ss = get_ss_client()
                        sheet = ss.worksheet("kotsuhi_data")
                        new_row = [selected_user, input_date.strftime("%Y/%m/%d"), route, dist_val, highway_val, auto_total]
                        sheet.append_row(new_row)
                        st.cache_data.clear() # キャッシュを消して最新化
                        st.success("登録完了！")
                        st.rerun() # 強制リロード
                    except Exception as e: st.error(f"登録エラー: {e}")

            if not filtered_df.empty:
                st.markdown("---")
                st.write("### 🗓️ 走行明細履歴")
                rows_html = "".join([f"<tr><td>{r['日付'].strftime('%m-%d')}</td><td>{r['区間']}</td><td>{r['走行距離']}km</td><td>{int(r['高速道路料金']):,}円</td><td>{int(r['合計金額']):,}円</td></tr>" for _, r in filtered_df.iterrows()])
                st.markdown(f'<table class="table-style"><thead><tr><th class="col-date">日付</th><th class="col-route">区間</th><th class="col-dist">距離</th><th class="col-high">高速</th><th class="col-total">合計</th></tr></thead><tbody>{rows_html}</tbody></table>', unsafe_allow_html=True)
                
                delete_mode = st.toggle("🗑️ 編集・削除モード")
                if delete_mode:
                    for idx, row in filtered_df.iterrows():
                        cols = st.columns([5, 1])
                        with cols[0]: st.write(f"{row['日付'].strftime('%m-%d')} {row['区間']} {int(row['合計金額']):,}円")
                        with cols[1]:
                            if st.button("🗑️", key=f"del_{idx}"):
                                try:
                                    ss = get_ss_client()
                                    sheet = ss.worksheet("kotsuhi_data")
                                    all_vals = sheet.get_all_values()
                                    target_row = -1
                                    
                                    # 削除対象の特定ロジックを厳密化
                                    search_name = str(row['名前']).strip()
                                    search_date = row['日付'].strftime("%Y/%m/%d")
                                    search_total = str(int(row['合計金額']))
                                    
                                    for i, v in enumerate(all_vals):
                                        if i == 0: continue
                                        if (len(v) >= 6 and 
                                            str(v[0]).strip() == search_name and 
                                            str(v[1]).replace("-", "/") == search_date and 
                                            str(v[5]).replace(",", "").strip() == search_total):
                                                target_row = i + 1
                                                break
                                    
                                    if target_row > 0:
                                        sheet.delete_rows(target_row)
                                        st.cache_data.clear() # 画面を最新にするためにキャッシュクリア
                                        st.rerun()
                                    else:
                                        st.error("一致する行が見つかりません。再起動してください。")
                                except Exception as e: st.error(f"削除エラー: {e}")

components.html("""
<script>
const doc = window.parent.document;
setInterval(() => {
    doc.querySelectorAll('input').forEach(input => {
        if (input.ariaLabel && (input.ariaLabel.includes('距離') || input.ariaLabel.includes('料金'))) {
            input.type = 'number'; input.inputMode = 'numeric';
        }
    });
}, 1000);
</script>""", height=0)
