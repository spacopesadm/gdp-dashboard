import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime
import os

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).strip().replace('R$', '').replace(' ', '')
    if ',' in v: v = v.replace('.', '').replace(',', '.')
    try: return float(v)
    except: return 0.0

def gerar_pix_limpo(valor, chave, nome, cidade):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    
    # Payload sem frescuras para o desenho ficar simples
    payload = f("00", "01")
    payload += f("26", f("00", "br.gov.bcb.pix") + f("01", chave))
    payload += f("52", "0000")
    payload += f("53", "986")
    payload += f("54", f"{valor:.2f}")
    payload += f("58", "BR")
    payload += f("59", nome[:20]) # Nome mais curto reduz quadradinhos
    payload += f("60", cidade[:15])
    payload += f("62", f("05", "***")) # TXID mínimo para simplificar o QR
    payload += "6304"
    
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    
    # Versão 1 (mínima) e Erro 'L' (mais simples de ler)
    qr = segno.make(payload, version=None, error='L')
    buffer = io.BytesIO()
    # Aumentei o scale para 20 para os quadrados ficarem gigantes na tela
    qr.save(buffer, kind='png', scale=20, border=4)
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
        c_pagto = [c for c in df.columns if any(x in c for x in ['PAGO', 'PAGTO', 'PAGAMENTO', 'BAIXA'])][0]
        
        res = pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'ESTA_PAGO': df[c_pagto].notna()
        })
        return res
    except: return None

# --- UI ---
df_base = carregar_dados()
if 'logado' not in st.session_state: st.session_state.logado = False

if not st.session_state.logado:
    st.title("👠 SPAÇO PÉS - Portal")
    acesso = limpar_numero(st.text_input("Telefone:", type="password"))
    if st.button("Entrar"):
        if df_base is not None:
            match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
            if not match.empty:
                st.session_state.dados = match
                st.session_state.logado = True
                st.rerun()
else:
    notas = st.session_state.dados
    tab1, tab2 = st.tabs(["Contas", "Histórico"])
    
    with tab1:
        pendentes = notas[notas['ESTA_PAGO'] == False]
        sel_val = []
        for idx, r in pendentes.iterrows():
            if st.checkbox(f"Nota {r['DOC']} - R$ {r['VALOR']:,.2f}", key=idx):
                sel_val.append(r['VALOR'])
    
    with st.sidebar:
        st.header("Pagamento")
        total = sum(sel_val)
        st.metric("Total", f"R$ {total:,.2f}")
        if total > 0:
            # TROQUE AQUI PELA CHAVE DA LOJA
            img_qr, copia = gerar_pix_limpo(total, "SUA_CHAVE_AQUI", "SPACOPES", "GOV VALADARES")
            
            # Fundo branco reforçado
            st.markdown('<div style="background-color: white; padding: 10px; border-radius: 5px; text-align: center;">', unsafe_allow_html=True)
            st.image(img_qr, width=220)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.code(copia)
        st.button("Sair", on_click=lambda: st.session_state.update({"logado": False}))
