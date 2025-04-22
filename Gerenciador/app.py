import streamlit as st
st.set_page_config(page_title="Controle de Mercadorias", layout="wide")

import os
import pandas as pd
from datetime import datetime, date
import tempfile
import openpyxl
import plotly.express as px
import plotly.graph_objects as go

# ==============================================================================
# CUSTOM CSS PARA UMA INTERFACE MODERNA
# ==============================================================================
st.markdown(
    """
    <style>
        /* Centraliza o conteúdo e define margens para um layout limpo */
        .main .block-container {
            padding: 2rem 2rem;
            max-width: 1200px;
            margin: auto;
        }
        /* Customiza os títulos e métricas */
        h1, h2, h3, h4 {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #333333;
        }
        .css-1avcm0n {
            font-family: 'Segoe UI', sans-serif;
        }
        /* Ajuste no botão de download */
        .css-1emrehy.edgvbvh3 {
            background-color: #007BFF;
            color: #FFFFFF;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ==============================================================================
# TÍTULO PRINCIPAL
# ==============================================================================
st.title("📦 Sistema de Controle de Mercadorias")

# ==============================================================================
# INICIALIZAÇÃO DOS DADOS (SESSION STATE)
# ==============================================================================
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(
        columns=["Data", "Produto", "Tipo", "Quantidade", "Valor Unitário"]
    )

# ==============================================================================
# FUNÇÕES AUXILIARES
# ==============================================================================

def carregar_dados(uploaded_file):
    """
    Lê o arquivo (CSV ou Excel), valida as colunas obrigatórias e formata os dados.
    """
    try:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        df.columns = df.columns.str.strip()
        
        obrigatorias = ["Data", "Produto", "Tipo", "Quantidade"]
        for col in obrigatorias:
            if col not in df.columns:
                st.error(f"Coluna obrigatória '{col}' não encontrada no arquivo.")
                return None
        
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date
        df.dropna(subset=["Data", "Produto", "Tipo", "Quantidade"], inplace=True)
        df["Tipo"] = df["Tipo"].fillna("").str.lower().str.strip()
        
        if "Valor Unitário" in df.columns:
            df["Valor Unitário"] = pd.to_numeric(df["Valor Unitário"], errors="coerce").fillna(0.0)
        else:
            df["Valor Unitário"] = 0.0
        
        return df
    
    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {e}")
        return None

def inserir_registro_manual():
    """
    Permite a inserção manual de um registro.
    """
    with st.form(key="form_registro", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_registro = st.date_input("Data", value=date.today())
        with col2:
            produto = st.text_input("Produto")
        with col3:
            tipo = st.selectbox("Tipo", ["entrada", "saída"])
        quantidade = st.number_input("Quantidade", min_value=0, step=1)
        valor_unit = st.number_input("Valor Unitário", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        submitted = st.form_submit_button("Adicionar Registro")
        if submitted:
            return {
                "Data": data_registro,
                "Produto": produto,
                "Tipo": tipo,
                "Quantidade": quantidade,
                "Valor Unitário": valor_unit
            }
    return None

def calcular_saldo(df):
    """
    Calcula o resumo do estoque por produto considerando:
    - Entradas, Saídas e Saldo em quantidade;
    - Valores financeiros (Valor Entradas, Valor Saídas e Resultado).
    Se não houver registro de saída para um produto, o resultado será 0.
    """
    entradas_qty = df[df["Tipo"] == "entrada"].groupby("Produto")["Quantidade"].sum()
    saidas_qty = df[df["Tipo"] == "saída"].groupby("Produto")["Quantidade"].sum()
    saldo_qty = entradas_qty.subtract(saidas_qty, fill_value=0)
    
    df["Valor Total"] = df["Quantidade"] * df["Valor Unitário"]
    entradas_valor = df[df["Tipo"] == "entrada"].groupby("Produto")["Valor Total"].sum()
    saidas_valor = df[df["Tipo"] == "saída"].groupby("Produto")["Valor Total"].sum()
    resultado = saidas_valor.subtract(entradas_valor, fill_value=0)
    resultado = resultado.where(saidas_valor != 0, 0)
    
    saldo = pd.DataFrame({
        "Entradas": entradas_qty,
        "Saídas": saidas_qty,
        "Saldo Atual": saldo_qty,
        "Valor Entradas": entradas_valor,
        "Valor Saídas": saidas_valor,
        "Resultado": resultado
    }).fillna(0)
    return saldo.sort_values("Saldo Atual", ascending=False)

def grafico_barra_quantidade(saldo):
    """
    Gera um gráfico de barras comparativo de quantidades (Entradas vs Saídas) por produto.
    """
    df_plot = saldo.reset_index()
    fig = px.bar(
        df_plot,
        x="Produto",
        y=["Entradas", "Saídas"],
        barmode="group",
        title="Comparativo de Quantidades (Entradas x Saídas)",
        labels={"value": "Quantidade", "variable": "Tipo"}
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor="#FFFFFF",
        legend_title_text="Tipo",
        margin=dict(l=40, r=40, t=60, b=80)
    )
    st.plotly_chart(fig, use_container_width=True)

def grafico_barra_valor(saldo):
    """
    Gera um gráfico de barras comparativo de valores (Valor Entradas vs Valor Saídas) por produto.
    """
    df_plot = saldo.reset_index()
    fig = px.bar(
        df_plot,
        x="Produto",
        y=["Valor Entradas", "Valor Saídas"],
        barmode="group",
        title="Comparativo de Valores (Entradas x Saídas)",
        labels={"value": "Valor (R$)", "variable": "Tipo"}
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor="#FFFFFF",
        legend_title_text="Tipo",
        margin=dict(l=40, r=40, t=60, b=80)
    )
    st.plotly_chart(fig, use_container_width=True)

def grafico_linha_evolucao(produto, df_produto):
    """
    Gera um gráfico de linha com a evolução diária da quantidade para um produto selecionado.
    """
    df_produto["Data"] = pd.to_datetime(df_produto["Data"])
    df_resumo = df_produto.groupby(["Data", "Tipo"])["Quantidade"].sum().reset_index()
    fig = px.line(
        df_resumo,
        x="Data",
        y="Quantidade",
        color="Tipo",
        title=f"Evolução Diária - {produto}",
        markers=True,
        labels={"Quantidade": "Quantidade", "Data": "Data"}
    )
    fig.update_layout(
        xaxis_title="Data",
        yaxis_title="Quantidade",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=40, r=40, t=60, b=80)
    )
    st.plotly_chart(fig, use_container_width=True)

def exportar_relatorio(df, saldo):
    """
    Exporta os dados e o resumo para um arquivo Excel com duas abas: 'Dados' e 'Resumo'.
    """
    data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"Relatorio_Controle_Mercadorias_{data_atual}.xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        caminho_arquivo = tmp.name
    with pd.ExcelWriter(caminho_arquivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
        saldo.to_excel(writer, sheet_name="Resumo")
    return caminho_arquivo

def formatar_tabela_resumo(saldo):
    """
    Formata a tabela de resumo do estoque com valores monetários e estilo condicional para o resultado.
    """
    styles = [
        {"selector": "th", "props": [("font-size", "12pt"), ("text-align", "center")]},
        {"selector": "td", "props": [("font-size", "11pt")]}
    ]
    def color_resultado(val):
        if val < 0:
            return "color: red"
        elif val > 0:
            return "color: green"
        else:
            return "color: black"
    return (
        saldo.style.format({
            "Valor Entradas": "R$ {:,.2f}",
            "Valor Saídas": "R$ {:,.2f}",
            "Resultado": "R$ {:,.2f}"
        })
        .applymap(color_resultado, subset=["Resultado"])
        .set_table_styles(styles)
    )

# ==============================================================================
# SIDEBAR: INSERÇÃO DE DADOS, FILTROS E ANÁLISE DETALHADA
# ==============================================================================
st.sidebar.header("Inserção de Dados")
origem = st.sidebar.radio("Origem dos Dados", ["Carregar arquivo", "Inserção manual"])
if origem == "Carregar arquivo":
    arquivo = st.sidebar.file_uploader("Envie arquivo CSV ou Excel", type=["csv", "xlsx"])
    if arquivo is not None:
        df_importado = carregar_dados(arquivo)
        if df_importado is not None:
            st.session_state.df = pd.concat([st.session_state.df, df_importado], ignore_index=True)
            st.sidebar.success("Arquivo importado com sucesso!")
elif origem == "Inserção manual":
    registro = inserir_registro_manual()
    if registro is not None:
        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([registro])], ignore_index=True)
        st.sidebar.success("Registro adicionado!")

if st.sidebar.button("Limpar Dados"):
    st.session_state.df = pd.DataFrame(
        columns=["Data", "Produto", "Tipo", "Quantidade", "Valor Unitário"]
    )
    st.sidebar.info("Dados limpos.")

st.sidebar.header("Filtros")
df_filtrado = st.session_state.df.copy()
if not df_filtrado.empty:
    datas = df_filtrado["Data"].dropna()
    data_min = min(datas) if not datas.empty else date.today()
    data_max = max(datas) if not datas.empty else date.today()
    intervalo = st.sidebar.date_input("Período", value=[data_min, data_max])
    if isinstance(intervalo, list) and len(intervalo) == 2:
        inicio, fim = intervalo
        df_filtrado = df_filtrado[(df_filtrado["Data"] >= inicio) & (df_filtrado["Data"] <= fim)]
    produtos_disp = sorted(df_filtrado["Produto"].unique().tolist())
    produtos_sel = st.sidebar.multiselect("Produtos", options=produtos_disp, default=produtos_disp)
    if produtos_sel:
        df_filtrado = df_filtrado[df_filtrado["Produto"].isin(produtos_sel)]
else:
    st.sidebar.info("Nenhum dado para filtrar.")

st.sidebar.header("Análise Detalhada por Produto")
produtos_analise = sorted(st.session_state.df["Produto"].unique().tolist())
produto_escolhido = st.sidebar.selectbox("Selecione um produto", options=["Nenhum"] + produtos_analise)

# ==============================================================================
# ÁREA PRINCIPAL: EXIBIÇÃO DOS DADOS, RESUMO E GRÁFICOS
# ==============================================================================
st.subheader("Dados de Movimentações")
if not st.session_state.df.empty:
    st.dataframe(st.session_state.df, use_container_width=True)
else:
    st.info("Nenhum dado inserido até o momento.")

if not df_filtrado.empty:
    saldo = calcular_saldo(df_filtrado)
    
    st.subheader("Resumo do Estoque por Produto")
    st.write(formatar_tabela_resumo(saldo))
    
    st.subheader("Gráficos Comparativos")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        grafico_barra_quantidade(saldo)
    with col_chart2:
        grafico_barra_valor(saldo)
    
    total_entradas_qty = df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"].sum()
    total_saidas_qty = df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"].sum()
    total_valor_entradas = (df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"] *
                             df_filtrado[df_filtrado["Tipo"]=="entrada"]["Valor Unitário"]).sum()
    total_valor_saidas = (df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"] *
                          df_filtrado[df_filtrado["Tipo"]=="saída"]["Valor Unitário"]).sum()
    resultado_global = 0 if total_valor_saidas == 0 else total_valor_saidas - total_valor_entradas

    st.subheader("Resumo Global")
    col_res1, col_res2, col_res3, col_res4, col_res5 = st.columns(5)
    col_res1.metric("Entradas (Qtd)", value=total_entradas_qty)
    col_res2.metric("Saídas (Qtd)", value=total_saidas_qty)
    col_res3.metric("Valor Entradas", value=f"R$ {total_valor_entradas:,.2f}")
    col_res4.metric("Valor Saídas", value=f"R$ {total_valor_saidas:,.2f}")
    if resultado_global < 0:
        col_res5.metric("Resultado (Perda)", value=f"R$ {abs(resultado_global):,.2f}",
                        delta=f"-R$ {abs(resultado_global):,.2f}", delta_color="inverse")
    else:
        col_res5.metric("Resultado (Lucro)", value=f"R$ {resultado_global:,.2f}",
                        delta=f"+R$ {resultado_global:,.2f}", delta_color="normal")
    
    if st.button("Exportar relatório para Excel"):
        caminho = exportar_relatorio(df_filtrado, saldo)
        with open(caminho, "rb") as file:
            st.download_button(
                label="Download do Relatório",
                data=file,
                file_name=os.path.basename(caminho),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("Nenhum dado disponível após os filtros.")

# ==============================================================================
# ANÁLISE DETALHADA POR PRODUTO
# ==============================================================================
if produto_escolhido != "Nenhum":
    df_prod = st.session_state.df[st.session_state.df["Produto"] == produto_escolhido].copy()
    if not df_prod.empty:
        st.subheader(f"Análise Detalhada - {produto_escolhido}")
        st.dataframe(df_prod, use_container_width=True)
        grafico_linha_evolucao(produto_escolhido, df_prod)

# ==============================================================================
# PRINCIPAIS PRODUTOS POR SALDO
# ==============================================================================
st.subheader("Principais Produtos por Saldo")
if not df_filtrado.empty:
    principais = calcular_saldo(df_filtrado).reset_index().sort_values("Saldo Atual", ascending=False).head(5)
    fig_top = px.bar(
        principais,
        x="Produto",
        y="Saldo Atual",
        title="Top 5 Produtos por Saldo Atual",
        labels={"Saldo Atual": "Saldo Atual (Qtd)"},
        text="Saldo Atual"
    )
    fig_top.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig_top.update_layout(uniformtext_minsize=8, uniformtext_mode="hide", margin=dict(l=40, r=40, t=60, b=80))
    st.plotly_chart(fig_top, use_container_width=True)
    st.table(principais)
else:
    st.info("Nenhum dado disponível para exibir os principais produtos.")


