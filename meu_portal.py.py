import streamlit as st
import pandas as pd
import re
import io
import segno
import base64

# --- CONFIGURAÇÃO SIMPLES ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide")

# --- FUNÇÃO DE PIX DIRETA ---
def gerar_pix(valor):
    chave = "09237407000101" # Seu CNPJ
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

# --- CARREGAMENTO DE DADOS ---
@st.cache_data
def ler_planilha():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        # Força os nomes das colunas para evitar erro de letra maiúscula/minúscula
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Erro ao abrir Pasta1.xlsx: {e}")
        return None

# --- INTERFACE ---
st.title("👠 Portal do Cliente - SPAÇO PÉS")

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    tel_busca = st.text_input("Digite seu Telefone (com DDD)", placeholder="Ex: 33991234567")
    if st.button("Consultar Faturas"):
        df = ler_planilha()
        if df is not None:
            # Limpa o telefone digitado e o da planilha para comparar
            tel_limpo = re.sub(r'\D', '', tel_busca)
            # Tenta achar o telefone na coluna que contém 'TEL' ou 'FONE'
            col_tel = [c for c in df.columns if 'TEL' in c or 'FONE' in c][0]
            df[col_tel] = df[col_tel].astype(str).str.replace(r'\D', '', regex=True)
            
            user_data = df[df[col_tel].str.endswith(tel_limpo[-8:])].copy()
            
            if not user_data.empty:
                st.session_state.dados = user_data
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Telefone não encontrado.")
else:
    # CLIENTE LOGADO
    df_cli = st.session_state.dados
    nome_cli = df_cli.iloc[0][1] # Pega o nome na segunda coluna
    st.write(f"### Olá, {nome_cli}")
    
    # Identificar colunas importantes
    col_venc = [c for c in df_cli.columns if 'VENC' in c][0]
    col_valor = [c for c in df_cli.columns if 'VALOR' in c or 'PRE' in c][0]
    col_conta = df_cli.columns[4] # Coluna E
    
    # Filtra o que não foi pago (coluna H vazia)
    pendentes = df_cli[df_cli.iloc[:, 7].isna()]
    
    selecionados = []
    
    for i, row in pendentes.iterrows():
        # Trata o valor para garantir que seja número
        v_bruto = re.sub(r'\D', '', str(row[col_valor]))
        v_final = float(v_bruto) / 100 if v_bruto else 0.0
        
        check = st.checkbox(f"Nota: {row[col_conta]} | Vencimento: {row[col_venc]} | Valor: R$ {v_final:,.2f}", key=i)
        if check:
            selecionados.append(v_final)
    
    total = sum(selecionados)
    
    if total > 0:
        st.markdown("---")
        st.write(f"## Total selecionado: R$ {total:,.2f}")
        
        img_b64, pix_code = gerar_pix(total)
        st.image(f"data:image/png;base64,{img_b64}", width=250)
        st.code(pix_code, language="text")
        st.write("👆 Copie o código acima e pague no seu banco.")
        
    if st.button("Sair / Trocar de conta"):
        st.session_state.clear()
        st.rerun()
