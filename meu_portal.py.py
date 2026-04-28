import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS (LOGO E DESIGN) ---
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

# --- URL DA LOGO ---
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
def carregar_dados_brutos():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Mapeamento dinâmico de colunas
        col_tel = [c for c in df.columns if 'TEL' in c or 'FONE' in c][0]
        col_nome = [c for c in df.columns if 'NOME' in c or 'RAZAO' in c][0]
        col_valor = [c for c in df.columns if any(x in c for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        col_venc = [c for c in df.columns if 'VENC' in c][0]
        col_conta = df.columns[4] # Coluna E
        col_pago = df.columns[7]  # Coluna H
        col_comp = df.columns[24] # Coluna Y

        base = pd.DataFrame()
        base['TEL_LIMPO'] = df[col_tel].astype(str).str.replace(r'\D', '', regex=True)
        base['CLIENTE'] = df[col_nome]
        base['VALOR_NUM'] = df[col_valor].apply(formatar_valor_real)
        base['CONTA'] = df[col_conta].astype(str)
        base['VENC_ORIGINAL'] = df[col_venc].astype(str)
        base['PAGO'] = df[col_pago]
        base['COMPRADOR'] = df[col_comp].fillna("N/I")
        
        return base
    except Exception as e:
        st.error(f"Erro na planilha: {e}")
        return None

# --- INTERFACE ---
if 'logado' not in st.session_state: 
    st.session_state.logado = False

if not st.session_state.logado:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    st.write("### 🔑 Acesso ao Portal")
    acesso = st.text_input("Seu Telefone (com DDD)", placeholder="Apenas números")
    
    if st.button("Consultar Faturas"):
        df_base = carregar_dados_brutos()
        if df_base is not None:
            tel_cliente = re.sub(r'\D', '', acesso)
            # AQUI ESTAVA O ERRO (LINHA 120 CORRIGIDA)
            match = df_base[df_base['TEL_LIMPO'].str.endswith(tel_cliente[-8:])].copy()
            
            if not match.empty:
                st.session_state.dados_cliente = match
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Nenhuma conta encontrada para este número.")
else:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    dados = st.session_state.dados_cliente
    
    # Filtra parcelas onde a Coluna H está vazia
    pendentes = dados[dados['PAGO'].isna() | (dados['PAGO'].astype(str).str.strip() == "")]
    
    st.markdown('<div class="main-content">', unsafe_allow_html=True)
    st.subheader(f"Olá, {dados['CLIENTE'].iloc[0]}")
    
    sel_v, sel_c = [], []
    
    if pendentes.empty:
        st.success("Tudo em dia! Você não possui faturas pendentes.")
    else:
        for idx, r in pendentes.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                label = f"Nota: {r['CONTA']} | Vencimento: {r['VENC_ORIGINAL']}"
                if st.checkbox(label, key=f"c_{idx}"):
                    sel_v.append(r['VALOR_NUM'])
                    sel_c.append(r['CONTA'])
                st.caption(f"👤 Comprador: {r['COMPRADOR']}")
            col2.write(f"**R$ {r['VALOR_NUM']:,.2f}**")
            st.divider()
    st.markdown('</div>', unsafe_allow_html=True)

    # --- BARRA DE PAGAMENTO ---
    total = sum(sel_v)
    if total > 0:
        qr_b64, pix_code = gerar_pix(total)
        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="90">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL SELECIONADO</span><br>
                    <span style="font-size: 24px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <button onclick="navigator.clipboard.writeText('{pix_code}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 12px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        COPIAR PIX
                    </button>
                    <a href="https://wa.me/553332782113" target="_blank" 
                        style="background-color: #25d366; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; font-weight: bold; text-align: center; font-size: 12px;">
                        ENVIAR COMPROVANTE
                    </a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()
