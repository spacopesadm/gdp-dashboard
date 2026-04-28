import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- FORÇAR TEMA CLARO ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    p, span, label, .stMarkdown, div, h1, h2, h3 { color: #121212 !important; }
    .stButton>button { background-color: var(--gold) !important; color: white !important; font-weight: bold; border-radius: 10px; }
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

def gerar_pix_seguro(valor, chave, nome, cidade, identificador="PORTAL"):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    payload = f("00", "01") + f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + f("54", f"{valor:.2f}") + \
              f("58", "BR") + f("59", nome[:25]) + f("60", cidade[:15]) + \
              f("62", f("05", identificador)) + "6304"
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    qr = segno.make(payload, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=15, border=4)
    return buffer.getvalue(), payload

@st.cache_data(ttl=60) 
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_doc = [c for c in df.columns if any(x in str(c) for x in ['NUM', 'DOC', 'NOTA'])][0]
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_pago = [c for c in df.columns if any(x in c for x in ['PAGO', 'PAGTO', 'PAGAMENTO', 'BAIXA'])][0]
        
        res = pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago]
        })
        return res
    except: return None

# --- LOGIN ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### 👠 SPAÇO PÉS - Portal")
        acesso = limpar_numero(st.text_input("Seu Telefone", type="password"))
        if st.button("ACESSAR"):
            if df_base is not None:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados, st.session_state.logado = match, True
                    st.rerun()
                else: st.error("Telefone não localizado.")
else:
    # --- ÁREA DO CLIENTE ---
    notas = st.session_state.dados
    pendentes = notas[notas['PAGO'].isna()].sort_values('VENC')
    
    st.title("💳 Pagamento")
    
    # Criamos os espaços onde o total e o Pix vão aparecer
    container_topo = st.container()
    
    st.divider()
    
    tab1, tab2 = st.tabs(["📌 Contas a Pagar", "✅ Histórico"])
    
    selecionados_valores = []
    selecionados_docs = []
    
    with tab1:
        if pendentes.empty:
            st.success("Tudo em dia!")
        else:
            for idx, r in pendentes.iterrows():
                col_check, col_info, col_valor = st.columns([0.5, 3, 1])
                
                # Regra de cor para vencidos
                hoje = datetime.now().date()
                vencido = r['VENC'].date() < hoje if pd.notnull(r['VENC']) else False
                cor_texto = "red" if vencido else "#121212"
                
                if col_check.checkbox(f"Pagar", key=f"chk_{idx}"): 
                    selecionados_valores.append(r['VALOR'])
                    selecionados_docs.append(str(r['DOC']))
                
                dt_venc = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
                col_info.markdown(f"📄 Nota: {r['DOC']} | Vencimento: <span style='color:{cor_texto}; font-weight:bold;'>{dt_venc}</span>", unsafe_allow_html=True)
                col_valor.write(f"**R$ {r['VALOR']:,.2f}**")
                st.divider()

    with tab2:
        pagas = notas[notas['PAGO'].notna()].sort_values('VENC', ascending=False)
        for _, r in pagas.iterrows():
            ca, cb = st.columns([4, 1])
            ca.write(f"✅ Nota: {r['DOC']} | Pago em: {str(r['PAGO'])[:10]}")
            cb.markdown(f"**R$ {r['VALOR']:,.2f}**")
            st.divider()

    # --- ATUALIZAÇÃO DO TOPO (TOTAL E PIX) ---
    total_geral = sum(selecionados_valores)
    
    with container_topo:
        st.metric("Total das Notas Selecionadas", f"R$ {total_geral:,.2f}")
        
        if total_geral > 0:
            # Identificador para o banco
            id_banco = f"NOTA{selecionados_docs[0]}" if len(selecionados_docs) == 1 else "VARIAS"
            chave_loja = "financeiro@spacopes.com.br"
            
            qr_img, pix_copia = gerar_pix_seguro(total_geral, chave_loja, "SPACO PES", "GOV VALADARES", id_banco)
            
            c_qr, c_txt = st.columns([1, 2])
            c_qr.image(qr_img, width=200, caption="Escaneie para pagar")
            with c_txt:
                st.write("**Pix Copia e Cola:**")
                st.code(pix_copia)
        else:
            st.info("Marque as caixinhas abaixo para gerar o Pix.")

    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
