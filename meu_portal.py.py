import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO PARA FUNDO BRANCO E TEXTO PRETO ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    
    /* Forçar texto a ser visível */
    p, span, label, .stMarkdown { color: #121212 !important; font-weight: 500 !important; }
    h1, h2, h3 { color: var(--gold) !important; }
    
    /* Botão */
    .stButton>button {
        background-color: var(--gold);
        color: white !important;
        border-radius: 8px;
        width: 100%;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #f0f2f6 !important; }
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

@st.cache_data
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        # Procura as colunas de forma mais flexível
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
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return None

# --- LÓGICA ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

# Caminhos das logos (tentando todos os nomes que vimos no seu GitHub)
logos = ["logo_horizontal.png.png", "Logo varias cores versao 21g - 2019.png"]
logo_topo = next((f for f in logos if os.path.exists(f)), None)

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if logo_topo: st.image(logo_topo, use_container_width=True)
        else: st.title("SPAÇO PÉS")
        
        st.write("### Portal do Cliente")
        acesso = limpar_numero(st.text_input("Seu Telefone (com DDD)", type="password"))
        if st.button("ACESSAR"):
            if df_base is not None and len(acesso) >= 8:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados = match
                    st.session_state.logado = True
                    st.rerun()
                else: st.error("Telefone não cadastrado.")
else:
    notas = st.session_state.dados
    st.markdown(f"## Olá, {notas['CLIENTE'].iloc[0]}")
    st.write("Selecione as faturas para gerar o PIX:")
    st.divider()

    sel_val, sel_doc = [], []
    for idx, r in notas.sort_values('VENC').iterrows():
        c1, c2, c3 = st.columns([0.5, 3, 1])
        if c1.checkbox(f"Pagar Nota {r['DOC']}", key=f"c_{idx}"):
            sel_val.append(r['VALOR'])
            sel_doc.append(r['DOC'])
        
        dt_venc = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
        c2.markdown(f"📄 **Nota:** {r['DOC']} | **Vencimento:** {dt_venc}")
        c3.markdown(f"**R$ {r['VALOR']:,.2f}**")
        st.write("---")

    with st.sidebar:
        if logo_topo: st.image(logo_topo, use_container_width=True)
        st.header("Pagamento")
        total = sum(sel_val)
        st.metric("Total", f"R$ {total:,.2f}")
        
        if total > 0:
            # Aqui você pode colocar a sua chave PIX real
            st.write("Escaneie o QR Code abaixo:")
            st.info("Sistema PIX Gerado com Sucesso")
        
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
