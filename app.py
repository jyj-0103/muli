import streamlit as st
import pandas as pd
import numpy as np
import os
import joblib
import json
import hashlib
import urllib.request
import uuid  # 用于生成动态随机 key 防止密码记忆
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from collections import defaultdict
import xgboost as xgb
import warnings
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error

warnings.filterwarnings('ignore')

# ==================== 1. 页面全局配置 (必须放在最前面) ====================
st.set_page_config(page_title="智能配色系统 Pro", page_icon="🎨", layout="wide")

st.markdown("""
    <style>
    .big-font { font-size: 20px !important; font-weight: bold; color: #1f77b4; }
    .success-text { color: #2ca02c; font-weight: bold; font-size: 16px; margin-bottom: 5px;}
    .warning-text { color: #ff7f0e; font-weight: bold; font-size: 16px; margin-bottom: 5px;}
    .error-text { color: #d62728; font-weight: bold; font-size: 16px; margin-bottom: 5px;}
    </style>
""", unsafe_allow_html=True)

# ==================== 2. 模型路径与下载链接 ====================
MODEL_FILE_PATH = "smart_color_models.pkl"
DATA_FILE_PATH = "processed_2.xlsx"

# ⚠️ 必须把这行替换为你自己 GitHub Releases 里真实存在的下载链接 ⚠️
MODEL_DOWNLOAD_URL = "https://github.com/jyj-0103/muli/releases/download/model2/smart_color_models.pkl"

# ==================== 3. 纯原生：多用户与审核系统 ====================
USER_DB_FILE = "users_db.json"

def hash_password(password):
    """简单的密码加密，防止明文泄露"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """加载本地账号数据库"""
    if not os.path.exists(USER_DB_FILE):
        # 初始化默认超级管理员 admin / 123456
        default_db = {
            "admin": {
                "password": hash_password("123456"),
                "is_admin": True,
                "is_approved": True
            }
        }
        with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_db, f)
        return default_db
    with open(USER_DB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_users(db):
    """保存账号到本地"""
    with open(USER_DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=4)

# 初始化 Session 状态
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["is_admin"] = False

# 生成随机且固定的输入框 Key（每次刷新页面都会变，彻底阻断浏览器记忆密码）
if "pwd_key_login" not in st.session_state:
    st.session_state["pwd_key_login"] = str(uuid.uuid4())
    st.session_state["pwd_key_reg1"] = str(uuid.uuid4())
    st.session_state["pwd_key_reg2"] = str(uuid.uuid4())

def render_auth_page():
    """渲染登录或注册界面"""
    st.markdown("<h1 style='text-align: center;'>🔐 智能配色系统 Pro 内部入口</h1>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.container(border=True):
            users_db = load_users()
            mode_selection = st.radio("请选择操作", ["🔑 账号登录", "📝 申请注册"], horizontal=True, label_visibility="collapsed")
            st.write("")
            
            if mode_selection == "🔑 账号登录":
                user_input = st.text_input("👤 用户名", autocomplete="off")
                # 使用动态 key 和 autocomplete="new-password" 双管齐下防记忆
                pwd_input = st.text_input("🔑 密码", type="password", key=st.session_state["pwd_key_login"], autocomplete="new-password")
                
                if st.button("🚀 登 录", type="primary", use_container_width=True):
                    if not user_input or not pwd_input:
                        st.error("请输入用户名和密码！")
                    elif user_input not in users_db:
                        st.error("❌ 该账号不存在！")
                    elif users_db[user_input]["password"] != hash_password(pwd_input):
                        st.error("❌ 密码错误！")
                    elif not users_db[user_input]["is_approved"]:
                        st.warning("⏳ 您的账号正在等待管理员审核，暂时无法登录。请联系管理员！")
                    else:
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = user_input
                        st.session_state["is_admin"] = users_db[user_input].get("is_admin", False)
                        
                        # 登录成功后重置动态 Key，确保下次退出再登录时输入框依然是全新的
                        st.session_state["pwd_key_login"] = str(uuid.uuid4())
                        
                        st.success("登录成功！正在进入系统...")
                        st.rerun()
            
            else:
                st.info("⚠️ 注册的新账号需要等待管理员后台批准后方可使用。")
                new_user = st.text_input("👤 想要注册的用户名", autocomplete="off")
                new_pwd = st.text_input("🔑 设置密码", type="password", key=st.session_state["pwd_key_reg1"], autocomplete="new-password")
                new_pwd_confirm = st.text_input("🔑 确认密码", type="password", key=st.session_state["pwd_key_reg2"], autocomplete="new-password")
                
                if st.button("📝 提交注册申请", type="primary", use_container_width=True):
                    if not new_user or not new_pwd:
                        st.error("信息填写不完整！")
                    elif new_pwd != new_pwd_confirm:
                        st.error("❌ 两次输入的密码不一致！")
                    elif new_user in users_db:
                        st.error("❌ 该用户名已被注册，请换一个！")
                    else:
                        users_db[new_user] = {
                            "password": hash_password(new_pwd),
                            "is_admin": False,
                            "is_approved": False
                        }
                        save_users(users_db)
                        # 重置注册框 key
                        st.session_state["pwd_key_reg1"] = str(uuid.uuid4())
                        st.session_state["pwd_key_reg2"] = str(uuid.uuid4())
                        st.success(f"🎉 账号 [{new_user}] 注册成功！请等待管理员审批后登录。")

# 拦截：如果未登录，则只显示登录/注册界面并停止运行后续代码
if not st.session_state["logged_in"]:
    render_auth_page()
    st.stop()

# ==================== 4. 辅助函数与模型逻辑 ====================
def safe_float(val):
    if pd.isna(val): return 0.0
    try: return float(val)
    except (ValueError, TypeError): return 0.0

def parse_dict_from_string(s):
    if not s.strip(): return {}
    d = {}
    for item in s.split(','):
        if ':' not in item: continue
        k, v = item.split(':')
        d[k.strip()] = float(v.strip())
    return d

def calc_weighted_error(c1, c2, weights=(1.0, 2.0, 2.0)):
    diff = np.array(c1) - np.array(c2)
    w = np.array(weights)
    return np.sqrt(np.sum((diff * w)**2))

def format_dict(d):
    return str(d) if d else "{}"

def dict_to_dataframe(d, col_name="用量"):
    if not d: return pd.DataFrame(columns=["材料名称", col_name])
    df = pd.DataFrame(list(d.items()), columns=["材料名称", col_name])
    df[col_name] = df[col_name].apply(lambda x: f"{x:g}")
    return df

@st.cache_resource
def get_model_state():
    return {
        'recipes': [], 'base_to_idx': {}, 'n_bases': 0, 'selected_bases': [],
        'add_to_idx': {}, 'n_additives': 0, 'all_additives': [],
        'red_additives': set(), 'blue_additives': set(), 'Y_add': None,
        'color_model': None, 'color_scaler': None, 'additive_model': None,
        'knn': None, 'scaler': None, 'is_loaded': False
    }

ms = get_model_state()

def train_and_save_models():
    try: df = pd.read_excel(DATA_FILE_PATH, sheet_name=0)
    except FileNotFoundError: return False, f"找不到文件: {DATA_FILE_PATH}，请检查路径。"

    base_cols = [(f'底料{i}', f'底料{i}数量') for i in range(1, 11)]
    add_cols = [(f'配料{i}', f'配料{i}数量') for i in range(1, 8)]

    ms['recipes'].clear()
    for _, row in df.iterrows():
        date_val = row['日期']
        if pd.isna(date_val): continue
        date_str = str(int(date_val)) if isinstance(date_val, (int, float)) else str(date_val)
        depth, red_blue, yellow_green = row['深浅'], row['红蓝'], row['黄绿']
        if pd.isna(depth) or pd.isna(red_blue) or pd.isna(yellow_green): continue
        
        bases, additives = {}, {}
        for name_col, qty_col in base_cols:
            name, qty = row[name_col], safe_float(row[qty_col])
            if pd.notna(name) and str(name).strip() not in ('无', ''): bases[str(name).strip()] = qty
        for name_col, qty_col in add_cols:
            name, qty = row[name_col], safe_float(row[qty_col])
            if pd.notna(name) and str(name).strip() not in ('无', ''): additives[str(name).strip()] = qty
                
        ms['recipes'].append({'date': date_str, 'bases': bases, 'additives': additives, 'color': (float(depth), float(red_blue), float(yellow_green))})

    base_count = defaultdict(int)
    for rec in ms['recipes']:
        for b in rec['bases']: base_count[b] += 1
        
    ms['selected_bases'] = [b for b, cnt in base_count.items() if cnt >= 3]
    ms['base_to_idx'] = {b: i for i, b in enumerate(ms['selected_bases'])}
    ms['n_bases'] = len(ms['selected_bases'])

    ms['all_additives'] = sorted(set(a for rec in ms['recipes'] for a in rec['additives']))
    ms['add_to_idx'] = {a: i for i, a in enumerate(ms['all_additives'])}
    ms['n_additives'] = len(ms['all_additives'])

    ms['Y_add'] = np.zeros((len(ms['recipes']), ms['n_additives']))
    for i, rec in enumerate(ms['recipes']):
        for a, qty in rec['additives'].items():
            if a in ms['add_to_idx']: ms['Y_add'][i, ms['add_to_idx'][a]] = qty

    X_color = np.array([rec['color'] for rec in ms['recipes']])

    ms['red_additives'].clear()
    ms['blue_additives'].clear()
    corr_threshold = 0.3
    for a in ms['all_additives']:
        y = ms['Y_add'][:, ms['add_to_idx'][a]]
        if np.sum(y > 0) < 5: continue
        corr, _ = spearmanr(X_color[:, 1], y)
        if not np.isnan(corr):
            if corr > corr_threshold: ms['red_additives'].add(a)
            elif corr < -corr_threshold: ms['blue_additives'].add(a)
            
    median_rb = np.median(X_color[:, 1])
    red_group, blue_group = X_color[:, 1] > median_rb, X_color[:, 1] < median_rb
    
    for a in ms['all_additives']:
        if a in ms['red_additives'] or a in ms['blue_additives']: continue
        y = ms['Y_add'][:, ms['add_to_idx'][a]]
        mean_red = np.mean(y[red_group]) if np.any(red_group) else 0
        mean_blue = np.mean(y[blue_group]) if np.any(blue_group) else 0
        if mean_red > mean_blue + 0.2 and mean_red > 0.1: ms['red_additives'].add(a)
        elif mean_blue > mean_red + 0.2 and mean_blue > 0.1: ms['blue_additives'].add(a)

    def temp_build_color_features(base_dict, add_dict):
        base_abs = np.zeros(ms['n_bases'])
        for b, qty in base_dict.items():
            if b in ms['base_to_idx']: base_abs[ms['base_to_idx'][b]] = qty
        total_base = sum(base_dict.values())
        base_ratio = base_abs / total_base if total_base > 0 else base_abs

        add_abs = np.zeros(ms['n_additives'])
        for a, qty in add_dict.items():
            if a in ms['add_to_idx']: add_abs[ms['add_to_idx'][a]] = qty
        total_add = sum(add_dict.values())
        add_ratio = add_abs / total_add if total_add > 0 else add_abs
        
        add_concentration = add_abs / (total_base + 1e-4)
        total_concentration = total_add / (total_base + 1e-4)
        n_base_types = np.sum(base_abs > 0)
        n_add_types = np.sum(add_abs > 0)
        red_sum = sum(add_abs[ms['add_to_idx'][a]] for a in ms['red_additives'] if a in ms['add_to_idx'])
        blue_sum = sum(add_abs[ms['add_to_idx'][a]] for a in ms['blue_additives'] if a in ms['add_to_idx'])

        return np.concatenate([base_abs, base_ratio, add_abs, add_ratio, add_concentration, [total_base, total_add, total_concentration, n_base_types, n_add_types, red_sum, blue_sum]])

    Z_color = np.array([temp_build_color_features(rec['bases'], rec['additives']) for rec in ms['recipes']])
    Y_color_arr = np.array([rec['color'] for rec in ms['recipes']])

    ms['color_scaler'] = StandardScaler()
    Y_color_scaled = ms['color_scaler'].fit_transform(Y_color_arr)

    xgb_color = xgb.XGBRegressor(n_estimators=1200, max_depth=10, learning_rate=0.015, subsample=0.8, colsample_bytree=0.8, min_child_weight=1, reg_lambda=1.0, random_state=42, n_jobs=-1)
    ms['color_model'] = MultiOutputRegressor(xgb_color)
    ms['color_model'].fit(Z_color, Y_color_scaled)

    X_base_abs, X_base_ratio = np.zeros((len(ms['recipes']), ms['n_bases'])), np.zeros((len(ms['recipes']), ms['n_bases']))
    for i, rec in enumerate(ms['recipes']):
        total = sum(rec['bases'].values())
        for b, qty in rec['bases'].items():
            if b in ms['base_to_idx']:
                idx = ms['base_to_idx'][b]
                X_base_abs[i, idx] = qty
                if total > 0: X_base_ratio[i, idx] = qty / total

    X_interaction = np.zeros((len(ms['recipes']), 3 * ms['n_bases']))
    for i in range(len(ms['recipes'])):
        for j in range(ms['n_bases']):
            X_interaction[i, j*3] = X_color[i, 0] * X_base_abs[i, j]
            X_interaction[i, j*3+1] = X_color[i, 1] * X_base_abs[i, j]
            X_interaction[i, j*3+2] = X_color[i, 2] * X_base_abs[i, j]

    total_base_weight = np.sum(X_base_abs, axis=1, keepdims=True)
    n_base_types_arr = np.sum(X_base_abs > 0, axis=1, keepdims=True)

    X_combined = np.hstack([X_color, X_base_abs, X_base_ratio, X_interaction, total_base_weight, n_base_types_arr])
    Y_add_log = np.log1p(ms['Y_add'])
    
    rf_multi = RandomForestRegressor(n_estimators=400, max_depth=15, min_samples_leaf=1, random_state=42, n_jobs=-1)
    ms['additive_model'] = MultiOutputRegressor(rf_multi)
    ms['additive_model'].fit(X_combined, Y_add_log)

    colors = np.array([rec['color'] for rec in ms['recipes']])
    ms['scaler'] = StandardScaler()
    colors_scaled = ms['scaler'].fit_transform(colors)
    ms['knn'] = NearestNeighbors(n_neighbors=3, metric='euclidean')
    ms['knn'].fit(colors_scaled)
    ms['is_loaded'] = True

    model_state = {k: v for k, v in ms.items() if k != 'is_loaded'}
    try:
        joblib.dump(model_state, MODEL_FILE_PATH)
        return True, f"模型训练完成，有效配方: {len(ms['recipes'])} 条，并已保存至 {MODEL_FILE_PATH}"
    except Exception as e: return False, f"模型保存失败: {e}"

def load_models():
    if not os.path.exists(MODEL_FILE_PATH): 
        return False, f"未找到模型文件。请先点击【从云端拉取大模型】下载。"
            
    try:
        model_state = joblib.load(MODEL_FILE_PATH)
        for k, v in model_state.items(): ms[k] = v
        ms['is_loaded'] = True
        return True, f"模型加载成功！共载入 {len(ms['recipes'])} 条历史配方。"
    except Exception as e: return False, f"加载模型失败: {e}"

def predict_color(base_dict, add_dict):
    base_abs = np.zeros(ms['n_bases'])
    for b, qty in base_dict.items():
        if b in ms['base_to_idx']: base_abs[ms['base_to_idx'][b]] = qty
    total_base = sum(base_dict.values())
    base_ratio = base_abs / total_base if total_base > 0 else base_abs

    add_abs = np.zeros(ms['n_additives'])
    for a, qty in add_dict.items():
        if a in ms['add_to_idx']: add_abs[ms['add_to_idx'][a]] = qty
    total_add = sum(add_dict.values())
    add_ratio = add_abs / total_add if total_add > 0 else add_abs
    
    add_con = add_abs / (total_base + 1e-4)
    tot_con = total_add / (total_base + 1e-4)
    n_base_t = np.sum(base_abs > 0)
    n_add_t = np.sum(add_abs > 0)
    r_sum = sum(add_abs[ms['add_to_idx'][a]] for a in ms['red_additives'] if a in ms['add_to_idx'])
    b_sum = sum(add_abs[ms['add_to_idx'][a]] for a in ms['blue_additives'] if a in ms['add_to_idx'])

    feat = np.concatenate([base_abs, base_ratio, add_abs, add_ratio, add_con, [total_base, total_add, tot_con, n_base_t, n_add_t, r_sum, b_sum]]).reshape(1, -1)
    pred_scaled = ms['color_model'].predict(feat)[0]
    return ms['color_scaler'].inverse_transform(pred_scaled.reshape(1, -1))[0]

def predict_new_additives(target_color, base_dict, max_additives=5, round_to=3):
    base_vec_abs = np.zeros(ms['n_bases'])
    base_vec_ratio = np.zeros(ms['n_bases'])
    total = sum(base_dict.values())
    n_base = len([q for q in base_dict.values() if q > 0])
    for b, qty in base_dict.items():
        if b in ms['base_to_idx']:
            idx = ms['base_to_idx'][b]
            base_vec_abs[idx] = qty
            if total > 0: base_vec_ratio[idx] = qty / total
            
    inter = np.zeros(3 * ms['n_bases'])
    for j in range(ms['n_bases']):
        inter[j*3] = target_color[0] * base_vec_abs[j]
        inter[j*3+1] = target_color[1] * base_vec_abs[j]
        inter[j*3+2] = target_color[2] * base_vec_abs[j]
        
    input_vec = np.hstack([target_color, base_vec_abs, base_vec_ratio, inter, [total], [n_base]]).reshape(1, -1)
    pred_log = ms['additive_model'].predict(input_vec)[0]
    pred_qty = np.expm1(pred_log)
    add_list = [(add, pred_qty[i]) for i, add in enumerate(ms['all_additives']) if pred_qty[i] > 0]
    add_list.sort(key=lambda x: -x[1])
    return {add: round(qty, round_to) for add, qty in add_list[:max_additives]}

def optimize_additives_high_precision(target_color, base_dict, initial_additives, max_additives=5, allow_type_change=True, lock_types=False, apply_penalty=True):
    current = initial_additives.copy()
    for k in list(current.keys()):
        if current[k] <= 0: current[k] = 0.005
    if len(current) > max_additives and not lock_types:
        current = dict(sorted(current.items(), key=lambda x: -x[1])[:max_additives])

    max_usage = {}
    for a in ms['all_additives']:
        if a in ms['add_to_idx']:
            y_arr = ms['Y_add'][:, ms['add_to_idx'][a]]
            hist_max = np.percentile(y_arr[y_arr > 0], 98) if np.any(y_arr > 0) else 1.0
            max_usage[a] = max(hist_max, current.get(a, 0.0) * 1.5)

    def get_err(d):
        c = predict_color(base_dict, d)
        color_err = calc_weighted_error(c, target_color, weights=(1.0, 2.0, 2.0))
        if apply_penalty:
            deviation_penalty = 0.0
            for k, v in d.items():
                orig = initial_additives.get(k, 0.0)
                deviation_penalty += abs(v - orig) / (orig + 0.1) * 0.15 
            return color_err + deviation_penalty
        return color_err

    def deep_steepest_descent(d):
        temp = d.copy()
        current_e = get_err(temp)
        if apply_penalty:
            step_sizes = [0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001]
        else:
            step_sizes = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001, 0.0005]
        
        for step in step_sizes:
            improved = True
            while improved:
                improved = False
                best_e = current_e
                best_temp = None
                keys = list(temp.keys())
                
                for k in keys:
                    for sign in [1, -1]:
                        new_val = temp[k] + sign * step
                        if 0 <= new_val <= max_usage.get(k, 1.0):
                            test_d = temp.copy()
                            test_d[k] = new_val
                            e = get_err(test_d)
                            if e < best_e - 1e-6:
                                best_e, best_temp = e, test_d

                for i in range(len(keys)):
                    for j in range(i + 1, len(keys)):
                        k1, k2 = keys[i], keys[j]
                        for s1 in [1, -1]:
                            for s2 in [1, -1]:
                                v1, v2 = temp[k1] + s1 * step, temp[k2] + s2 * step
                                if 0 <= v1 <= max_usage.get(k1, 1.0) and 0 <= v2 <= max_usage.get(k2, 1.0):
                                    test_d = temp.copy()
                                    test_d[k1], test_d[k2] = v1, v2
                                    e = get_err(test_d)
                                    if e < best_e - 1e-6:
                                        best_e, best_temp = e, test_d
                                        
                if best_temp is not None:
                    temp = best_temp
                    current_e = best_e
                    improved = True
        return temp, current_e

    best_dict, best_err = deep_steepest_descent(current)

    if allow_type_change and not lock_types:
        struct_improved = True
        while struct_improved:
            struct_improved = False
            for k in list(best_dict.keys()):
                test = best_dict.copy()
                del test[k]
                t_dict, t_err = deep_steepest_descent(test)
                if t_err < best_err - 1e-4:
                    best_dict, best_err = t_dict, t_err
                    struct_improved = True
                    
            if len(best_dict) < max_additives:
                candidates = [a for a in ms['all_additives'] if a not in best_dict and a != '无']
                best_new_a, best_new_err = None, best_err
                for a in candidates:
                    test = best_dict.copy()
                    test[a] = 0.02 
                    e = get_err(test)
                    if e < best_new_err:
                        best_new_err, best_new_a = e, a
                if best_new_a:
                    test = best_dict.copy()
                    test[best_new_a] = 0.02
                    t_dict, t_err = deep_steepest_descent(test)
                    if t_err < best_err - 1e-4:
                        best_dict, best_err = t_dict, t_err
                        struct_improved = True

    final_dict = {}
    for k, v in best_dict.items():
        if lock_types and k in initial_additives:
            final_dict[k] = round(max(0.001, v), 3) 
        elif v >= 0.001:
            final_dict[k] = round(v, 3)

    return final_dict, predict_color(base_dict, final_dict)

def compute_increments(old_dict, new_dict):
    increments = {}
    all_keys = set(old_dict.keys()).union(set(new_dict.keys()))
    for a in all_keys:
        orig = old_dict.get(a, 0.0)
        final = new_dict.get(a, 0.0)
        inc = round(final - orig, 3)
        if inc != 0: increments[a] = inc
    return increments

def recommend_single(target_depth, target_red_blue, target_yellow_green, k=3, color_threshold=6.0):
    target_color = np.array([target_depth, target_red_blue, target_yellow_green])
    target_scaled = ms['scaler'].transform(target_color.reshape(1, -1))
    distances, indices = ms['knn'].kneighbors(target_scaled, n_neighbors=k)
    results = []
    
    for idx in indices[0]:
        rec = ms['recipes'][idx]
        hist_color = np.array(rec['color'])
        color_dist = np.linalg.norm(hist_color - target_color)
        skip_optimization = False

        if color_dist <= color_threshold:
            initial_additives = rec['additives'].copy()
            if len(initial_additives) > 5:
                initial_additives = dict(sorted(initial_additives.items(), key=lambda x: -x[1])[:5])
                
            if not initial_additives:
                init_type = "历史配方无配料（保留原状，无需预测）"
                allow_type_change = False
                skip_optimization = True
            else:
                init_type = "历史相近配方（种类不变，仅微调数量）"
                allow_type_change = False
        else:
            initial_additives = predict_new_additives(target_color, rec['bases'], max_additives=5)
            init_type = "模型预测（可改变种类）"
            allow_type_change = True

        if skip_optimization:
            opt_additives = {}
            opt_color = tuple(hist_color)
            final_error = np.abs(np.array(opt_color) - target_color)
        else:
            opt_additives, opt_color = optimize_additives_high_precision(
                target_color, rec['bases'], initial_additives,
                max_additives=5, allow_type_change=allow_type_change, lock_types=False
            )
            final_error = np.abs(np.array(opt_color) - target_color)
            
        results.append({
            'date': rec['date'],
            'history_bases': rec['bases'],
            'history_additives': rec['additives'],
            'history_color': rec['color'],
            'initial_additives': initial_additives,
            'init_type': init_type,
            'optimized_additives': opt_additives,
            'optimized_color': tuple(opt_color),
            'final_error': final_error,
            'distance': distances[0][list(indices[0]).index(idx)],
            'color_distance': color_dist
        })
    results.sort(key=lambda x: x['color_distance'])
    return results

# ==================== 5. 侧边栏：控制台与模型加载 ====================
with st.sidebar:
    st.success(f"👤 欢迎回来：**{st.session_state['username']}**")
    if st.button("🚪 退出登录", use_container_width=True):
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["is_admin"] = False
        # 退出登录时强制刷新输入框Key
        st.session_state["pwd_key_login"] = str(uuid.uuid4())
        st.rerun()
        
    # ================= 管理员专属控制面板 =================
    if st.session_state["is_admin"]:
        st.markdown("---")
        st.markdown("### 👑 管理员控制台")
        
        # 模块A：账号审核
        with st.container(border=True):
            users_db = load_users()
            pending_users = [u for u, d in users_db.items() if not d.get("is_approved", False)]
            
            if not pending_users:
                st.info("✅ 当前无待审核账号")
            else:
                st.warning(f"🔔 有 {len(pending_users)} 个新账号等待批准")
                for pu in pending_users:
                    col_a, col_b = st.columns([2, 1])
                    with col_a: st.write(f"**{pu}**")
                    with col_b:
                        if st.button("批准", key=f"btn_{pu}", type="primary"):
                            users_db[pu]["is_approved"] = True
                            save_users(users_db)
                            st.rerun()
                            
        # 模块B：模型管理（只有管理员可见）
        st.write("")
        st.markdown("#### ⚙️ AI 模型核心管理")
        with st.container(border=True):
            if st.button("📂 启动/加载本地模型", use_container_width=True):
                with st.spinner("正在加载模型..."):
                    success, msg = load_models()
                    if success: st.success(msg)
                    else: st.error(msg)
            
            st.write("")
            if st.button("📥 从云端强制拉取大模型", type="primary", use_container_width=True):
                with st.spinner("🚀 正在下载 AI 大模型 (约 250MB)，请耐心等待..."):
                    try:
                        urllib.request.urlretrieve(MODEL_DOWNLOAD_URL, MODEL_FILE_PATH)
                        st.success("✅ 云端模型拉取成功！现在可以点击上方的【加载本地模型】了。")
                    except Exception as e:
                        st.error(f"❌ 下载模型失败，请检查链接或仓库权限: {e}")

            st.write("")
            if st.button("🚀 根据本地 Excel 重新训练", type="secondary", use_container_width=True):
                with st.spinner("正在重新训练..."):
                    success, msg = train_and_save_models()
                    if success: st.success(msg)
                    else: st.error(msg)
                            
    # ================= 所有人可见的系统运行状态 =================
    st.markdown("---")
    st.image("https://cdn-icons-png.flaticon.com/512/3003/3003054.png", width=60)
    if ms['is_loaded']:
        st.success("🟢 核心大模型已就绪")
        st.caption("🔥 高精推演引擎运转中，可随时使用。")
    else: 
        st.warning("🔴 模型尚未启动或未部署")

# ==================== 5.5 如果模型未加载，拦截并提示 ====================
if not ms['is_loaded']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    if st.session_state["is_admin"]:
        st.info("👈 **管理员提示：** 当前 AI 模型未处于工作状态。请在左侧侧边栏【AI 模型核心管理】区域点击 **[启动/加载本地模型]**。如果本地缺少模型文件，请先点击 **[从云端强制拉取]**。")
    else:
        st.error("⚠️ **系统拦截：** AI 核心推理模型当前尚未启动加载，系统暂时无法提供配色计算服务。请耐心等待，或联系管理员（admin）登录后台进行模型初始化部署。")
    st.stop() # 阻断下方主界面的渲染

# ==================== 6. 主界面业务 Tabs (模型加载后可见) ====================
tab1, tab2, tab3, tab4 = st.tabs([
    "💡 方案大厅 (智能推荐)", 
    "🔬 调色实验室 (配方微调)", 
    "🪄 全新配方推导 (底料+目标色)", 
    "🔮 色值正向预测 (底料+配料)"
])

# ================= Tab 1: 智能推荐 =================
with tab1:
    st.markdown("### 根据目标颜色寻找并推荐最佳配方")
    with st.container(border=True):
        col1, col2, col3, col4 = st.columns([1,1,1,1])
        with col1: target_d = st.number_input("🌑 深浅目标值", value=49.0, step=0.1, key="t1_d")
        with col2: target_rb = st.number_input("🔴 红蓝目标值", value=6.0, step=0.1, key="t1_rb")
        with col3: target_yg = st.number_input("🟢 黄绿目标值", value=9.0, step=0.1, key="t1_yg")
        with col4:
            st.write("")
            st.write("")
            btn_search = st.button("🔍 开始高精智能推荐", type="primary", use_container_width=True)
    
    if btn_search:
        with st.spinner("正在执行多维计算，逼近极限精度..."):
            results = recommend_single(target_d, target_rb, target_yg, k=3, color_threshold=6.0)
            st.markdown(f"#### 🎯 目标颜色: 深浅=`{target_d:.2f}`, 红蓝=`{target_rb:.2f}`, 黄绿=`{target_yg:.2f}`")
            st.markdown(f"推荐 {len(results)} 个历史底料组合，配料种类 ≤5:\n")
            
            for i, res in enumerate(results, 1):
                with st.container(border=True):
                    st.markdown(f"### 🌟 推荐方案 {i} <span style='font-size: 14px; color: #888;'> (历史颜色距离 = {res['color_distance']:.4f}, KNN距离 = {res['distance']:.4f})</span>", unsafe_allow_html=True)
                    st.write("")
                    
                    rc1, rc2 = st.columns(2)
                    with rc1:
                        st.markdown("<div style='background-color:#f0f2f6; padding:10px; border-radius:5px; margin-bottom:10px;'>📜 <b>历史配方数据 (基准参考)</b></div>", unsafe_allow_html=True)
                        st.caption(f"**日期:** {res['date']}")
                        
                        st.write("**历史底料:**")
                        if res['history_bases']: st.dataframe(dict_to_dataframe(res['history_bases']), hide_index=True, use_container_width=True)
                        else: st.markdown("无")
                        
                        st.write("**历史配料:**")
                        if res['history_additives']: st.dataframe(dict_to_dataframe(res['history_additives']), hide_index=True, use_container_width=True)
                        else: st.markdown("无")
                        
                        st.write("**历史呈现颜色:**")
                        cc1, cc2, cc3 = st.columns(3)
                        cc1.metric("深浅", f"{res['history_color'][0]:.2f}")
                        cc2.metric("红蓝", f"{res['history_color'][1]:.2f}")
                        cc3.metric("黄绿", f"{res['history_color'][2]:.2f}")
                        
                    with rc2:
                        st.markdown("<div style='background-color:#e8f5e9; padding:10px; border-radius:5px; margin-bottom:10px;'>✨ <b>AI 高精度矩阵优化配方 (实际使用)</b></div>", unsafe_allow_html=True)
                        st.caption(f"**初始配料来源:** {res['init_type']}")
                        
                        st.write("**初始配料:**")
                        if res['initial_additives']: st.dataframe(dict_to_dataframe(res['initial_additives']), hide_index=True, use_container_width=True)
                        else: st.markdown("无")
                        
                        st.write("**最终配料 (≤5种):**")
                        if res['optimized_additives']: st.dataframe(dict_to_dataframe(res['optimized_additives'], col_name="AI推荐用量"), hide_index=True, use_container_width=True)
                        else: st.markdown("无")
                        
                        st.write("**优化后预测颜色:**")
                        cc1, cc2, cc3 = st.columns(3)
                        if "无需预测" in res['init_type']:
                            cc1.metric("深浅", f"{res['optimized_color'][0]:.2f}")
                            cc2.metric("红蓝", f"{res['optimized_color'][1]:.2f}")
                            cc3.metric("黄绿", f"{res['optimized_color'][2]:.2f}")
                        else:
                            cc1.metric("深浅", f"{res['optimized_color'][0]:.2f}", f"Δ {res['final_error'][0]:.2f}", delta_color="off")
                            cc2.metric("红蓝", f"{res['optimized_color'][1]:.2f}", f"Δ {res['final_error'][1]:.2f}", delta_color="off")
                            cc3.metric("黄绿", f"{res['optimized_color'][2]:.2f}", f"Δ {res['final_error'][2]:.2f}", delta_color="off")
                st.write("")

# ================= Tab 2: 增量微调 =================
with tab2:
    st.markdown("### 在现有配方基础上进行高精度微调")
    with st.container(border=True):
        base_str = st.text_input("📦 请输入底料 (格式要求: 名称:数量,用逗号隔开)", placeholder="例: 三色:1475, 中灰:525", key="t2_base")
        add_str = st.text_input("🧪 请输入当前已有配料 (格式要求: 名称:数量,用逗号隔开)", placeholder="例: R03:0.15, 304#黄:0.1, 9010:20", key="t2_add")
        
        st.write("🎯 设定目标颜色：")
        col1, col2, col3 = st.columns(3)
        with col1: t_d = st.number_input("目标深浅", value=48.4, step=0.1, key="t2_d")
        with col2: t_rb = st.number_input("目标红蓝", value=5.61, step=0.1, key="t2_rb")
        with col3: t_yg = st.number_input("目标黄绿", value=8.47, step=0.1, key="t2_yg")
        
        btn_opt = st.button("⚡ 极限高精度优化", type="primary", use_container_width=True, key="t2_btn")
    
    if btn_opt:
        if not base_str:
            st.error("底料分布不可为空！")
        else:
            base_dict = parse_dict_from_string(base_str)
            add_dict = parse_dict_from_string(add_str)
            target = (t_d, t_rb, t_yg)
            
            with st.spinner("正在进行对角线联动评估，这可能需要几秒钟时间..."):
                current_color_pred = predict_color(base_dict, add_dict)
                color_diff = np.linalg.norm(np.array(current_color_pred) - np.array(target))
                
                lock_types = False
                if color_diff <= 1.0:
                    st.info(f"🔍 **[评估]** 当前初始配方与目标颜色的色差预测为 **{color_diff:.2f} (≤ 1.0)**\n\n**[策略]** 触发锁定模式：仅在【原配料基础】上微调数量，不引入新配料，不剔除旧配料。")
                    lock_types = True
                else:
                    st.warning(f"🔍 **[评估]** 当前初始配方与目标颜色的色差预测为 **{color_diff:.2f} (> 1.0)**\n\n**[策略]** 允许引入新配料或剔除无效配料，进行全局增量优化。")
                
                best_add, best_color = optimize_additives_high_precision(
                    target, base_dict, add_dict, max_additives=5, allow_type_change=True, lock_types=lock_types
                )
                increments = compute_increments(add_dict, best_add)
                error = np.abs(np.array(best_color) - np.array(target))
                
                st.markdown("---")
                st.markdown("### 🏆 优化结果 (高精矩阵版)")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("最终预测 深浅", f"{best_color[0]:.2f}", f"偏离 {error[0]:.2f}", delta_color="off")
                c2.metric("最终预测 红蓝", f"{best_color[1]:.2f}", f"偏离 {error[1]:.2f}", delta_color="off")
                c3.metric("最终预测 黄绿", f"{best_color[2]:.2f}", f"偏离 {error[2]:.2f}", delta_color="off")
                st.write("")

                rc1, rc2 = st.columns(2)
                with rc1:
                    with st.container(border=True):
                        st.markdown("#### 📝 建议的【最终配料用量】")
                        if not best_add:
                            st.write("无需任何配料")
                        else:
                            st.dataframe(dict_to_dataframe(best_add, col_name="目标克数"), hide_index=True, use_container_width=True)
                            
                        add_str_new = ','.join([f"{k}:{v:g}" for k,v in best_add.items()])
                        st.text_input("🔗 可直接复制的最终配料字符串:", value=add_str_new, key="t2_copy")
                        
                with rc2:
                    with st.container(border=True):
                        st.markdown("#### 🛠 需要【额外操作的动作】")
                        if not increments:
                            st.markdown("<div class='success-text'>🎉 保持当前配料不变</div>", unsafe_allow_html=True)
                        else:
                            for a, inc in increments.items():
                                if inc > 0:
                                    if a not in add_dict:
                                        st.markdown(f"<div class='success-text'>➕ <b>{a}</b>: 增加 {inc:g} (新增配料)</div>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<div class='success-text'>📈 <b>{a}</b>: 增加 {inc:g}</div>", unsafe_allow_html=True)
                                elif inc < 0:
                                    if best_add.get(a, 0) == 0:
                                        st.markdown(f"<div class='error-text'>❌ <b>{a}</b>: 减少 {-inc:g} (完全剔除)</div>", unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"<div class='warning-text'>📉 <b>{a}</b>: 减少 {-inc:g}</div>", unsafe_allow_html=True)

# ================= Tab 3: 全新配方推导 =================
with tab3:
    st.markdown("### 给出已知底料与目标颜色，从零推导所需配料")
    with st.container(border=True):
        base_str3 = st.text_input("📦 请输入底料 (如: 三色:1475, 中灰:525)", placeholder="必填，用逗号隔开", key="t3_base")
        
        st.write("🎯 设定目标颜色：")
        col1, col2, col3 = st.columns(3)
        with col1: t3_d = st.number_input("目标深浅", value=48.4, step=0.1, key="t3_d")
        with col2: t3_rb = st.number_input("目标红蓝", value=5.61, step=0.1, key="t3_rb")
        with col3: t3_yg = st.number_input("目标黄绿", value=8.47, step=0.1, key="t3_yg")
        
        btn_pred_add = st.button("🪄 一键推导极优配料 (深度双向搜索)", type="primary", use_container_width=True, key="t3_btn")
    
    if btn_pred_add:
        if not base_str3:
            st.error("请输入底层材料组合！")
        else:
            base_dict3 = parse_dict_from_string(base_str3)
            target3 = (t3_d, t3_rb, t3_yg)
            
            with st.spinner("系统正在进行双通道并发寻优，无视常识枷锁逼近极致误差..."):
                guess1 = predict_new_additives(target3, base_dict3, max_additives=5)
                res1_add, res1_col = optimize_additives_high_precision(
                    target3, base_dict3, guess1, max_additives=5, allow_type_change=True, lock_types=False, apply_penalty=False
                )
                err1 = calc_weighted_error(res1_col, target3)
                
                res2_add, res2_col = optimize_additives_high_precision(
                    target3, base_dict3, {}, max_additives=5, allow_type_change=True, lock_types=False, apply_penalty=False
                )
                err2 = calc_weighted_error(res2_col, target3)
                
                if err1 <= err2:
                    best_add3, best_color3 = res1_add, res1_col
                else:
                    best_add3, best_color3 = res2_add, res2_col
                    
                error3 = np.abs(np.array(best_color3) - np.array(target3))
                
                st.markdown("---")
                st.markdown("### 🏆 智能极优配料推导结果")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("预测最终 深浅", f"{best_color3[0]:.2f}", f"偏离 {error3[0]:.2f}", delta_color="off")
                c2.metric("预测最终 红蓝", f"{best_color3[1]:.2f}", f"偏离 {error3[1]:.2f}", delta_color="off")
                c3.metric("预测最终 黄绿", f"{best_color3[2]:.2f}", f"偏离 {error3[2]:.2f}", delta_color="off")
                
                st.write("")
                with st.container(border=True):
                    st.markdown("#### ✨ 推荐使用的配料组合 (≤5种)")
                    if not best_add3:
                        st.write("当前底料已非常接近目标颜色，不需要添加任何配料。")
                    else:
                        st.dataframe(dict_to_dataframe(best_add3, col_name="需添加的克数"), hide_index=True, use_container_width=True)
                        add_str_new3 = ','.join([f"{k}:{v:g}" for k,v in best_add3.items()])
                        st.text_input("🔗 复制推导配料代码:", value=add_str_new3, key="t3_copy")

# ================= Tab 4: 色值正向预测 =================
with tab4:
    st.markdown("### 已知底料和配料参数，正向预测它的实际呈现色值")
    with st.container(border=True):
        base_str4 = st.text_input("📦 请输入底料 (如: 三色:1475, 中灰:525)", placeholder="必填，用逗号隔开", key="t4_base")
        add_str4 = st.text_input("🧪 请输入配料 (如: R03:0.15, 9010:20)", placeholder="如果没有配料，可留空", key="t4_add")
        
        btn_pred_color = st.button("🔮 物理反射率正向预测", type="primary", use_container_width=True, key="t4_btn")
        
    if btn_pred_color:
        if not base_str4:
            st.error("底料部分必须填写哦！")
        else:
            base_dict4 = parse_dict_from_string(base_str4)
            add_dict4 = parse_dict_from_string(add_str4)
            
            with st.spinner("AI 神经网络正在运算光照与物理反射率..."):
                pred_col = predict_color(base_dict4, add_dict4)
                
                st.markdown("---")
                st.markdown("### 📊 颜色预测报告")
                st.write("根据您的原材料绝对用量，AI预测该配方干燥后的呈现色值如下：")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("🌑 预测 深浅", f"{pred_col[0]:.3f}")
                c2.metric("🔴 预测 红蓝", f"{pred_col[1]:.3f}")
                c3.metric("🟢 预测 黄绿", f"{pred_col[2]:.3f}")
