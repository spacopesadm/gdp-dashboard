import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CUSTOMIZADO (CORES DOURADO E PRETO) ---
st.markdown("""
    <style>
    /* Fundo da página e textos */
    .stApp { background-color: #121212; color: #FFFFFF; }
    
    /* Cor do Dourado Spaço Pés */
    :root { --gold: #c5a059; }

    /* Estilo dos Títulos */
    h1, h2, h3 { color: var(--gold) !important; font-family: 'Segoe UI', sans-serif; }
    
    /* Botões */
    .stButton>button {
        background-color: var(--gold);
        color: black !important;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        width: 100%;
    }
    .stButton>button:hover { background-color: #e2c07d; color: black; }

    /* Checkboxes */
    .stCheckbox { color: var(--gold); }

    /* Barra Lateral */
    section[data-testid="stSidebar"] { background-color: #1a1a1a; border-right: 1px solid #333; }
    
    /* Inputs de texto */
    .stTextInput>div>div>input { background-color: #262626; color: white; border: 1px solid #c5a059; }
    
    /* Divider */
    hr { border: 0.5px solid #333; }
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
        st.image("logo_horizontal.png", use_container_width=True)
    else:
        st.markdown("<h1 style='text-align: center;'>👠 SPAÇO PÉS</h1>", unsafe_allow_html=True)
        
    with st.columns([1, 1.5, 1])[1]:
        st.markdown("<p style='text-align: center; color: #c5a059;'>Acesse seu extrato e pague via PIX</p>", unsafe_allow_html=True)
        acesso = limpar_numero(st.text_input("Digite seu Telefone (DDD + Número)", type="password"))
        if st.button("ENTRAR NO PORTAL"):
            match = df[df['TEL'].str.endswith(acesso[-8:])] if df is not None and len(acesso) >= 8 else None
            if match is not None and not match.empty:
                st.session_state.dados = match
                st.session_state.logado = True
                st.rerun()
            else: st.error("Telefone não localizado.")

# --- ÁREA DO CLIENTE ---
else:
    notas = st.session_state.dados
    
    # Cabeçalho com Nome e Logo icone
    col_logo, col_texto = st.columns([1, 4])
    with col_logo:
        if os.path.exists("logo_icone.png"):
            st.image("logo_icone.png", width=100)
    with col_texto:
        st.title(f"Olá, {notas['CLIENTE'].iloc[0]}")
    
    st.write("Selecione as notas para pagar:")
    st.divider()

    sel_val, sel_doc = [], []
    for idx, r in notas.sort_values('VENC').iterrows():
        c1, c2, c3 = st.columns([0.5, 3, 1])
        if c1.checkbox("Pagar", key=f"c_{idx}"):
            sel_val.append(r['VALOR'])
            sel_doc.append(r['DOC'])
        vencido = r['VENC'].date() < datetime.now().date() if pd.notnull(r['VENC']) else False
        status = "VENCIDO" if vencido else "ABERTO"
        cor_status = "#FF4B4B" if vencido else "#c5a059"
        
        c2.write(f"📄 Nota: {r['DOC']} | Vencimento: {r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else '--'}")
        c3.markdown(f"<span style='color:{cor_status}; font-weight:bold;'>R$ {r['VALOR']:,.2f} ({status})</span>", unsafe_allow_html=True)
        st.divider()

    # --- BARRA LATERAL ---
    with st.sidebar:
        if os.path.exists("logo_horizontal.png"):
            st.image("logo_horizontal.png", use_container_width=True)
        
        st.header("Pagamento")
        total = sum(sel_val)
        st.metric("Total Selecionado", f"R$ {total:,.2f}")
        
        if total > 0:
            img, copia = gerar_pix_seguro(total, "pix@spacopes.com.br", "SPACO PES", "GOV VALADARES", sel_doc)
            st.image(img, caption="Aponte a câmera do banco")
            with st.expander("Código Copia e Cola"):
                st.code(copia)
        
        st.markdown("---")
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
