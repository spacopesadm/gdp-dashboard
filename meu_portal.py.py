import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO VISUAL (Dourado Spaço Pés) ---
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    p, span, label, .stMarkdown { color: #121212 !important; font-weight: 500 !important; }
    h1, h2, h3 { color: var(--gold) !important; font-family: 'Segoe UI', sans-serif; }
    .stButton>button { background-color: var(--gold); color: white !important; border-radius: 8px; font-weight: bold; width: 100%; }
    section[data-testid="stSidebar"] { background-color: #f8f9fa !important; border-right: 1px solid #e0e0e0; }
    .stTabs [data-baseweb="tab"] { color: #121212; font-weight: bold; }
    .stTabs [aria-selected="true"] { color: var(--gold) !important; border-bottom-color: var(--gold) !important; }
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
    
    # Payload PIX Estático com Identificador de Nota
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

def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_doc = [c for c in df.columns if any(x in str(c) for x in ['NUM', 'DOC', 'NOTA'])][0]
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_pagto = [c for c in df.columns if any(x in c for x in ['PAGO', 'PAGTO', 'PAGAMENTO', 'BAIXA'])][0]
        
        res = pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pagto]
        })
        return res
    except: return None

# --- LÓGICA PRINCIPAL ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

logos_possiveis = ["logo_horizontal.png.png", "Logo varias cores versao 21g - 2019.png"]
logo_path = next((f for f in logos_possiveis if os.path.exists(f)), None)

if not st.session_state.logado:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if logo_path: st.image(logo_path, use_container_width=True)
        st.write("### Portal do Cliente")
        acesso = limpar_numero(st.text_input("Seu Telefone", type="password"))
        if st.button("ACESSAR"):
            if df_base is not None:
                match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.dados, st.session_state.logado = match, True
                    st.rerun()
                else: st.error("Telefone não localizado.")
else:
    notas = st.session_state.dados
    st.markdown(f"## Olá, {notas['CLIENTE'].iloc[0]}")
    tab1, tab2 = st.tabs(["📌 Contas a Pagar", "✅ Histórico de Pagamentos"])

    with tab1:
        pendentes = notas[notas['PAGO'].isna()].sort_values('VENC')
        sel_val, sel_doc = [], []
        if pendentes.empty:
            st.success("Tudo em dia! Nenhuma conta pendente.")
        else:
            for idx, r in pendentes.iterrows():
                c1, c2, c3 = st.columns([0.5, 3, 1])
                hoje = datetime.now().date()
                vencido = r['VENC'].date() < hoje if pd.notnull(r['VENC']) else False
                cor_venc = "red" if vencido else "#121212"
                
                if c1.checkbox(f"Pagar", key=idx): 
                    sel_val.append(r['VALOR'])
                    sel_doc.append(str(r['DOC']))

                dv = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
                c2.markdown(f"📄 Nota: {r['DOC']} | Vencimento: <span style='color:{cor_venc}; font-weight:bold;'>{dv}</span>", unsafe_allow_html=True)
                c3.write(f"**R$ {r['VALOR']:,.2f}**")
                st.divider()

    with tab2:
        pagas = notas[notas['PAGO'].notna()].sort_values('VENC', ascending=False)
        if pagas.empty:
            st.info("Nenhuma conta paga encontrada no histórico.")
        else:
            for _, r in pagas.iterrows():
                col_a, col_b = st.columns([4, 1])
                col_a.write(f"✅ Nota: {r['DOC']} | Pago em: {str(r['PAGO'])[:10]}")
                col_b.markdown(f"<span style='color:green; font-weight:bold;'>R$ {r['VALOR']:,.2f}</span>", unsafe_allow_html=True)
                st.divider()

    with st.sidebar:
        if logo_path: st.image(logo_path, use_container_width=True)
        st.header("Pagamento")
        total = sum(sel_val)
        
        # Identificador dinâmico para o extrato do banco
        if len(sel_doc) == 1:
            id_pix = f"NOTA{sel_doc[0]}"[:25]
        elif len(sel_doc) > 1:
            id_pix = "VARIAS"
        else:
            id_pix = "PORTAL"

        st.metric("Total Selecionado", f"R$ {total:,.2f}")
        
        if total > 0:
            # TROQUE PELA CHAVE PIX REAL ABAIXO
            chave_real = "financeiro@spacopes.com.br" 
            img_qr, copia = gerar_pix_seguro(total, chave_real, "SPACO PES", "GOV VALADARES", id_pix)
            
            st.markdown('<div style="background-color: white; padding: 15px; border-radius: 10px; display: flex; justify-content: center;">', unsafe_allow_html=True)
            st.image(img_qr, width=220)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.write("**Pix Copia e Cola:**")
            st.code(copia)
        else:
            st.warning("Selecione uma nota acima.")
        
        st.divider()
        if st.button("Sair"):
            st.session_state.logado = False
            st.rerun()
