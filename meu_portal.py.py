import streamlit as st
import pandas as pd
import re
import io
import segno
import base64
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS PROFISSIONAL (REMOVE POPUPS E MENUS) ---
st.markdown("""
    <style>
    /* Remove barra superior e menus do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    
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
    .main-content { margin-bottom: 200px; }
    p, span, label, div { color: #121212 !important; }
    
    .btn-whats {
        background-color: #25d366;
        color: white !important;
        padding: 10px 15px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: bold;
        font-size: 14px;
        text-align: center;
        display: block;
    }
    .logo-container {
        text-align: center;
        padding: 20px;
        background-color: #121212;
        margin: -2rem -2rem 2rem -2rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES DE APOIO ---
def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).strip().replace('R$', '').replace(' ', '')
    if ',' in v: v = v.replace('.', '').replace(',', '.')
    try: return float(v)
    except: return 0.0

def gerar_pix_seguro(valor, chave, nome, cidade, identificador="PORTAL"):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    id_limpo = re.sub(r'[^A-Z0-9]', '', identificador.upper())[:25]
    payload = f("00", "01") + f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + f("54", f"{valor:.2f}") + \
              f("58", "BR") + f("59", nome[:25]) + f("60", cidade[:15]) + \
              f("62", f("05", id_limpo)) + "6304"
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    qr = segno.make(payload, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=5, border=1)
    return base64.b64encode(buffer.getvalue()).decode(), payload

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Mapeamento dinâmico
        c_tel = [c for c in df.columns if 'TELEFONE' in c or 'FONE' in c][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if 'VALOR' in c or 'PRE' in c or 'VALENTIA' in c][0]
        c_pago = df.columns[7] # Coluna H: Dt.Pagto
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_conta = df.columns[4] # Coluna E: N° Conta

        return pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'CONTA': df[c_conta].astype(str),
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago] # Dt.Pagto
        })
    except: return None

# --- FLUXO DO APLICATIVO ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

if not st.session_state.logado:
    st.markdown('<div class="logo-container"><h1 style="color:#c5a059; margin:0;">SPAÇO PÉS</h1></div>', unsafe_allow_html=True)
    with st.container():
        st.write("### Acesso ao Portal")
        acesso = limpar_numero(st.text_input("Digite seu Telefone (com DDD)", type="password"))
        if st.button("ACESSAR PORTAL"):
            if df_base is not None:
                match = df_base[df_base['TEL'].str.contains(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados, st.session_state.logado = match, True
                    st.rerun()
                else: st.error("Cadastro não encontrado.")
else:
    st.markdown('<div class="logo-container"><h1 style="color:#c5a059; margin:0;">SPAÇO PÉS</h1></div>', unsafe_allow_html=True)
    
    dados = st.session_state.dados
    st.markdown(f"#### Bem-vindo(a), {dados['CLIENTE'].iloc[0]}")
    
    tab1, tab2 = st.tabs(["📌 Contas a Pagar", "✅ Histórico de Pagos"])
    
    with tab1:
        # FILTRO DE BUSCA
        busca = st.text_input("🔍 Filtrar por N° Conta ou Data", placeholder="Ex: 030424")
        
        pendentes = dados[dados['PAGO'].isna()].sort_values('VENC')
        if busca:
            pendentes = pendentes[pendentes['CONTA'].str.contains(busca) | 
                                 pendentes['VENC'].dt.strftime('%d/%m/%Y').str.contains(busca)]

        sel_v, sel_c = [], []
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        
        if pendentes.empty:
            st.info("Nenhuma conta pendente encontrada.")
        else:
            for idx, r in pendentes.iterrows():
                col1, col2 = st.columns([4, 1])
                dt = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
                if col1.checkbox(f"N° CONTA: {r['CONTA']} | Vencimento: {dt}", key=f"p_{idx}"):
                    sel_v.append(r['VALOR'])
                    sel_c.append(r['CONTA'])
                col2.write(f"R$ {r['VALOR']:,.2f}")
                st.divider()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        # Histórico olha para parcelas que têm data na Coluna H (PAGO)
        historico = dados[dados['PAGO'].notna()].sort_values('PAGO', ascending=False)
        if historico.empty:
            st.write("Ainda não constam pagamentos baixados no sistema.")
        else:
            for _, h in historico.iterrows():
                dt_p = pd.to_datetime(h['PAGO']).strftime('%d/%m/%Y')
                st.success(f"CONTA: {h['CONTA']} | Pago em: {dt_p} | Valor: R$ {h['VALOR']:,.2f}")

    # --- BARRA DE PAGAMENTO FIXA ---
    total = sum(sel_v)
    if total > 0:
        CHAVE_PIX = "pix@spacopes.com.br"
        id_banco = f"C{sel_c[0]}"[:25]
        qr_b64, copia = gerar_pix_seguro(total, CHAVE_PIX, "SPACO PES", "GOV VALADARES", id_banco)
        
        lista_c = ", ".join([f"N° CONTA {c}" for c in sel_c])
        msg = f"Olá! Paguei R$ {total:,.2f} referente: {lista_c}. Segue comprovante:"
        link_w = f"https://wa.me/553332782113?text={msg.replace(' ', '%20')}"

        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="80">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL SELECIONADO</span><br>
                    <span style="font-size: 22px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button onclick="navigator.clipboard.writeText('{copia}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 10px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: bold;">
                        COPIAR PIX
                    </button>
                    <a href="{link_w}" target="_blank" class="btn-whats">ENVIAR COMPROVANTE</a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.sidebar.button("Sair do Portal"):
        st.session_state.logado = False
        st.rerun()
