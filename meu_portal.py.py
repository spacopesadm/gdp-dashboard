import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS (LIMPEZA DE POPUPS E AJUSTE DE LOGO) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    /* Remove botões de ajuda e popups do Streamlit */
    .stException, .stStatusWidget, button[title="View source"] {display:none !important;}
    
    .stApp { background-color: #FFFFFF !important; }
    
    .footer-fixa {
        position: fixed;
        bottom: 0; left: 0; width: 100%;
        background-color: #ffffff;
        padding: 10px;
        border-top: 3px solid #c5a059;
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 15px;
        box-shadow: 0px -5px 15px rgba(0,0,0,0.1);
    }
    .main-content { margin-bottom: 250px; }
    
    .logo-container {
        text-align: center;
        padding: 20px;
        background-color: #121212;
        margin: -2rem -2rem 2rem -2rem;
    }
    .logo-img {
        max-width: 200px;
        height: auto;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO PIX (SOMA CORRIGIDA) ---
def gerar_pix_estavel(valor, chave, nome="SPACO PES", cidade="GOV VALADARES"):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    
    # Identificador fixo e curto para evitar erro de "chave não encontrada"
    id_fixo = "PORTALSP" 

    payload = f("00", "01") + \
              f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + \
              f("54", f"{valor:.2f}") + \
              f("58", "BR") + \
              f("59", nome[:25]) + \
              f("60", cidade[:15]) + \
              f("62", f("05", id_fixo)) + "6304"
    
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

def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
    try: return float(v)
    except: return 0.0

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_pago = df.columns[7]   # Coluna H
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_conta = df.columns[4]  # Coluna E
        c_comprador = df.columns[24] # Coluna Y
        
        return pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'CONTA': df[c_conta].astype(str),
            'COMPRADOR': df[c_comprador].fillna("N/I"),
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago]
        })
    except: return None

# --- LÓGICA DE INTERFACE ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

# HEADER COM LOGO
# DICA: Substitua o link abaixo pelo link direto da sua imagem (hospedada no GitHub ou Imbb)
LOGO_URL = "https://i.postimg.cc/502WdGsD/logo-horizontal-png.png" 

def exibir_header():
    st.markdown(f'''
        <div class="logo-container">
            <img src="{LOGO_URL}" class="logo-img" alt="SPAÇO PÉS">
        </div>
    ''', unsafe_allow_html=True)

if not st.session_state.logado:
    exibir_header()
    col_l, col_r = st.columns([1, 2])
    with col_r:
        acesso = limpar_numero(st.text_input("Digite seu Telefone", type="password"))
        if st.button("ACESSAR MINHAS CONTAS"):
            if df_base is not None:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados, st.session_state.logado = match, True
                    st.rerun()
else:
    exibir_header()
    dados = st.session_state.dados
    
    # Aba de Parcelas
    pendentes = dados[dados['PAGO'].isna()].sort_values('VENC')
    
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.subheader(f"Olá, {dados['CLIENTE'].iloc[0]}")
    
    sel_v, sel_c = [], []
    for idx, r in pendentes.iterrows():
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.checkbox(f"Nota: {r['CONTA']} | Venc: {r['VENC'].strftime('%d/%m/%Y')}", key=idx):
                sel_v.append(r['VALOR'])
                sel_c.append(r['CONTA'])
            st.markdown(f'<p style="margin-left: 30px; font-size: 13px; color: #666;">👤 Comprador: {r["COMPRADOR"]}</p>', unsafe_allow_html=True)
        col2.write(f"R$ {r['VALOR']:,.2f}")
        st.divider()
    st.markdown('</div>', unsafe_allow_html=True)

    # --- BARRA DE PAGAMENTO FIXA ---
    total = sum(sel_v)
    if total > 0:
        CHAVE_PIX = "09237407000101"
        qr_b64, copia = gerar_pix_estavel(total, CHAVE_PIX)
        
        link_w = f"https://wa.me/553332782113?text=Paguei R$ {total:.2f} (Notas: {', '.join(sel_c)})"

        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="90">
                <div style="text-align: left;">
                    <span style="font-size: 12px; font-weight: bold; color: #121212;">VALOR TOTAL</span><br>
                    <span style="font-size: 24px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button onclick="navigator.clipboard.writeText('{copia}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 14px;">
                        COPIAR PIX
                    </button>
                    <a href="{link_w}" target="_blank" 
                        style="background-color: #25d366; color: white; padding: 12px 20px; border-radius: 5px; text-decoration: none; font-weight: bold; font-size: 14px; text-align: center;">
                        ENVIAR COMPROVANTE
                    </a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.sidebar.button("Sair"):
        st.session_state.logado = False
        st.rerun()
