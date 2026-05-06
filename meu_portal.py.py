import streamlit as st
import pandas as pd
import re
import io
import segno
import base64
from datetime import datetime

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

LOGO_URL = "https://raw.githubusercontent.com/jacovieira/spaco-pes/main/logo.png"

# --- FUNÇÕES DE CÁLCULO ---
def formatar_valor_real(valor):
    if pd.isna(valor): return 0.0
    try:
        if isinstance(valor, (float, int)) and valor > 0:
            return float(valor) / 100 if valor > 10000 else float(valor)
        v_str = re.sub(r'\D', '', str(valor))
        return float(v_str) / 100 if v_str else 0.0
    except: return 0.0

def calcular_valor_com_juros(valor_original, data_vencimento):
    if pd.isna(data_vencimento):
        return valor_original, 0
    
    hoje = datetime.now().date()
    venc = data_vencimento.date()
    
    if hoje > venc:
        dias_atraso = (hoje - venc).days
        if dias_atraso > 5:
            taxa_juros = (dias_atraso * 0.002)
            valor_final = valor_original * (1 + taxa_juros)
            return valor_final, dias_atraso
            
    return valor_original, 0

def gerar_pix(valor):
    chave = "09237407000101"
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

        base = pd.DataFrame()
        base['TEL_LIMPO'] = df[c_tel].astype(str).str.replace(r'\D', '', regex=True)
        base['CLIENTE'] = df[c_nome]
        base['VALOR_ORIGINAL'] = df[c_valor].apply(formatar_valor_real)
        base['CONTA'] = df[c_conta].astype(str)
        
        # Tratamento de datas para ordenação
        base['VENC_DATA'] = pd.to_datetime(df[c_venc], errors='coerce')
        base['VENC_STR'] = base['VENC_DATA'].dt.strftime('%d/%m/%Y').fillna(df[c_venc].astype(str))
        
        base['PAGO_VALOR'] = df[c_pago]
        # Converte coluna de pagamento para data (se possível) para ordenar o histórico
        base['PAGO_DATA_ORDEM'] = pd.to_datetime(df[c_pago], errors='coerce', dayfirst=True)
        
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
    
    aba_pendente, aba_pago = st.tabs(["📌 Contas a Pagar", "✅ Histórico de Pagos"])
    
    with aba_pendente:
        # Pendentes: Ordenados pelo vencimento mais antigo primeiro
        pendentes = dados[dados['PAGO_VALOR'].isna() | (dados['PAGO_VALOR'].astype(str).str.strip() == "")].sort_values('VENC_DATA')
        sel_v, sel_c = [], []
        
        if pendentes.empty:
            st.success("Você não possui faturas pendentes.")
        else:
            st.markdown('<div class="main-content">', unsafe_allow_html=True)
            for idx, r in pendentes.iterrows():
                valor_atualizado, atraso = calcular_valor_com_juros(r['VALOR_ORIGINAL'], r['VENC_DATA'])
                col1, col2 = st.columns([3, 1])
                with col1:
                    label = f"Nota: {r['CONTA']} | Venc: {r['VENC_STR']}"
                    if atraso > 0: label += f" (Vencida há {atraso} dias)"
                    if st.checkbox(label, key=f"p_{idx}"):
                        sel_v.append(valor_atualizado)
                        sel_c.append(r['CONTA'])
                    if atraso > 0:
                        st.caption(f"⚠️ Original: R$ {r['VALOR_ORIGINAL']:,.2f} + juros de 0,2%/dia")
                col2.write(f"**R$ {valor_atualizado:,.2f}**")
                st.divider()
            st.markdown('</div>', unsafe_allow_html=True)

    with aba_pago:
        # PAGOS: Ordenados pela data de pagamento mais RECENTE primeiro
        pagos = dados[dados['PAGO_VALOR'].notna() & (dados['PAGO_VALOR'].astype(str).str.strip() != "")]
        pagos = pagos.sort_values('PAGO_DATA_ORDEM', ascending=False)
        
        if pagos.empty:
            st.write("Nenhum pagamento registrado.")
        else:
            for idx, r in pagos.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1: st.write(f"✅ Nota: {r['CONTA']} | Pago em: {r['PAGO_VALOR']}")
                col2.write(f"R$ {r['VALOR_ORIGINAL']:,.2f}")
                st.divider()

    # --- BARRA DE PIX E WHATSAPP ---
    total = sum(sel_v)
    if total > 0:
        qr_b64, pix_code = gerar_pix(total)
        msg_w = f"Olá! Paguei R$ {total:,.2f} referente às notas: {', '.join(sel_c)}. Segue comprovante:".replace(' ', '%20')
        link_w = f"https://wa.me/553332782113?text={msg_w}"

        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="85">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL COM JUROS</span><br>
                    <span style="font-size: 22px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <button onclick="navigator.clipboard.writeText('{pix_code}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 10px; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 12px;">
                        COPIAR PIX
                    </button>
                    <a href="{link_w}" target="_blank" 
                        style="background-color: #25d366; color: white; padding: 10px; border-radius: 5px; text-decoration: none; font-weight: bold; text-align: center; font-size: 12px;">
                        ENVIAR COMPROVANTE
                    </a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.button("Sair"):
        st.session_state.clear()
        st.rerun()
