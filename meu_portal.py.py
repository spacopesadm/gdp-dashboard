import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS PARA BARRA FIXA NO RODAPÉ ---
st.markdown("""
    <style>
    /* Estilo geral */
    .stApp { background-color: #FFFFFF !important; }
    :root { --gold: #c5a059; }
    
    /* Barra Fixa no Rodapé */
    .footer-fixa {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #f8f9fa;
        padding: 15px;
        border-top: 2px solid #c5a059;
        z-index: 9999;
        display: flex;
        justify-content: space-around;
        align-items: center;
        box-shadow: 0px -2px 10px rgba(0,0,0,0.1);
    }
    
    /* Espaçamento para o conteúdo não ficar escondido atrás da barra */
    .main-content { margin-bottom: 150px; }
    
    p, span, label { color: #121212 !important; }
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
    # Payload Pix Estático
    def f(id, v): return f"{id}{len(v):02d}{v}"
    
    payload = f("00", "01") + \
              f("26", f("00", "br.gov.bcb.pix") + f("01", chave)) + \
              f("52", "0000") + f("53", "986") + \
              f("54", f"{valor:.2f}") + \
              f("58", "BR") + \
              f("59", nome[:25]) + \
              f("60", cidade[:15]) + \
              f("62", f("05", identificador)) + "6304"
    
    # Cálculo do CRC16
    crc = 0xFFFF
    for char in payload.encode('utf-8'):
        crc ^= (char << 8)
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    
    payload += hex(crc & 0xFFFF).upper().replace('0X', '').zfill(4)
    
    qr = segno.make(payload, error='M')
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=10, border=1)
    return buffer.getvalue(), payload

@st.cache_data(ttl=60)
def carregar_dados():
    try:
        df = pd.read_excel("Pasta1.xlsx")
        df.columns = [str(c).strip().upper() for c in df.columns]
        # Identificação automática de colunas
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_doc = [c for c in df.columns if any(x in str(c) for x in ['NUM', 'DOC', 'NOTA'])][0]
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_pago = [c for c in df.columns if any(x in c for x in ['PAGO', 'PAGTO', 'BAIXA'])][0]
        
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

# --- LÓGICA DE ACESSO ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

if not st.session_state.logado:
    st.write("### 👠 SPAÇO PÉS - Portal do Cliente")
    acesso = limpar_numero(st.text_input("Digite seu telefone cadastrado", type="password"))
    if st.button("ACESSAR"):
        if df_base is not None:
            # Busca pelos últimos 8 dígitos para evitar erro de DDD/9
            match = df_base[df_base['TEL'].str.endswith(acesso[-8:])] if len(acesso) >= 8 else pd.DataFrame()
            if not match.empty:
                st.session_state.dados = match
                st.session_state.logado = True
                st.rerun()
            else: st.error("Telefone não encontrado.")
else:
    # --- ÁREA LOGADA ---
    notas = st.session_state.dados
    pendentes = notas[notas['PAGO'].isna()].sort_values('VENC')
    
    st.markdown(f"### Olá, {notas['CLIENTE'].iloc[0]}")
    
    # Criar abas
    tab1, tab2 = st.tabs(["📌 Contas a Pagar", "✅ Histórico"])
    
    sel_valores = []
    sel_docs = []
    
    with tab1:
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        if pendentes.empty:
            st.success("Você não possui pendências!")
        else:
            for idx, r in pendentes.iterrows():
                col1, col2 = st.columns([4, 1])
                dt = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
                if col1.checkbox(f"Nota: {r['DOC']} | Vencimento: {dt}", key=idx):
                    sel_valores.append(r['VALOR'])
                    sel_docs.append(str(r['DOC']))
                col2.write(f"R$ {r['VALOR']:,.2f}")
                st.divider()
        st.markdown('</div>', unsafe_allow_html=True)

    with tab2:
        pagas = notas[notas['PAGO'].notna()]
        st.dataframe(pagas[['DOC', 'VENC', 'VALOR', 'PAGO']], use_container_width=True)

    # --- BARRA FIXA DE PAGAMENTO NO RODAPÉ ---
    total = sum(sel_valores)
    if total > 0:
        # AQUI VOCÊ COLOCA SUA CHAVE PIX REAL
        CHAVE_PIX = "pix@spacopes.com.br" # Coloque o CNPJ ou E-mail da loja aqui
        
        id_cobrança = f"NOTA{sel_docs[0]}" if len(sel_docs) == 1 else "VARIAS"
        img_qr, copia_cola = gerar_pix_seguro(total, CHAVE_PIX, "SPACO DOS PES", "GOV VALADARES", id_cobrança)
        
        # Injeção da barra fixa no rodapé
        st.markdown(f"""
            <div class="footer-fixa">
                <div style="text-align: left;">
                    <span style="font-size: 14px; font-weight: bold;">TOTAL SELECIONADO</span><br>
                    <span style="font-size: 24px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="text-align: center;">
                    <span style="font-size: 12px;">Escaneie o QR Code ou use o Copia e Cola</span>
                </div>
                <div style="text-align: right;">
                    <button onclick="navigator.clipboard.writeText('{copia_cola}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        COPIAR PIX
                    </button>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Exibe o QR Code apenas se o usuário rolar até o final ou via menu
        with st.sidebar:
            st.image(img_qr, caption="QR Code de Pagamento")
            st.text_area("Código Pix Copia e Cola:", copia_cola, height=100)
    
    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
