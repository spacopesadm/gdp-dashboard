import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    .stApp { background-color: #FFFFFF !important; }
    
    .logo-container {
        text-align: center;
        padding: 20px;
        background-color: #121212;
        margin: -2rem -2rem 2rem -2rem;
        margin-bottom: 20px;
    }
    .logo-img { max-width: 200px; height: auto; }
    
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
    .main-content { margin-bottom: 250px; }
    </style>
    """, unsafe_allow_html=True)

LOGO_URL = "https://i.postimg.cc/502WdGsD/logo-horizontal-png.png"

# --- FUNÇÕES ---
def formatar_valor_real(valor):
    if pd.isna(valor): return 0.0
    v_str = re.sub(r'\D', '', str(valor))
    if not v_str: return 0.0
    return float(v_str) / 100

def gerar_pix(valor):
    chave = "pix@spacopes.com.br"
    def f(id, v): return f"{id}{len(v):02d}{v}"
    payload = f("00", "01") + f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + f("54", f"{valor:.2f}") + \
              f("58", "BR") + f("59", "SPACO PES") + f("60", "GOV VALADARES") + \
              f("62", f("05", "PORTAL")) + "6304"
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    qr = segno.make(payload, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=5)
    return base64.b64encode(buffer.getvalue()).decode(), payload

@st.cache_data(ttl=5)
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        c_tel = [c for c in df.columns if 'TEL' in c or 'FONE' in c][0]
        c_nome = [c for c in df.columns if 'NOME' in c or 'RAZAO' in c][0]
        c_valor = [c for c in df.columns if any(x in c for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_venc = [c for c in df.columns if 'VENC' in c][0]
        c_conta = df.columns[4] 
        c_pago = df.columns[7]  
        c_comp = df.columns[24] 

        base = pd.DataFrame()
        base['TEL_LIMPO'] = df[c_tel].astype(str).str.replace(r'\D', '', regex=True)
        base['CLIENTE'] = df[c_nome]
        base['VALOR_NUM'] = df[c_valor].apply(formatar_valor_real)
        base['CONTA'] = df[c_conta].astype(str)
        base['VENC_ORIGINAL'] = df[c_venc].astype(str)
        base['PAGO'] = df[c_pago]
        base['COMPRADOR'] = df[c_comp].fillna("N/I")
        return base
    except: return None

# --- INTERFACE ---
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    st.write("### 🔑 Acesso ao Portal")
    acesso = st.text_input("Seu Telefone", placeholder="Apenas números")
    if st.button("Consultar"):
        df_base = carregar_dados()
        if df_base is not None:
            tel_digito = re.sub(r'\D', '', acesso)
            match = df_base[df_base['TEL_LIMPO'].str.endswith(tel_digito[-8:])].copy()
            if not match.empty:
                st.session_state.dados_cliente = match
                st.session_state.logado = True
                st.rerun()
            else: st.error("Cadastro não encontrado.")
else:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    dados = st.session_state.dados_cliente
    
    st.subheader(f"Olá, {dados['CLIENTE'].iloc[0]}")
    
    # CRIAÇÃO DAS ABAS
    aba_pendente, aba_pago = st.tabs(["📌 Contas a Pagar", "✅ Histórico de Pagos"])
    
    with aba_pendente:
        pendentes = dados[dados['PAGO'].isna() | (dados['PAGO'].astype(str).str.strip() == "")]
        sel_v, sel_c = [], []
        
        if pendentes.empty:
            st.success("Você não possui faturas pendentes.")
        else:
            st.markdown('<div class="main-content">', unsafe_allow_html=True)
            for idx, r in pendentes.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    if st.checkbox(f"Nota: {r['CONTA']} | Venc: {r['VENC_ORIGINAL']}", key=f"p_{idx}"):
                        sel_v.append(r['VALOR_NUM'])
                        sel_c.append(r['CONTA'])
                col2.write(f"**R$ {r['VALOR_NUM']:,.2f}**")
                st.divider()
            st.markdown('</div>', unsafe_allow_html=True)

    with aba_pago:
        # Mostra o que TEM algo escrito na Coluna H
        pagos = dados[dados['PAGO'].notna() & (dados['PAGO'].astype(str).str.strip() != "")]
        if pagos.empty:
            st.write("Nenhum pagamento registrado ainda.")
        else:
            for idx, r in pagos.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"✅ Nota: {r['CONTA']} (Paga em: {r['PAGO']})")
                col2.write(f"R$ {r['VALOR_NUM']:,.2f}")
                st.divider()

    # --- BARRA DE PIX ---
    total = sum(sel_v)
    if total > 0:
        qr_b64, pix_code = gerar_pix(total)
        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="85">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL SELECIONADO</span><br>
                    <span style="font-size: 22px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <button onclick="navigator.clipboard.writeText('{pix_code}')" 
                    style="background-color: #c5a059; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                    COPIAR PIX
                </button>
            </div>
        """, unsafe_allow_html=True)

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()
