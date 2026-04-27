import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO VISUAL (MANTIDO BRANCO E DOURADO) ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    p, span, label, .stMarkdown { color: #121212 !important; }
    h1, h2, h3 { color: var(--gold) !important; font-family: 'Segoe UI', sans-serif; }
    .stButton>button {
        background-color: var(--gold);
        color: white !important;
        border-radius: 8px;
        font-weight: bold;
        width: 100%;
    }
    section[data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #e0e0e0; }
    /* Estilo das Abas */
    .stTabs [data-baseweb="tab"] { color: #121212; }
    .stTabs [aria-selected="true"] { color: var(--gold) !important; border-bottom-color: var(--gold) !important; }
    </style>
    """, unsafe_allow_html=True)

# --- FUNÇÕES ---
def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).strip().replace('R$', '').replace(' ', '')
    if ',' in v: v = v.replace('.', '').replace(',', '.')
    try: return float(v)
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
        # Procura coluna de status (opcional)
        c_sta = [c for c in df.columns if 'STATUS' in c or 'SITU' in c]
        status_col = c_sta[0] if c_sta else None

        res = pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce')
        })
        if status_col: res['STATUS'] = df[status_col].str.upper().str.strip()
        else: res['STATUS'] = 'ABERTO' # Se não houver coluna, assume aberto
        return res
    except: return None

# --- LÓGICA ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

logos = ["logo_horizontal.png.png", "Logo varias cores versao 21g - 2019.png"]
logo_path = next((f for f in logos if os.path.exists(f)), None)

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if logo_path: st.image(logo_path, use_container_width=True)
        st.write("### Acesso ao Portal")
        acesso = limpar_numero(st.text_input("Seu Telefone", type="password"))
        if st.button("ENTRAR"):
            if df_base is not None and len(acesso) >= 8:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados = match
                    st.session_state.logado = True
                    st.rerun()
                else: st.error("Telefone não encontrado.")
else:
    notas = st.session_state.dados
    st.title(f"Olá, {notas['CLIENTE'].iloc[0]}")
    
    # --- CRIAÇÃO DAS ABAS ---
    aba_pendente, aba_pago = st.tabs(["📌 Contas a Pagar", "✅ Histórico (Pagas)"])

    with aba_pendente:
        # Filtra apenas o que NÃO está pago
        pendentes = notas[notas['STATUS'] != 'PAGA']
        if pendentes.empty:
            st.success("Você não possui contas pendentes no momento!")
            sel_val, sel_doc = [], []
        else:
            st.write("Selecione as faturas para pagar:")
            sel_val, sel_doc = [], []
            for idx, r in pendentes.sort_values('VENC').iterrows():
                c1, c2, c3 = st.columns([0.5, 3, 1])
                if c1.checkbox(f"Nota {r['DOC']}", key=f"c_{idx}"):
                    sel_val.append(r['VALOR'])
                    sel_doc.append(r['DOC'])
                vencido = r['VENC'].date() < datetime.now().date() if pd.notnull(r['VENC']) else False
                status_cor = "red" if vencido else "#c5a059"
                c2.markdown(f"📄 **Vencimento:** {r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else 'S/D'}")
                c3.markdown(f"<span style='color:{status_cor}; font-weight:bold;'>R$ {r['VALOR']:,.2f}</span>", unsafe_allow_html=True)
                st.divider()

    with aba_pago:
        # Filtra apenas o que está pago
        pagas = notas[notas['STATUS'] == 'PAGA']
        if pagas.empty:
            st.info("Nenhuma fatura paga encontrada no histórico.")
        else:
            for idx, r in pagas.sort_values('VENC', ascending=False).iterrows():
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"✅ **Nota:** {r['DOC']} | Pago em: {r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else 'S/D'}")
                c2.markdown(f"<span style='color:green; font-weight:bold;'>R$ {r['VALOR']:,.2f}</span>", unsafe_allow_html=True)
                st.divider()

    with st.sidebar:
        if logo_path: st.image(logo_path, use_container_width=True)
        st.header("Pagamento")
        total = sum(sel_val) if 'sel_val' in locals() else 0
        st.metric("Total Selecionado", f"R$ {total:,.2f}")
        if total > 0:
            img_qr, copia_cola = gerar_pix_seguro(total, "COLOQUE_SEU_PIX_AQUI", "SPAÇO PÉS", "GOV VALADARES", sel_doc)
            st.image(img_qr, use_container_width=True)
            st.code(copia_cola)
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
