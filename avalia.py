import streamlit as st
import os
import json
from datetime import datetime
from fpdf import FPDF
import firebase_admin
from firebase_admin import credentials, db
import re

# Diretórios
RELATORIO_DIR = "relatorios/"
os.makedirs(RELATORIO_DIR, exist_ok=True)

# Firebase - inicializar apenas uma vez
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_key.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://avalia-pntp-default-rtdb.firebaseio.com/'
    })

# Gerar chave segura
def gerar_chave_firebase(municipio, tipo_orgao):
    chave = f"{municipio}_{tipo_orgao}".lower()
    chave = re.sub(r"[ .#/\\$\\[\\]]", "_", chave)
    return chave

# Firebase utils
def salvar_no_firebase(municipio, tipo_orgao, respostas):
    chave = gerar_chave_firebase(municipio, tipo_orgao)
    ref = db.reference(f"avaliacoes/{chave}")
    ref.set({
        "municipio": municipio,
        "tipo": tipo_orgao,
        "respostas": respostas,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

def carregar_do_firebase(municipio, tipo_orgao):
    chave = gerar_chave_firebase(municipio, tipo_orgao)
    ref = db.reference(f"avaliacoes/{chave}")
    return ref.get()

# Arquivos locais
CRITERIOS_JSON = "criterios_por_topico.json"
EXPLICACOES_JSON = "explicacoes_cartilha.json"

def carregar_criterios(tipo_orgao):
    with open(CRITERIOS_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get(tipo_orgao, {})

def carregar_explicacoes():
    with open(EXPLICACOES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def limpar_texto(texto):
    if not texto:
        return ""
    return texto.replace("–", "-").replace("“", '"').replace("”", '"').replace("•", "-").replace("’", "'").replace("‘", "'").replace("…", "...")

def gerar_pdf(dados):
    nome = f"{dados['municipio'].replace(' ', '_')}_{dados['tipo']}_relatorio.pdf"
    caminho = os.path.join(RELATORIO_DIR, nome)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, limpar_texto(f"Avaliação de {dados['municipio']}"), ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, limpar_texto(f"Tipo: {dados['tipo']} - Data: {dados['data']}"), ln=True)
    pdf.ln(5)

    for topico, perguntas in dados["respostas"].items():
        bloco_topico = []
        for pergunta, criterios in perguntas.items():
            blocos_nao_atende = []
            for crit, v in criterios.items():
                if v["status"] == "Não Atende":
                    linha = f"  - {crit}: {v['status']}"
                    if v["observacao"]:
                        linha += f" | Obs: {v['observacao']}"
                    blocos_nao_atende.append(limpar_texto(linha))
            if blocos_nao_atende:
                bloco_topico.append((pergunta, blocos_nao_atende))

        if bloco_topico:
            pdf.set_font("Arial", "B", 13)
            pdf.cell(0, 10, limpar_texto(topico), ln=True)
            pdf.set_font("Arial", "", 11)
            for pergunta, linhas in bloco_topico:
                pdf.multi_cell(0, 8, limpar_texto(f"- {pergunta}"))
                for linha in linhas:
                    pdf.multi_cell(0, 7, linha)
                pdf.ln(2)
            pdf.ln(3)

    pdf.output(caminho)
    return caminho

# Interface
st.set_page_config(page_title="Avaliação Firebase", layout="wide")
st.title("📋 Avaliação com Firebase (com validação)")

municipio = st.text_input("Nome do Município:")
tipo_orgao = st.radio("Tipo de órgão:", ["Prefeitura", "Câmara"])

estrutura = carregar_criterios(tipo_orgao)
explicacoes = carregar_explicacoes()
respostas = {}
opcoes = ["Atende", "Não Atende"]

dados_antigos = carregar_do_firebase(municipio, tipo_orgao)

def recuperar(topico, pergunta, criterio, campo):
    try:
        return dados_antigos["respostas"][topico][pergunta][criterio][campo]
    except:
        return ""

for topico, perguntas in estrutura.items():
    st.subheader(f"📂 {topico}")
    respostas[topico] = {}

    for pergunta, criterios in perguntas.items():
        respostas[topico][pergunta] = {}
        with st.expander(f"📝 {pergunta}", expanded=False):
            bloco = explicacoes.get(pergunta, {})

            if bloco.get("explicacao"):
                st.info(f"ℹ️ {bloco['explicacao']}")
            if bloco.get("base_legal"):
                st.markdown(f"📜 **Base legal:** {bloco['base_legal']}")

            status_disp = st.selectbox("Disponibilidade", opcoes,
                key=f"{topico}_{pergunta}_disp",
                index=opcoes.index(recuperar(topico, pergunta, "Disponibilidade", "status")) if dados_antigos else 0
            )
            obs_disp = st.text_input("Observação:", key=f"{topico}_{pergunta}_disp_obs",
                value=recuperar(topico, pergunta, "Disponibilidade", "observacao") if dados_antigos else "")
            respostas[topico][pergunta]["Disponibilidade"] = {"status": status_disp, "observacao": obs_disp}

            if "Disponibilidade" in criterios and status_disp == "Não Atende":
                for crit in criterios:
                    if crit != "Disponibilidade":
                        respostas[topico][pergunta][crit] = {"status": "Não Atende", "observacao": ""}
                st.warning("🔒 Os demais critérios foram marcados como Não Atende.")
            else:
                for crit in criterios:
                    if crit == "Disponibilidade":
                        continue
                    status = st.selectbox(crit, opcoes,
                        key=f"{topico}_{pergunta}_{crit}_status",
                        index=opcoes.index(recuperar(topico, pergunta, crit, "status")) if dados_antigos else 0
                    )
                    obs = st.text_input("Observação:", key=f"{topico}_{pergunta}_{crit}_obs",
                        value=recuperar(topico, pergunta, crit, "observacao") if dados_antigos else "")
                    respostas[topico][pergunta][crit] = {"status": status, "observacao": obs}

# Botões
if st.button("💾 Salvar no Firebase"):
    if not municipio.strip():
        st.warning("⚠️ Por favor, preencha o nome do município antes de salvar.")
    else:
        salvar_no_firebase(municipio, tipo_orgao, respostas)
        st.success("✅ Avaliação salva com sucesso!")

if st.button("📄 Gerar Relatório PDF"):
    if not municipio.strip():
        st.warning("⚠️ Preencha o nome do município para gerar o relatório.")
    else:
        dados = {
            "municipio": municipio,
            "tipo": tipo_orgao,
            "respostas": respostas,
            "data": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        caminho_pdf = gerar_pdf(dados)
        st.success("✅ PDF gerado com sucesso!")
        with open(caminho_pdf, "rb") as f:
            st.download_button("⬇️ Baixar PDF", f, file_name=os.path.basename(caminho_pdf))
