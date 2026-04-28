import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠", initial_sidebar_state="collapsed")

# --- ESTILO CSS (REMOVE BARRA LATERAL, POPUPS E AJUSTA RODAPÉ) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #FFFFFF !important; }
    
    .footer-fixa {
        position: fixed;
        bottom: 0; left: 0; width: 100%;
        background-color: #ffffff;
        padding: 15px;
        border-top: 3px solid #c5a059;
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 20px;
        box-shadow: 0px -5px 15px rgba(0,0,0,0.1);
    }
    .main-content { margin-bottom: 280px; }
    .logo-container {
        text-align: center;
        padding: 20px;
        background-color: #121212;
        margin: -2rem -2rem 2rem -2rem;
    }
    .logo-img { max-width: 180px; height: auto; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE SEGURANÇA (VALOR E PIX) ---
def formatar_valor_real(valor):
    if pd.isna(valor): return 0.0
    v_str = re.sub(r'\D', '', str(valor))
    if not v_str: return 0.0
    return float(v_str) / 100

def gerar_pix_seguro(valor, chave="pix@spacopes.com.br"):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    
    # Payload padrão BC (Identificador curto para não dar erro)
    payload = f("00", "01") + \
              f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + \
              f("54", f"{valor:.2f}") + \
              f("58", "BR") + \
              f("59", "SPACO PES") + \
              f("60", "GOV VALADARES") + \
              f("62", f("05", "PORTAL")) + "6304"
    
    # Cálculo CRC16
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    
    payload_final = payload + hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    qr = segno.make(payload_final, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=5, border=1)
    return base64.b64encode(buffer.getvalue()).decode(), payload_final

@st.cache_data(ttl=5)
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        c_tel = [c for c in df.columns if 'TEL' in c or 'FONE' in c][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in c for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_pago = df.columns[7] 
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_conta = df.columns[4] 
        c_comprador = df.columns[24] 
        
        df[c_tel] = df[c_tel].astype(str).str.replace(r'\D', '', regex=True)
        
        return pd.DataFrame({
            'TEL': df[c_tel],
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(formatar_valor_real),
            'CONTA': df[c_conta].astype(str),
            'COMPRADOR': df[c_comprador].fillna("N/I"),
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago]
        })
    except: return None

# --- LOGICA DE INTERFACE ---
LOGO_URL = "https://i.postimg.cc/502WdGsD/logo-horizontal-png.png"

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    st.write("### Acesso ao Portal")
    acesso = st.text_input("Seu Telefone", placeholder="Digite apenas números")
    
    if st.button("ENTRAR"):
        df_base = carregar_dados()
        if df_base is not None:
            tel_limpo = re.sub(r'\D', '', acesso)
            match = df_base[df_base['TEL'].str.endswith(tel_limpo[-8:])].copy()
            if not match.empty:
                st.session_state.dados = match
                st.session_state.logado = True
                st.rerun()
            else: st.error("Telefone não encontrado.")
else:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    dados_cli = st.session_state.dados
    pendentes = dados_cli[dados_cli['PAGO'].isna()].sort_values('VENC')
    
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.write(f"#### Olá, {dados_cli['CLIENTE'].iloc[0]}")
    
    sel_v, sel_c = [], []
    
    if pendentes.empty:
        st.success("Nenhuma conta pendente encontrada!")
    else:
        for idx, r in pendentes.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.checkbox(f"Nota: {r['CONTA']} | Venc: {r['VENC'].strftime('%d/%m/%Y')}", key=f"chk_{idx}"):
                    sel_v.append(r['VALOR'])
                    sel_c.append(r['CONTA'])
                st.caption(f"👤 {r['COMPRADOR']}")
            col2.write(f"**R$ {r['VALOR']:,.2f}**")
            st.divider()
