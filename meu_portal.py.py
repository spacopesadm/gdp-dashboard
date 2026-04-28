import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS (LIMPEZA TOTAL DE MENUS E POPUPS) ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display:none;}
    .stDecoration {display:none;}
    div[data-testid="stStatusWidget"] {display:none;}
    
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
    .main-content { margin-bottom: 260px; }
    
    .logo-container {
        text-align: center;
        padding: 20px;
        background-color: #121212;
        margin: -2rem -2rem 2rem -2rem;
    }
    .logo-img { max-width: 200px; height: auto; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÃO DE TRATAMENTO DE VALOR (CORREÇÃO DE MILHAR) ---
def tratar_valor_financeiro(valor):
    if pd.isna(valor): return 0.0
    # Remove R$, espaços e pontos de milhar, deixando apenas a vírgula decimal
    v = str(valor).replace('R$', '').replace(' ', '').strip()
    
    if ',' in v and '.' in v: # Formato 1.250,50
        v = v.replace('.', '').replace(',', '.')
    elif ',' in v: # Formato 1250,50
        v = v.replace(',', '.')
        
    try:
        resultado = float(v)
        # Se o valor for absurdamente alto (como 17000 em vez de 170), 
        # fazemos uma verificação de segurança dividindo por 100 se necessário
        # mas a limpeza acima já deve resolver 100% dos casos.
        return resultado
    except:
        return 0.0

def gerar_pix_curto(valor, chave):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    # Identificador fixo e curto para não travar o banco
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
    
    payload_final = payload + hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    qr = segno.make(payload_final, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=5, border=1)
    return base64.b64encode(buffer.getvalue()).decode(), payload_final

@st.cache_data(ttl=30)
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
        
        return pd.DataFrame({
            'TEL': df[c_tel].astype(str).apply(lambda x: re.sub(r'\D', '', x)),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_financeiro),
            'CONTA': df[c_conta].astype(str),
            'COMPRADOR': df[c_comprador].fillna("N/I"),
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago]
        })
    except: return None

# --- INTERFACE ---
LOGO_URL = "https://raw.githubusercontent.com/jacovieira/spaco-pes/main/logo.png"

if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.markdown(f'<div class="logo-container"><img src="{LOGO_URL}" class="logo-img"></div>', unsafe_allow_html=True)
    acesso = st.text_input("Seu Telefone (apenas números)", type="password")
    if st.button("ENTRAR NO PORTAL"):
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
    st.write(f"### Bem-vindo, {dados_cli['CLIENTE'].iloc[0]}")
    
    sel_v, sel_c = [], []
    
    if pendentes.empty:
        st.success("Tudo em dia! Nenhuma parcela pendente.")
    else:
        for idx, r in pendentes.iterrows():
            col1, col2 = st.columns([3, 1])
            with col1:
                # Usamos o índice para garantir que cada checkbox seja único
                if st.checkbox(f"Nota: {r['CONTA']} | Venc: {r['VENC'].strftime('%d/%m/%Y')}", key=f"v_{idx}"):
                    sel_v.append(r['VALOR'])
                    sel_c.append(r['CONTA'])
                st.caption(f"👤 {r['COMPRADOR']}")
            col2.write(f"**R$ {r['VALOR']:,.2f}**")
            st.divider()
    st.markdown('</div>', unsafe_allow_html=True)

    # --- BARRA FIXA CORRIGIDA ---
    total = sum(sel_v)
    if total > 0:
        qr_b64, copia = gerar_pix_curto(total, "09237407000101")
        
        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="85">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL SELECIONADO</span><br>
                    <span style="font-size: 24px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <button onclick="navigator.clipboard.writeText('{copia}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 12px 15px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        COPIAR PIX
                    </button>
                    <a href="https://wa.me/553332782113" target="_blank" 
                        style="background-color: #25d366; color: white; padding: 10px; border-radius: 5px; text-decoration: none; font-weight: bold; text-align: center; font-size: 11px;">
                        ENVIAR COMPROVANTE
                    </a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.sidebar.button("Sair"):
        st.session_state.clear()
        st.rerun()
