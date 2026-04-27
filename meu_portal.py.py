import streamlit as st
import pandas as pd
import re
import io
import segno
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Portal SPAÇO PÉS", layout="wide")

def limpar_numero(texto):
    return re.sub(r'\D', '', str(texto)) if pd.notnull(texto) else ""

# --- TRATAMENTO DE VALOR (CORRIGE R$ 176,58 QUE VIRA 17658) ---
def tratar_valor_br(valor):
    if pd.isna(valor): return 0.0
    v = str(valor).strip().replace('R$', '').replace(' ', '')
    # Se o valor vier como "176,58" (com vírgula), corrigimos
    if ',' in v:
        v = v.replace('.', '').replace(',', '.')
    try:
        val = float(v)
        # Se o valor for absurdamente alto (ex: 17658 em vez de 176.58), dividimos por 100
        # Ajuste este limite se tiver notas reais acima de 5 mil reais
        if val > 5000 and '.' not in str(valor):
            return val / 100
        return val
    except:
        return 0.0

# --- GERADOR PIX ---
def gerar_pix_seguro(valor, chave, nome, cidade, notas_selecionadas):
    def f(id, v): return f"{id}{len(v):02d}{v}"
    
    docs_limpos = [re.sub(r'\D', '', str(n)) for n in notas_selecionadas]
    txt_notas = "N" + ",".join([n for n in docs_limpos if n])
    txid = re.sub(r'[^A-Z0-9]', '', txt_notas.upper())[:25] 
    if not txid: txid = "PORTAL"
    
    payload = f("00", "01") 
    payload += f("26", f("00", "br.gov.bcb.pix") + f("01", chave))
    payload += "520400005303986" 
    payload += f("54", f"{valor:.2f}")
    payload += "5802BR" 
    payload += f("59", nome[:25])
    payload += f("60", cidade[:15])
    payload += f("62", f("05", txid)) 
    payload += "6304"
    
    # Cálculo CRC16
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

# --- CARREGAR DADOS ---
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

        return pd.DataFrame({
            'ID_TEL': df[c_tel].apply(limpar_numero),
            'CLIENTE': df[c_nom],
            'VALOR': df[c_val].apply(tratar_valor_br),
            'DOCUMENTO': df[c_doc],
            'VENCIMENTO': pd.to_datetime(df[c_ven], errors='coerce')
        })
    except Exception as e:
        st.error(f"Erro na planilha: {e}")
        return None

if 'logado' not in st.session_state: st.session_state.logado = False
if 'minhas_notas' not in st.session_state: st.session_state.minhas_notas = None

df_base = carregar_dados()

if not st.session_state.logado:
    st.markdown("<h1 style='text-align: center;'>👠 SPAÇO PÉS</h1>", unsafe_allow_html=True)
    with st.columns([1, 1, 1])[1]:
        acesso = limpar_numero(st.text_input("Sua Senha (DDD + Telefone)", type="password"))
        if st.button("ENTRAR NO PORTAL", use_container_width=True):
            if len(acesso) >= 8:
                match = df_base[df_base['ID_TEL'].str.endswith(acesso[-8:])]
                if not match.empty:
                    st.session_state.minhas_notas = match
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("Telefone não encontrado no cadastro.")
            else:
                st.warning("Digite o número completo com DDD.")
else:
    # --- INTERFACE LOGADA ---
    notas = st.session_state.minhas_notas
    st.title(f"Olá, {notas['CLIENTE'].iloc[0]}")
    st.write("Selecione as notas para pagar:")

    selecionadas_valores = []
    selecionadas_docs = []
    
    # Listagem das notas
    for idx, r in notas.sort_values('VENCIMENTO').iterrows():
        c1, c2, c3 = st.columns([0.5, 3, 1])
        
        # Checkbox para seleção
        if c1.checkbox("Pagar", key=f"check_{idx}"):
            selecionadas_valores.append(r['VALOR'])
            selecionadas_docs.append(r['DOCUMENTO'])
        
        vencido = False
        if pd.notnull(r['VENCIMENTO']):
            vencido = r['VENCIMENTO'].date() < datetime.now().date()
            data_str = r['VENCIMENTO'].strftime('%d/%m/%Y')
        else:
            data_str = "--/--/----"
            
        status = "VENCIDO" if vencido else "ABERTO"
        cor = "red" if vencido else "green"
        
        c2.write(f"📄 Nota: {r['DOCUMENTO']} | Vencimento: {data_str}")
        c3.markdown(f"**R$ {r['VALOR']:,.2f}** :[{status}]({cor})")
        st.divider()

    # --- BARRA LATERAL (ONDE FICA O PIX) ---
    with st.sidebar:
        st.header("Resumo do Pagamento")
        total_pago = sum(selecionadas_valores)
        st.metric("Total Selecionado", f"R$ {total_pago:,.2f}")
        
        if total_pago > 0:
            st.write("---")
            img_qr, copia_cola = gerar_pix_seguro(
                total_pago, 
                "pix@spacopes.com.br", 
                "SPACO PES", 
                "GOV VALADARES", 
                selecionadas_docs
            )
            st.image(img_qr, caption="Aponte a câmera do seu banco")
            with st.expander("Ver código Copia e Cola"):
                st.code(copia_cola)
        else:
            st.info("Selecione as notas ao lado para gerar o seu QR Code Pix.")

        st.write("---")
        if st.button("Sair / Logout"):
            st.session_state.logado = False
            st.session_state.minhas_notas = None
            st.rerun()