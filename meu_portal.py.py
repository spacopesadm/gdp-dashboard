import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CUSTOMIZADO (BRANCO E DOURADO) ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; color: #121212; }
    :root { --gold: #c5a059; }
    h1, h2, h3 { color: var(--gold) !important; font-family: 'Segoe UI', sans-serif; }
    .stButton>button {
        background-color: var(--gold);
        color: black !important;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        width: 100%;
    }
    .stCheckbox { color: var(--gold); }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).strip().replace('R$', '').replace(' ', '')
    if ',' in v: v = v.replace('.', '').replace(',', '.')
    try:
        val = float(v)
        if val > 5000 and '.' not in str(valor): return val / 100
        return val
    except: return 0.0

def gerar_pix_seguro(valor, chave, nome, cidade, notas_selecionadas):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    docs_limpos = [re.sub(r'\D', '', str(n)) for n in notas_selecionadas]
    txt_notas = "N" + ",".join([n for n in docs_limpos if n])
    txid = re.sub(r'[^A-Z0-9]', '', txt_notas.upper())[:25]
    if not txid: txid = "PORTAL"
    
    payload = f("00", "01") + f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + "520400005303986" + f("54", f"{valor:.2f}") + "5802BR" + f("59", nome[:25]) + f("60", cidade[:15]) + f("62", f("05", txid)) + "6304"
    
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    
    qr = segno.make(payload)
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=10)
    return buffer.getvalue(), payload

@st.cache_data
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_doc = [c for c in df.columns if any(x in str(c) for x in ['NUM', 'DOC', 'NOTA'])][0]
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        return pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce')
        })
    except: return None

# --- INÍCIO DO APP ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

# Lista de possíveis nomes da logo que estão no seu GitHub
arquivos_logo = ["logo_horizontal.png.png", "Logo varias cores versao 21g - 2019.png"]
logo_path = next((f for f in arquivos_logo if os.path.exists(f)), None)

if not st.session_state.logado:
    # Mostra a logo se encontrar algum dos arquivos
    if logo_path:
        st.image(logo_path, use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center;'>👠 SPAÇO PÉS</h1>", unsafe_allow_html=True)
        
    with st.columns([1, 1.5, 1])[1]:
        acesso = limpar_numero(st.text_input("Seu Telefone", type="password"))
        if st.button("ACESSAR MINHAS CONTAS"):
            if df_base is not None and len(acesso) >= 8:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados = match
                    st.session_state.logado = True
                    st.rerun()
                else: st.error("Telefone não localizado.")

else:
    notas = st.session_state.dados
    col1, col2 = st.columns([1, 4])
    with col1:
        # Tenta carregar o ícone redondo se você subir ele com esse nome
        if os.path.exists("Sem título-451.png"):
            st.image("Sem título-451.png", width=80)
    with col2:
        st.title(f"Olá, {notas['CLIENTE'].iloc[0]}")
    
    st.write("Selecione as faturas para pagar:")
    sel_val, sel_doc = [], []
    for idx, r in notas.sort_values('VENC').iterrows():
        c1, c2, c3 = st.columns([0.5, 3, 1])
        if c1.checkbox("Pagar", key=f"c_{idx}"):
            sel_val.append(r['VALOR'])
            sel_doc.append(r['DOC'])
        vencido = r['VENC'].date() < datetime.now().date() if pd.notnull(r['VENC']) else False
        cor = "#FF4B4B" if vencido else "#c5a059"
