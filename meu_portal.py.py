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
    .stButton>button:hover { background-color: #e2c07d; color: black; }
    .stCheckbox { color: var(--gold); }
    section[data-testid="stSidebar"] { background-color: #f8f9fa; border-right: 1px solid #e0e0e0; }
    .stTextInput>div>div>input { background-color: white; color: #121212; border: 1px solid #c5a059; }
    hr { border: 0.5px solid #e0e0e0; }
    </style>
    """, unsafe_allow_html=True)

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
    
    payload = f("00", "01") 
    payload += f("26", f("00", "br.gov.bcb.pix") + f("01", chave))
    payload += "520400005303986" 
    payload += f("54", f"{valor:.2f}")
    payload += "5802BR" 
    payload += f("59", nome[:25])
    payload += f("60", cidade[:15])
    payload += f("62", f("05", txid)) 
    payload += "6304"
    
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
    except:
        return None

if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

# --- TELA DE LOGIN ---
if not st.session_state.logado:
    if os.path.exists("logo_horizontal.png"):
        st.image("logo_horizontal.png", use_container_width=True)
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
                else:
                    st.error("Telefone não localizado.")

# --- ÁREA DO CLIENTE ---
else:
    notas = st.session_state.dados
    col1, col2 = st.columns([1, 4])
    with col1:
        if os.path.exists("logo_icone.png"):
            st.image("logo_icone.png", width=80)
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
        
        data_venc = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else '--'
        c2.markdown(f"📄 Nota: {r['DOC']} | Vencimento: {data_venc}")
        c3.markdown(f"<span style='color:{cor}; font-weight:bold;'>R$ {r['VALOR']:,.2f}</span>", unsafe_allow_html=True)
        st.divider()

    with st.sidebar:
        if os.path.exists("logo_horizontal.png"):
            st.image("logo_horizontal.png", use_container_width=True)
        
        st.header("Resumo")
        total = sum(sel_val)
        st.metric("Total Selecionado", f"R$ {total:,.2f}")
        
        if total > 0:
            img, copia = gerar_pix_seguro(total, "pix@spacopes.com.br", "SPACO PES", "GOV VALADARES", sel_doc)
            st.image(img)
            st.code(copia)
        
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
