import streamlit as st
import pandas as pd
import re
import io
import segno
import base64
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide", page_icon="👠")

# --- ESTILO CSS ---
st.markdown("""
    <style>
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
    .main-content { margin-bottom: 250px; }
    p, span, label, div { color: #121212 !important; }
    .btn-whats {
        background-color: #25d366;
        color: white !important;
        padding: 10px 15px;
        border-radius: 8px;
        text-decoration: none;
        font-weight: bold;
        font-size: 14px;
    }
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
    # Limita identificador a 25 caracteres sem espaços para o banco aceitar
    id_limpo = re.sub(r'\W+', '', identificador)[:25].upper()
    
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
        c_tel = [c for c in df.columns if any(x in c for x in ['TEL', 'CEL', 'FONE'])][0]
        c_nom = [c for c in df.columns if 'NOME' in c or 'RAZ' in c][0]
        c_val = [c for c in df.columns if any(x in str(c) for x in ['VALOR', 'PRE', 'VALENTIA'])][0]
        c_doc = [c for c in df.columns if any(x in str(c) for x in ['NUM', 'DOC', 'NOTA'])][0]
        c_ven = [c for c in df.columns if 'VENC' in c][0]
        c_pago = [c for c in df.columns if any(x in c for x in ['PAGO', 'PAGTO', 'BAIXA'])][0]
        
        return pd.DataFrame({
            'TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOC': df[c_doc],
            'VENC': pd.to_datetime(df[c_ven], errors='coerce'),
            'PAGO': df[c_pago]
        })
    except: return None

# --- APP ---
if 'logado' not in st.session_state: st.session_state.logado = False
df_base = carregar_dados()

if not st.session_state.logado:
    st.write("### 👠 Portal SPAÇO PÉS")
    acesso = limpar_numero(st.text_input("Telefone (Apenas números)", type="password"))
    if st.button("ACESSAR"):
        if df_base is not None:
            match = df_base[df_base['TEL'].str.endswith(acesso[-8:])]
            if not match.empty:
                st.session_state.dados, st.session_state.logado = match, True
                st.rerun()
else:
    notas = st.session_state.dados
    pendentes = notas[notas['PAGO'].isna()].sort_values('VENC')
    
    st.markdown(f"### Olá, {notas['CLIENTE'].iloc[0]}")
    tab1, tab2 = st.tabs(["📌 Parcelas", "✅ Histórico"])
    
    sel_v, sel_d = [], []
    
    with tab1:
        st.markdown('<div class="main-content">', unsafe_allow_html=True)
        for idx, r in pendentes.iterrows():
            col1, col2 = st.columns([4, 1])
            dt = r['VENC'].strftime('%d/%m/%Y') if pd.notnull(r['VENC']) else "S/D"
            if col1.checkbox(f"Nota: {r['DOC']} | Vencimento: {dt}", key=f"chk_{idx}"):
                sel_v.append(r['VALOR'])
                sel_d.append(str(r['DOC']))
            col2.write(f"R$ {r['VALOR']:,.2f}")
            st.divider()
        st.markdown('</div>', unsafe_allow_html=True)

    # --- BARRA FIXA ATUALIZADA ---
    total = sum(sel_v)
    if total > 0:
        CHAVE_PIX = "09237407000101"
        # Agora o identificador pega o número da nota selecionada
        id_banco = f"NOTA{sel_d[0]}" if len(sel_d) == 1 else "VARIAS"
        qr_b64, copia = gerar_pix_seguro(total, CHAVE_PIX, "SPACO PES", "GOV VALADARES", id_banco)
        
        # Link para o WhatsApp
        msg_whats = f"Olá! Realizei o pagamento via Pix no valor de R$ {total:,.2f} referente à nota {', '.join(sel_d)}. Segue o comprovante:"
        link_whats = f"https://wa.me/553332782113?text={msg_whats.replace(' ', '%20')}"

        st.markdown(f"""
            <div class="footer-fixa">
                <img src="data:image/png;base64,{qr_b64}" width="90">
                <div style="text-align: left;">
                    <span style="font-size: 11px; font-weight: bold;">TOTAL</span><br>
                    <span style="font-size: 20px; color: #c5a059; font-weight: bold;">R$ {total:,.2f}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 5px;">
                    <button onclick="navigator.clipboard.writeText('{copia}')" 
                        style="background-color: #c5a059; color: white; border: none; padding: 8px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: bold;">
                        COPIAR PIX
                    </button>
                    <a href="{link_whats}" target="_blank" class="btn-whats">ENVIAR COMPROVANTE</a>
                </div>
            </div>
        """, unsafe_allow_html=True)

    if st.button("Sair"):
        st.session_state.logado = False
        st.rerun()
