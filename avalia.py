import streamlit as st
import os
import json
from datetime import datetime
from fpdf import FPDF

# Diretórios
AVALIACAO_DIR = "data/avaliacoes/"
RELATORIO_DIR = "relatorios/"
CRITERIOS_JSON = "criterios_por_topico.json"
EXPLICACOES_JSON = "explicacoes_cartilha.json"

os.makedirs(AVALIACAO_DIR, exist_ok=True)
os.makedirs(RELATORIO_DIR, exist_ok=True)

# Funções utilitárias
def carregar_criterios(tipo_orgao):
    with open(CRITERIOS_JSON, "r", encoding="utf-8") as f:
        return json.load(f).get(tipo_orgao, {})

def carregar_explicacoes():
    with open(EXPLICACOES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def listar_avaliacoes_salvas():
    return [f for f in os.listdir(AVALIACAO_DIR) if f.endswith(".json")]

def carregar_avaliacao_por_nome(nome_arquivo):
    caminho = os.path.join(AVALIACAO_DIR, nome_arquivo)
    if os.path.exists(caminho):
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def salvar_avaliacao_nomeado(municipio, tipo_orgao, respostas):
    nome_arquivo = f"{municipio.replace(' ', '_')}_{tipo_orgao}.json"
    caminho = os.path.join(AVALIACAO_DIR, nome_arquivo)
    dados = {
        "municipio": municipio,
        "tipo": tipo_orgao,
        "respostas": respostas,
        "data": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return dados

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
            disp_status = criterios.get("Disponibilidade", {}).get("status", "")
            disp_obs = criterios.get("Disponibilidade", {}).get("observacao", "")
            outros_nao_atende = []

            # Se DISPONIBILIDADE for "Não Atende", só ela entra no relatório
            if disp_status == "Não Atende":
                linha = f"- {pergunta}\n  - Disponibilidade: Não Atende"
                if disp_obs:
                    linha += f" | Obs: {disp_obs}"
                bloco_topico.append(linha)
            else:
                # Verifica os outros critérios
                for crit, v in criterios.items():
                    if crit != "Disponibilidade" and v["status"] == "Não Atende":
                        linha = f"  - {crit}: {v['status']}"
                        if v["observacao"]:
                            linha += f" | Obs: {v['observacao']}"
                        outros_nao_atende.append(limpar_texto(linha))

                if outros_nao_atende:
                    bloco_topico.append(f"- {pergunta}")
                    bloco_topico.extend(outros_nao_atende)

        if bloco_topico:
            pdf.set_font("Arial", "B", 13)
            pdf.cell(0, 10, limpar_texto(topico), ln=True)
            pdf.set_font("Arial", "", 11)
            for linha in bloco_topico:
                pdf.multi_cell(0, 7, limpar_texto(linha))
            pdf.ln(3)

    pdf.output(caminho)
    return caminho

# Interface Streamlit
st.set_page_config(page_title="Avaliação PNTP", layout="wide")
st.title("📋 Avaliação PNTP")

arquivos = listar_avaliacoes_salvas()
avaliacao_selecionada = st.selectbox("📂 Selecione uma avaliação salva:", [""] + arquivos)
ultima_avaliacao = carregar_avaliacao_por_nome(avaliacao_selecionada) if avaliacao_selecionada else None

municipio = st.text_input("Nome do Município:", value=ultima_avaliacao["municipio"] if ultima_avaliacao else "")
tipo_orgao = st.radio("Tipo de órgão:", ["Prefeitura", "Câmara"], index=["Prefeitura", "Câmara"].index(ultima_avaliacao["tipo"]) if ultima_avaliacao else 0)

estrutura = carregar_criterios(tipo_orgao)
explicacoes = carregar_explicacoes()
respostas = {}
opcoes = ["Atende", "Não Atende"]

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

            def recuperar(criterio, campo):
                try:
                    return ultima_avaliacao["respostas"][topico][pergunta][criterio][campo]
                except:
                    return ""

            status_disp = st.selectbox("Disponibilidade", opcoes,
                key=f"{topico}_{pergunta}_disp",
                index=opcoes.index(recuperar("Disponibilidade", "status")) if ultima_avaliacao else 0
            )
            obs_disp = st.text_input("Observação:", key=f"{topico}_{pergunta}_disp_obs",
                value=recuperar("Disponibilidade", "observacao") if ultima_avaliacao else "")
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
                        index=opcoes.index(recuperar(crit, "status")) if ultima_avaliacao else 0
                    )
                    obs = st.text_input("Observação:", key=f"{topico}_{pergunta}_{crit}_obs",
                        value=recuperar(crit, "observacao") if ultima_avaliacao else "")
                    respostas[topico][pergunta][crit] = {"status": status, "observacao": obs}

if st.button("💾 Salvar progresso atual"):
    salvar_avaliacao_nomeado(municipio, tipo_orgao, respostas)
    st.success("✅ Progresso salvo com sucesso!")

if st.button("📄 Salvar e Gerar Relatório PDF"):
    dados = salvar_avaliacao_nomeado(municipio, tipo_orgao, respostas)
    caminho_pdf = gerar_pdf(dados)
    st.success("✅ Relatório gerado com sucesso!")
    with open(caminho_pdf, "rb") as f:
        st.download_button("⬇️ Baixar PDF", f, file_name=os.path.basename(caminho_pdf))
