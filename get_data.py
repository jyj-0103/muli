import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import os

# ==================== 1. 页面配置与样式 ====================
st.set_page_config(page_title="配色数据录入系统", page_icon="📝", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
""", unsafe_allow_html=True)

# 辅助转换函数
def safe_float(val):
    try: return float(val)
    except: return 0.0

# ==================== 2. 全局状态初始化 & 弹窗监控 ====================
# 初始化弹窗状态
if "show_toast" not in st.session_state:
    st.session_state.show_toast = ""
if "show_balloons" not in st.session_state:
    st.session_state.show_balloons = False

# 触发弹窗提醒 (跨越刷新边界)
if st.session_state.show_toast:
    st.toast(st.session_state.show_toast, icon="✅")
    st.session_state.show_toast = ""
if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# 初始化录入区的 Session State (为了实现“选无全无”的联动效果)
for i in range(1, 11):
    if f"new_b_name_{i}" not in st.session_state: st.session_state[f"new_b_name_{i}"] = "无"
    if f"new_b_qty_{i}" not in st.session_state: st.session_state[f"new_b_qty_{i}"] = 0.0
for i in range(1, 8):
    if f"new_a_name_{i}" not in st.session_state: st.session_state[f"new_a_name_{i}"] = "无"
    if f"new_a_qty_{i}" not in st.session_state: st.session_state[f"new_a_qty_{i}"] = 0.0
for key in ["color_depth", "color_rb", "color_yg"]:
    if key not in st.session_state: st.session_state[key] = 0.0

# 清空表单的函数
def clear_form():
    for i in range(1, 11):
        st.session_state[f"new_b_name_{i}"] = "无"
        st.session_state[f"new_b_qty_{i}"] = 0.0
    for i in range(1, 8):
        st.session_state[f"new_a_name_{i}"] = "无"
        st.session_state[f"new_a_qty_{i}"] = 0.0
    st.session_state.color_depth = 0.0
    st.session_state.color_rb = 0.0
    st.session_state.color_yg = 0.0

# 联动逻辑：选“无”后自动把后续清零
def base_change(idx):
    if st.session_state[f"new_b_name_{idx}"] == "无":
        st.session_state[f"new_b_qty_{idx}"] = 0.0
        # 强制后续所有的底料全部变成无和0
        for j in range(idx + 1, 11):
            st.session_state[f"new_b_name_{j}"] = "无"
            st.session_state[f"new_b_qty_{j}"] = 0.0

def add_change(idx):
    if st.session_state[f"new_a_name_{idx}"] == "无":
        st.session_state[f"new_a_qty_{idx}"] = 0.0
        # 强制后续所有的配料全部变成无和0
        for j in range(idx + 1, 8):
            st.session_state[f"new_a_name_{j}"] = "无"
            st.session_state[f"new_a_qty_{j}"] = 0.0

# ==================== 3. 数据库配置与材料字典 ====================
DB_FILE = "records_db.csv"

BASE_MATERIALS = [
    "无", "一白", "一白拉链泡", "一级大红", "三色", "三色涤膜", "中灰", "二白", "二白拉丝", 
    "二白拉链泡", "于三色", "于中灰", "于二白", "于大红", "于灰泡", "于特白", "于粉红", 
    "于花白", "于针织黑", "于黑泡", "兰切片", "兰白片", "冯三色", "冯大红", "吸塑片", 
    "咖啡", "土黄", "土黄长丝", "墨绿", "壬紫红", "大红", "大红拉链泡", "天兰", "好一白", 
    "好三色", "好大红", "好宝兰", "好浅三色", "好浅灰", "好灰泡", "好特白", "好特白长丝", 
    "好特黑", "好白涤膜", "好白长丝", "好紫红", "好芷青", "好金黄", "好黑泡", "好黑长丝", 
    "宝兰", "差天兰", "差宝兰", "广西大红", "广西特黑", "广西紫红", "广西鲜大红", "广西黑", 
    "普大红", "普白", "暗大红", "本白", "杂拉丝泡", "杂片", "李大红", "李紫红", "果绿", 
    "梅红", "梅红涤膜", "棕切片", "油壶切片", "油壶片", "油壶白片", "浅三色", "浅兰切片", 
    "浅宝兰", "浅果绿", "浅灰", "深三色", "深大红", "深灰", "混宝兰", "混遮光", "灰切片", 
    "灰泡", "灰涤膜", "特白", "特白涤膜", "特白长丝", "特级粉红", "特级紫红", "特黑", "白", 
    "白丝泡", "白切片", "白切粒", "白吸塑片", "白块", "白拉链泡", "白摩擦料", "白摩擦片", 
    "白杂切片", "白泡", "白涤膜", "白片", "白长丝", "米白", "米色", "米色涤膜", "米黄切片", 
    "粉红", "粉红涤膜", "紫红", "紫罗兰", "红亮好特白", "红切片", "红拉链丝泡", "红杂片", 
    "红片", "绿切片", "绿包带", "绿吸塑片", "绿泡", "绿片", "绿黄片", "花白", "芷青", 
    "荧光红", "荧光黄", "诸暨三色", "遮光", "金黄", "长丝黑", "陈粉红", "陈紫红", "驼色", 
    "驼色切片", "鲜大红", "黄切片", "黄泡", "黑切片", "黑泡", "黑片", "黑紫红", "黑长丝"
]

ADDITIVE_MATERIALS = [
    "无", "0#黄", "1#橙", "1#黄", "104兰", "10572", "10593", "106#红", "10672", 
    "107#橙", "10732", "108#红", "1080", "109#红", "110#", "114#黄", "115#19", 
    "1160", "1170", "1178", "1180", "12008", "1220", "1240", "1310", "1380", 
    "1470", "1480", "1520", "1560", "1770", "1850", "1880", "1920", "197#", 
    "204", "2170", "2180", "25#橙", "3#兰", "3#黄", "3%兰", "3005", "301", "310", 
    "3310", "3380", "35%兰", "35%黄", "3560", "3660", "3670", "3680", "4#黄", 
    "4580", "5#黄", "5%黑", "503", "503兰", "56345", "5B红", "5B绿", "6#黄", 
    "6203", "6220", "6230", "6260", "6270", "6280", "6970", "7270", "7410", 
    "7603", "7610", "7640", "7680", "7710", "7780", "8#黄", "9001", "9002", 
    "9004", "9010", "9020", "9050", "9060", "9070", "BGS", "CB", "FB", "H01", 
    "H03", "OB-1", "R03", "RL橙", "桃红", "橙R", "紫4", "紫6", "紫7", "紫B", 
    "群青", "钛白粉", "黄棕", "黑母粒"
]

COLUMNS = ["册列", "日期"]
for i in range(1, 11): COLUMNS.extend([f"底料{i}", f"底料{i}数"])
for i in range(1, 8): COLUMNS.extend([f"配料{i}", f"配料{i}数"])
COLUMNS.extend(["深浅", "红蓝", "黄绿"])

def load_data():
    if os.path.exists(DB_FILE):
        df = pd.read_csv(DB_FILE)
        for i in range(1, 11):
            col = f"底料{i}"
            df[col] = df[col].astype(str).str.strip()
            df.loc[~df[col].isin(BASE_MATERIALS), col] = "无"
            df[f"底料{i}数"] = pd.to_numeric(df[f"底料{i}数"], errors='coerce').fillna(0)
            
        for i in range(1, 8):
            col = f"配料{i}"
            df[col] = df[col].astype(str).str.strip()
            df.loc[~df[col].isin(ADDITIVE_MATERIALS), col] = "无"
            df[f"配料{i}数"] = pd.to_numeric(df[f"配料{i}数"], errors='coerce').fillna(0)
            
        for col in ["深浅", "红蓝", "黄绿"]:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    return pd.DataFrame(columns=COLUMNS)

def save_data(df):
    df.to_csv(DB_FILE, index=False, encoding='utf-8-sig')

# ==================== 4. 界面展示 - 动态新增录入 ====================
st.title("📝 实验室配色数据库")

with st.expander("➕ 点击此处展开以【新增录入数据】", expanded=False):
    st.subheader("📌 基础信息")
    c1, c2 = st.columns(2)
    with c1: ce_lie = st.number_input("册列 (批次号)", value=1, step=1)
    with c2: date_val = st.date_input("📅 日期", value=datetime.today(), format="YYYY/MM/DD")

    st.markdown("---")
    st.subheader("📦 底料输入区域 - ⚠️ 严格要求：底料总和必须为 2000")
    col_b1, col_b2 = st.columns(2)
    for i in range(1, 11):
        target_col = col_b1 if i <= 5 else col_b2
        with target_col:
            bc1, bc2 = st.columns([3, 2])
            with bc1: st.selectbox(f"底料 {i}", BASE_MATERIALS, key=f"new_b_name_{i}", on_change=base_change, args=(i,))
            with bc2: st.number_input(f"数量(g)", min_value=0.0, step=10.0, key=f"new_b_qty_{i}")

    st.markdown("---")
    st.subheader("🧪 配料输入区域 (精确至克)")
    col_a1, col_a2 = st.columns(2)
    for i in range(1, 8):
        target_col = col_a1 if i <= 4 else col_a2
        with target_col:
            ac1, ac2 = st.columns([3, 2])
            with ac1: st.selectbox(f"配料 {i}", ADDITIVE_MATERIALS, key=f"new_a_name_{i}", on_change=add_change, args=(i,))
            with ac2: st.number_input(f"数量(g)", min_value=0.0, step=0.01, format="%.3f", key=f"new_a_qty_{i}")

    st.markdown("---")
    st.subheader("🎯 实际呈现颜色值")
    color_col1, color_col2, color_col3 = st.columns(3)
    with color_col1: st.number_input("深浅", step=0.1, key="color_depth")
    with color_col2: st.number_input("红蓝", step=0.1, key="color_rb")
    with color_col3: st.number_input("黄绿", step=0.1, key="color_yg")

    if st.button("✅ 校验并录入当前数据", type="primary", use_container_width=True):
        base_sum = sum(st.session_state[f"new_b_qty_{i}"] for i in range(1, 11) if st.session_state[f"new_b_name_{i}"] != "无")
        
        if abs(base_sum - 2000) > 0.01:
            st.error(f"❌ **错误：底料总和不等于 2000！** 当前总和为 **{base_sum}g**。请向上检查数量并修改后重新提交。")
        else:
            row_dict = {"册列": ce_lie, "日期": date_val.strftime("%Y%m%d")}
            for i in range(1, 11):
                name = st.session_state[f"new_b_name_{i}"]
                row_dict[f"底料{i}"] = name
                row_dict[f"底料{i}数"] = st.session_state[f"new_b_qty_{i}"] if name != "无" else 0.0
            for i in range(1, 8):
                name = st.session_state[f"new_a_name_{i}"]
                row_dict[f"配料{i}"] = name
                row_dict[f"配料{i}数"] = st.session_state[f"new_a_qty_{i}"] if name != "无" else 0.0
            
            row_dict["深浅"] = st.session_state.color_depth
            row_dict["红蓝"] = st.session_state.color_rb
            row_dict["黄绿"] = st.session_state.color_yg

            df = load_data()
            df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
            save_data(df)
            
            # 设置成功弹窗与动画
            st.session_state.show_toast = "数据录入成功！底层库已更新。"
            st.session_state.show_balloons = True
            clear_form()
            st.rerun()

# ==================== 5. 数据面板 - 查、改、删 ====================
st.markdown("---")
st.subheader("📚 历史数据管理库 (支持双击修改与勾选删除)")

current_df = load_data()

if current_df.empty:
    st.warning("📭 数据库当前为空，请先在上方录入数据。")
else:
    st.info("💡 **操作说明**：\n- **自动清空机制**：在表格里修改材料为【无】，保存时它后面的材料会自动全部清空！\n- **修改数据**：直接双击表格修改（材料列已锁定为下拉菜单，无法乱填）。\n- **删除数据**：勾选第一列的 `🗑️ 选中删除`，然后点击红色的【删除选中行】按钮。")
    
    current_df.insert(0, "🗑️ 选中删除", False)

    col_config = {}
    for i in range(1, 11):
        col_config[f"底料{i}"] = st.column_config.SelectboxColumn("底料选项", options=BASE_MATERIALS, required=True)
    for i in range(1, 8):
        col_config[f"配料{i}"] = st.column_config.SelectboxColumn("配料选项", options=ADDITIVE_MATERIALS, required=True)

    edited_df = st.data_editor(
        current_df, 
        use_container_width=True,
        num_rows="fixed", 
        column_config=col_config, 
        hide_index=True,
        height=400
    )
    
    # === 实时监控底料总和 ===
    error_msgs = []
    for idx, row in edited_df.iterrows():
        base_sum = 0.0
        found_none_base = False
        # 实时计算时，遇到无就停止加总（模拟保存后的级联效果）
        for i in range(1, 11):
            mat = str(row.get(f"底料{i}", "无")).strip()
            if found_none_base or mat == "无":
                found_none_base = True
            else:
                base_sum += safe_float(row.get(f"底料{i}数", 0))
        
        if abs(base_sum - 2000) > 0.01:
            error_msgs.append(f"❌ **表格第 {idx+1} 行**：当前的底料总和为 **{base_sum}g**，未达到 2000g。")

    if error_msgs:
        st.error("🚨 **检测到表格中有底料不等于2000的记录！【保存修改】功能已被强制锁定。**")
        for msg in error_msgs: st.warning(msg)
        save_button_disabled = True
    else:
        st.success("✅ 实时检测通过：当前表格内所有数据行的底料总和均严格等于 2000g。")
        save_button_disabled = False

    col_btn1, col_btn2 = st.columns(2)
    
    # ================= 按钮 1：保存修改 =================
    with col_btn1:
        if st.button("💾 确认并保存所有修改", type="primary", disabled=save_button_disabled, use_container_width=True):
            df_to_save = edited_df.drop(columns=["🗑️ 选中删除"])
            
            # === 保存时执行“选中无，后续全无”的数据清洗 ===
            for idx, row in df_to_save.iterrows():
                # 清洗底料
                found_none_base = False
                for i in range(1, 11):
                    if found_none_base or str(row[f"底料{i}"]).strip() == "无":
                        found_none_base = True
                        df_to_save.at[idx, f"底料{i}"] = "无"
                        df_to_save.at[idx, f"底料{i}数"] = 0.0
                    else:
                        df_to_save.at[idx, f"底料{i}数"] = safe_float(row[f"底料{i}数"])
                        
                # 清洗配料
                found_none_add = False
                for i in range(1, 8):
                    if found_none_add or str(row[f"配料{i}"]).strip() == "无":
                        found_none_add = True
                        df_to_save.at[idx, f"配料{i}"] = "无"
                        df_to_save.at[idx, f"配料{i}数"] = 0.0
                    else:
                        df_to_save.at[idx, f"配料{i}数"] = safe_float(row[f"配料{i}数"])

            save_data(df_to_save)
            st.session_state.show_toast = "表格修改已成功应用并保存！"
            st.rerun()

    # ================= 按钮 2：删除选中的行 =================
    with col_btn2:
        if st.button("🚨 删除勾选的行", use_container_width=True):
            rows_to_keep = edited_df[edited_df["🗑️ 选中删除"] == False]
            rows_to_keep = rows_to_keep.drop(columns=["🗑️ 选中删除"])
            
            if len(rows_to_keep) == len(current_df):
                st.warning("⚠️ 您还没有勾选任何需要删除的行！请先在表格最左侧的复选框打勾。")
            else:
                save_data(rows_to_keep)
                st.session_state.show_toast = "选中的数据行已被彻底删除！"
                st.rerun()

    # ==================== 6. 导出 Excel ====================
    st.markdown("---")
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='配色数据')
        return output.getvalue()
    
    export_df = current_df.drop(columns=["🗑️ 选中删除"])
    
    st.download_button(
        label="📥 导出全部数据为 Excel 文件",
        data=to_excel(export_df),
        file_name=f"配方合集_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
