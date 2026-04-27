import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CUSTOMIZADO (CORES BRANCO E DOURADO) ---
st.markdown("""
    <style>
    /* Fundo da página e textos principais (Preto para boa leitura no branco) */
    .stApp { background-color: #FFFFFF; color: #121212; }
    
    /* Cor do Dourado Spaço Pés */
    :root { --gold: #c5a059; }

    /* Estilo dos Títulos (Sempre Dourado) */
    h1, h2, h3 { color: var(--gold) !important; font-family: 'Segoe UI', sans-serif; }
    
    /* Botões (Fundo Dourado, Texto Preto) */
    .stButton>button {
        background-color: var(--gold);
        color: black !important;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        width: 100%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); /* Sombra leve */
    }
    .stButton>button:hover { background-color: #e2c07d; color: black; border: none; }

    /* Checkboxes (Dourado) */
    .stCheckbox { color: var(--gold); }
    .stCheckbox [data-testid="stWidgetLabel"] > div { color: #121212 !important; } /* Texto do checkbox preto */

    /* Barra Lateral (Branco Leve ou Gelo para destacar) */
    section[data-testid="stSidebar"] { 
        background-color: #f8f9fa; 
        border-right: 1px solid #e0e0e0; 
    }
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2 { color: var(--gold) !important; }
    
    /* Inputs de texto (Fundo branco, Borda dourada) */
    .stTextInput>div>div>input { 
        background-color: white; 
        color: #121212; 
        border: 1px solid #c5a059; 
    }
    
    /* Divider (Divisor de linha cinza leve) */
    hr { border: 0.5px solid #e0e0e0; }

    /* Status Text */
    .stMarkdown p { color: #121212; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES (MANTIDAS) ---
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
        return pd.DataFrame({'TEL': df[c_tel].apply(limpar_numero), 'CLIENTE': df[c_nom], 'VALOR': df[c_val].apply(tratar_valor_br), 'DOC': df[c_doc], 'VENC': pd.to_datetime(df[c_ven], errors='coerce')})
    except: return None

if 'logado' not in st.session_state: st.session_state.logado = False
df = carregar_dados()

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    # Exibe a logo horizontal no topo se existir
    if os.path.exists("logo_horizontal.png"):
        st.image("logo_horizontal.png", use_container_width=True
