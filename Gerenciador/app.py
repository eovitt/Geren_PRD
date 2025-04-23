import streamlit as st
import pandas as pd
from datetime import datetime, date
import tempfile
import os
import openpyxl
import plotly.express as px
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da página
st.set_page_config(page_title="Controle de Mercadorias", layout="wide")

# CSS personalizado com nova paleta de cores
st.markdown(
    """
    <style>
        .main .block-container {
            padding: 2rem;
            max-width: 1200px;
            margin: auto;
            background-color: #FFFFFF;
        }
        h1, h2, h3, h4 {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            color: #1A3C5A; /* Azul escuro */
        }
        .css-1avcm0n {
            font-family: 'Segoe UI', sans-serif;
            color: #1A3C5A;
        }
        .css-1emrehy.edgvbvh3 {
            background-color: #2E7D32; /* Verde escuro */
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: bold;
        }
        .css-1emrehy.edgvbvh3:hover {
            background-color: #4CAF50; /* Verde claro */
            cursor: pointer;
        }
        .css-kniuvf {
            background-color: #F5F7FA; /* Cinza claro */
            border: 1px solid #E0E0E0;
            border-radius: 8px;
            padding: 1rem;
            font-size: 1.2rem;
        }
        a {
            color: #4CAF50;
            text-decoration: none;
        }
        a:hover {
            color: #2E7D32;
        }
        /* Estilizar tabelas */
        table {
            border-collapse: collapse;
            width: 100%;
        }
        th, td {
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid #E0E0E0;
        }
        th {
            background-color: #1A3C5A;
            color: white;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Inicialização do session_state
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame(
        columns=["Data", "Produto", "Tipo", "Quantidade", "Custo Unitário", "Preço de Venda"]
    )


# ==============================================================================
# FUNÇÕES DE MANIPULAÇÃO DE DADOS
# ==============================================================================

@st.cache_data
def carregar_dados(uploaded_file):
    """Lê e valida um arquivo CSV ou Excel com dados de movimentação."""
    try:
        logger.info(f"Carregando arquivo: {uploaded_file.name}")
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
        
        df.columns = df.columns.str.strip()
        required_columns = ["Data", "Produto", "Tipo", "Quantidade"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"Colunas obrigatórias não encontradas: {missing_columns}")
            return None
        
        # Padronizar e validar dados
        df["Data"] = pd.to_datetime(df["Data"], errors="coerce").dt.date
        df["Tipo"] = df["Tipo"].str.lower().str.strip()
        df["Produto"] = df["Produto"].str.lower().str.strip()
        df.dropna(subset=required_columns, inplace=True)
        
        if not df["Tipo"].isin(["entrada", "saída"]).all():
            st.error("A coluna 'Tipo' deve conter apenas 'entrada' ou 'saída'.")
            return None
        if (df["Quantidade"] < 0).any():
            st.error("A coluna 'Quantidade' não pode conter valores negativos.")
            return None
        
        df["Custo Unitário"] = pd.to_numeric(df.get("Custo Unitário", 0.0), errors="coerce").fillna(0.0)
        df["Preço de Venda"] = pd.to_numeric(df.get("Preço de Venda", 0.0), errors="coerce").fillna(0.0)
        
        # Validar Preço de Venda para saídas
        if (df[df["Tipo"] == "saída"]["Preço de Venda"] <= 0).any():
            st.error("O 'Preço de Venda' deve ser maior que 0 para saídas no arquivo carregado.")
            return None
        
        # Validar Custo Unitário para entradas do mesmo produto
        existing_df = st.session_state.df
        for _, row in df.iterrows():
            if row["Tipo"] == "entrada":
                produto = row["Produto"]
                custo_unit = row["Custo Unitário"]
                # Verificar se o produto já existe em entradas
                entradas_produto = existing_df[(existing_df["Produto"] == produto) & (existing_df["Tipo"] == "entrada")]
                if not entradas_produto.empty:
                    custo_existente = entradas_produto["Custo Unitário"].iloc[0]
                    if custo_unit != custo_existente:
                        st.error(f"O produto '{produto}' já possui entradas com Custo Unitário R$ {custo_existente:.2f}. Não é permitido registrar com um valor diferente (R$ {custo_unit:.2f}).")
                        return None
        
        logger.info(f"Dados carregados: {df}")
        return df
    
    except Exception as e:
        logger.error(f"Erro ao carregar arquivo: {e}")
        st.error(f"Erro ao carregar o arquivo: {e}")
        return None

def inserir_registro_manual():
    """Permite a inserção manual de um registro."""
    with st.form(key="form_registro", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            data_registro = st.date_input("Data", value=date.today())
        with col2:
            produto = st.text_input("Produto")
        with col3:
            tipo = st.selectbox("Tipo", ["entrada", "saída"])
        
        quantidade = st.number_input("Quantidade", min_value=0, step=1)
        custo_unit = st.number_input("Custo Unitário", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        preco_venda = st.number_input("Preço de Venda", min_value=0.0, value=0.0, step=0.01, format="%.2f")
        
        if not st.form_submit_button("Adicionar Registro"):
            return None
        
        if not produto.strip():
            st.error("O campo 'Produto' não pode estar vazio.")
            return None
        
        if tipo == "saída" and preco_venda <= 0:
            st.error("O 'Preço de Venda' deve ser maior que 0 para saídas.")
            return None
        
        # Validar Custo Unitário para entradas do mesmo produto
        if tipo == "entrada":
            produto = produto.lower().strip()
            entradas_produto = st.session_state.df[(st.session_state.df["Produto"] == produto) & (st.session_state.df["Tipo"] == "entrada")]
            if not entradas_produto.empty:
                custo_existente = entradas_produto["Custo Unitário"].iloc[0]
                if custo_unit != custo_existente:
                    st.error(f"O produto '{produto}' já possui entradas com Custo Unitário R$ {custo_existente:.2f}. Não é permitido registrar com um valor diferente (R$ {custo_unit:.2f}).")
                    return None
            
        return {
            "Data": data_registro,
            "Produto": produto.lower().strip(),
            "Tipo": tipo,
            "Quantidade": quantidade,
            "Custo Unitário": custo_unit,
            "Preço de Venda": preco_venda
        }

@st.cache_data
def calcular_saldo(df):
    """Calcula o resumo do estoque por produto."""
    logger.info(f"Dados recebidos para cálculo: {df}")
    
    # Verificar se há saídas com Preço de Venda zerado
    if not df[df["Tipo"] == "saída"].empty:
        saidas_invalidas = df[(df["Tipo"] == "saída") & (df["Preço de Venda"] <= 0)]
        if not saidas_invalidas.empty:
            st.warning("Existem saídas com 'Preço de Venda' igual a 0. Por favor, corrija os registros para calcular o 'Valor Saídas' e 'Lucro' corretamente.")
            logger.warning(f"Saídas com Preço de Venda inválido: {saidas_invalidas}")
    
    entradas_qty = df[df["Tipo"] == "entrada"].groupby("Produto")["Quantidade"].sum()
    saidas_qty = df[df["Tipo"] == "saída"].groupby("Produto")["Quantidade"].sum()
    saldo_qty = entradas_qty.subtract(saidas_qty, fill_value=0)
    
    # Calcular valores financeiros
    df_entradas = df[df["Tipo"] == "entrada"].copy()
    df_entradas["Valor Entradas"] = df_entradas["Quantidade"] * df_entradas["Custo Unitário"]
    entradas_valor = df_entradas.groupby("Produto")["Valor Entradas"].sum()
    
    df_saidas = df[df["Tipo"] == "saída"].copy()
    df_saidas["Valor Saídas"] = df_saidas["Quantidade"] * df_saidas["Preço de Venda"]
    saidas_valor = df_saidas.groupby("Produto")["Valor Saídas"].sum()
    
    # Calcular lucro: (Preço de Venda - Custo Médio) * Quantidade para saídas
    custo_medio = df[df["Tipo"] == "entrada"].groupby("Produto")["Custo Unitário"].mean()
    df_saidas = df_saidas.join(custo_medio.rename("Custo Médio"), on="Produto")
    df_saidas["Custo Médio"] = df_saidas["Custo Médio"].fillna(0.0)
    df_saidas["Lucro"] = df_saidas["Quantidade"] * (df_saidas["Preço de Venda"] - df_saidas["Custo Médio"])
    lucro = df_saidas.groupby("Produto")["Lucro"].sum().fillna(0)
    
    # Log para depuração
    logger.info(f"Entradas: {entradas_qty}")
    logger.info(f"Saídas: {saidas_qty}")
    logger.info(f"Valor Entradas: {entradas_valor}")
    logger.info(f"Valor Saídas: {saidas_valor}")
    logger.info(f"Custo Médio: {custo_medio}")
    logger.info(f"Lucro: {lucro}")
    
    saldo = pd.DataFrame({
        "Entradas": entradas_qty,
        "Saídas": saidas_qty,
        "Saldo Atual": saldo_qty,
        "Valor Entradas": entradas_valor,
        "Valor Saídas": saidas_valor,
        "Lucro": lucro
    }).fillna(0)
    
    # Formatar valores diretamente no DataFrame
    saldo["Valor Entradas"] = saldo["Valor Entradas"].apply(lambda x: f"R$ {x:,.2f}")
    saldo["Valor Saídas"] = saldo["Valor Saídas"].apply(lambda x: f"R$ {x:,.2f}")
    saldo["Lucro"] = saldo["Lucro"].apply(lambda x: f"R$ {x:,.2f}")
    
    logger.info(f"Resumo calculado: {saldo}")
    return saldo.sort_values("Saldo Atual", ascending=False)


# ==============================================================================
# FUNÇÕES DE VISUALIZAÇÃO
# ==============================================================================

def create_bar_chart(data, x, y, title, labels, barmode="group"):
    """Cria um gráfico de barras com Plotly."""
    if data.empty:
        st.warning("Nenhum dado disponível para o gráfico.")
        return
    fig = px.bar(
        data.reset_index(),
        x=x,
        y=y,
        barmode=barmode,
        title=title,
        labels=labels
    )
    fig.update_layout(
        xaxis_tickangle=-45,
        plot_bgcolor="#FFFFFF",
        legend_title_text="Tipo",
        margin=dict(l=40, r=40, t=60, b=80)
    )
    st.plotly_chart(fig, use_container_width=True)

def grafico_barra_quantidade(saldo):
    """Gera um gráfico de barras comparativo de quantidades (Entradas vs Saídas)."""
    create_bar_chart(
        saldo,
        x="Produto",
        y=["Entradas", "Saídas"],
        title="Comparativo de Quantidades (Entradas x Saídas)",
        labels={"value": "Quantidade", "variable": "Tipo"}
    )

def grafico_barra_valor(saldo):
    """Gera um gráfico de barras comparativo de valores (Valor Entradas vs Valor Saídas)."""
    create_bar_chart(
        saldo,
        x="Produto",
        y=["Valor Entradas", "Valor Saídas"],
        title="Comparativo de Valores (Entradas x Saídas)",
        labels={"value": "Valor (R$)", "variable": "Tipo"}
    )

def grafico_linha_evolucao(produto, df_produto, agregacao="Diária"):
    """Gera um gráfico de linha com a evolução da quantidade para um produto."""
    if df_produto.empty:
        st.warning("Nenhum dado disponível para o gráfico.")
        return
    
    df_resumo = df_produto.copy()
    if agregacao == "Semanal":
        df_resumo["Data"] = pd.to_datetime(df_resumo["Data"]).dt.to_period("W").apply(lambda r: r.start_time)
    elif agregacao == "Mensal":
        df_resumo["Data"] = pd.to_datetime(df_resumo["Data"]).dt.to_period("M").apply(lambda r: r.start_time)
    
    df_resumo = df_resumo.groupby(["Data", "Tipo"])["Quantidade"].sum().reset_index()
    fig = px.line(
        df_resumo,
        x="Data",
        y="Quantidade",
        color="Tipo",
        title=f"Evolução {agregacao} - {produto}",
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

def grafico_top_produtos(df_filtrado):
    """Gera um gráfico dos principais produtos por saldo."""
    principais = calcular_saldo(df_filtrado).reset_index().sort_values("Saldo Atual", ascending=False).head(5)
    fig = px.bar(
        principais,
        x="Produto",
        y="Saldo Atual",
        title="Top 5 Produtos por Saldo Atual",
        labels={"Saldo Atual": "Saldo Atual (Qtd)"},
        text="Saldo Atual"
    )
    fig.update_traces(texttemplate="%{text:.2s}", textposition="outside")
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode="hide", margin=dict(l=40, r=40, t=60, b=80))
    st.plotly_chart(fig, use_container_width=True)
    st.table(principais)


# ==============================================================================
# FUNÇÕES DE EXPORTAÇÃO E FORMATAÇÃO
# ==============================================================================

def exportar_relatorio(df, saldo):
    """Exporta os dados e o resumo para um arquivo Excel."""
    data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo = f"Relatorio_Controle_Mercadorias_{data_atual}.xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        caminho_arquivo = tmp.name
    with pd.ExcelWriter(caminho_arquivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
        saldo.to_excel(writer, sheet_name="Resumo")
    return caminho_arquivo, nome_arquivo

def formatar_tabela_resumo(saldo):
    """Formata a tabela de resumo do estoque com valores monetários e estilo condicional."""
    def color_lucro(val):
        # Como os valores já estão formatados como string, precisamos converter para float
        val_float = float(val.replace("R$ ", "").replace(".", "").replace(",", "."))
        return "color: red" if val_float < 0 else "color: green" if val_float > 0 else "color: black"
    
    styles = [
        {"selector": "th", "props": [("font-size", "12pt"), ("text-align", "center")]},
        {"selector": "td", "props": [("font-size", "11pt")]}
    ]
    return (
        saldo.style
        .applymap(color_lucro, subset=["Lucro"])
        .set_table_styles(styles)
    )


# ==============================================================================
# FUNÇÕES DE INTERFACE
# ==============================================================================

def configurar_filtros(df):
    """Configura os filtros na sidebar e retorna o DataFrame filtrado."""
    st.sidebar.header("Filtros")
    if df.empty:
        st.sidebar.info("Nenhum dado para filtrar.")
        return df
    
    # Filtro de período
    datas = df["Data"].dropna()
    data_min, data_max = min(datas, default=date.today()), max(datas, default=date.today())
    intervalo = st.sidebar.date_input("Período", value=[data_min, data_max])
    
    df_filtrado = df
    if isinstance(intervalo, (list, tuple)) and len(intervalo) == 2:
        inicio, fim = intervalo
        if inicio > fim:
            st.error("A data inicial não pode ser posterior à data final.")
            return df
        df_filtrado = df_filtrado[(df_filtrado["Data"] >= inicio) & (df_filtrado["Data"] <= fim)]
    
    # Filtro de produtos
    produtos_disp = sorted(df_filtrado["Produto"].unique())
    produtos_sel = st.sidebar.multiselect("Produtos", options=produtos_disp, default=produtos_disp)
    if produtos_sel:
        df_filtrado = df_filtrado[df_filtrado["Produto"].isin(produtos_sel)]
    
    # Filtro de tipo de movimentação
    tipo_mov = st.sidebar.multiselect("Tipo de Movimentação", ["entrada", "saída"], default=["entrada", "saída"])
    if tipo_mov:
        df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipo_mov)]
    
    return df_filtrado

def configurar_insercao_dados():
    """Configura a seção de inserção de dados na sidebar."""
    st.sidebar.header("Inserção de Dados")
    origem = st.sidebar.radio("Origem dos Dados", ["Carregar arquivo", "Inserção manual"])
    
    if origem == "Carregar arquivo":
        arquivo = st.sidebar.file_uploader("Envie arquivo CSV ou Excel", type=["csv", "xlsx"])
        if arquivo:
            df_importado = carregar_dados(arquivo)
            if df_importado is not None:
                st.session_state.df = pd.concat([st.session_state.df, df_importado], ignore_index=True)
                st.sidebar.success("Arquivo importado com sucesso!")
    else:
        registro = inserir_registro_manual()
        if registro:
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([registro])], ignore_index=True)
            st.sidebar.success("Registro adicionado!")

    if st.sidebar.button("Limpar Dados"):
        if st.sidebar.checkbox("Confirmar limpeza dos dados"):
            st.session_state.df = pd.DataFrame(
                columns=["Data", "Produto", "Tipo", "Quantidade", "Custo Unitário", "Preço de Venda"]
            )
            st.sidebar.success("Dados limpos.")
        else:
            st.sidebar.warning("Marque a caixa de confirmação para limpar os dados.")

def configurar_analise_detalhada():
    """Configura a seção de análise detalhada por produto na sidebar."""
    st.sidebar.header("Análise Detalhada por Produto")
    produtos_analise = sorted(st.session_state.df["Produto"].unique().tolist())
    produto_escolhido = st.sidebar.selectbox("Selecione um produto", options=["Nenhum"] + produtos_analise)
    agregacao = st.sidebar.selectbox("Agregação Temporal", ["Diária", "Semanal", "Mensal"])
    return produto_escolhido, agregacao

def exibir_dados_movimentacoes(df):
    """Exibe a tabela de movimentações com formatação melhorada."""
    st.subheader("Dados de Movimentações")
    if df.empty:
        st.info("Nenhum dado inserido até o momento.")
        return
    
    # Criar uma cópia do DataFrame para formatação
    df_display = df.copy()
    
    # Formatar valores monetários
    df_display["Custo Unitário"] = df_display["Custo Unitário"].apply(lambda x: f"R$ {x:,.2f}")
    df_display["Preço de Venda"] = df_display["Preço de Venda"].apply(lambda x: f"R$ {x:,.2f}")
    
    # Definir função para colorir linhas com base no tipo
    def color_tipo(val):
        color = '#E3F2FD' if val == "entrada" else '#FFEBEE'  # Azul claro para entradas, vermelho claro para saídas
        return f'background-color: {color}'
    
    # Aplicar estilos
    styled_df = (
        df_display.style
        .applymap(color_tipo, subset=["Tipo"])
        .set_properties(**{'text-align': 'left'})
        .set_table_styles([
            {'selector': 'th', 'props': [('font-size', '12pt'), ('text-align', 'center')]},
            {'selector': 'td', 'props': [('font-size', '11pt')]}
        ])
    )
    
    st.write(styled_df)

def exibir_resumo_estoque(df_filtrado):
    """Exibe o resumo do estoque e gráficos comparativos."""
    if df_filtrado.empty:
        st.info("Nenhum dado disponível após os filtros.")
        return
    
    saldo = calcular_saldo(df_filtrado)
    
    st.subheader("Resumo do Estoque por Produto")
    st.write(formatar_tabela_resumo(saldo))
    
    st.subheader("Gráficos Comparativos")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        grafico_barra_quantidade(saldo)
    with col_chart2:
        grafico_barra_valor(saldo)
    
    # Resumo global
    total_entradas_qty = df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"].sum()
    total_saidas_qty = df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"].sum()
    total_valor_entradas = (df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"] * 
                            df_filtrado[df_filtrado["Tipo"]=="entrada"]["Custo Unitário"]).sum()
    total_valor_saidas = (df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"] * 
                          df_filtrado[df_filtrado["Tipo"]=="saída"]["Preço de Venda"]).sum()
    
    df_saidas = df_filtrado[df_filtrado["Tipo"] == "saída"].copy()
    custo_medio = df_filtrado[df_filtrado["Tipo"] == "entrada"].groupby("Produto")["Custo Unitário"].mean()
    df_saidas = df_saidas.join(custo_medio.rename("Custo Médio"), on="Produto")
    df_saidas["Custo Médio"] = df_saidas["Custo Médio"].fillna(0.0)
    df_saidas["Lucro"] = df_saidas["Quantidade"] * (df_saidas["Preço de Venda"] - df_saidas["Custo Médio"])
    lucro_global = df_saidas["Lucro"].sum()
    
    st.subheader("Resumo Global")
    col_res1, col_res2, col_res3, col_res4, col_res5 = st.columns(5)
    col_res1.metric("Entradas (Qtd)", value=total_entradas_qty)
    col_res2.metric("Saídas (Qtd)", value=total_saidas_qty)
    col_res3.metric("Valor Entradas", value=f"R$ {total_valor_entradas:,.2f}")
    col_res4.metric("Valor Saídas", value=f"R$ {total_valor_saidas:,.2f}")
    
    lucro_label = "Lucro (Perda)" if lucro_global < 0 else "Lucro"
    lucro_value = abs(lucro_global) if lucro_global < 0 else lucro_global
    delta = f"-R$ {abs(lucro_global):,.2f}" if lucro_global < 0 else f"+R$ {lucro_global:,.2f}"
    delta_color = "inverse" if lucro_global < 0 else "normal"
    col_res5.metric(lucro_label, value=f"R$ {lucro_value:,.2f}", delta=delta, delta_color=delta_color)
    
    if st.button("Exportar relatório para Excel"):
        with st.spinner("Gerando relatório..."):
            caminho, nome_arquivo = exportar_relatorio(df_filtrado, saldo)
            with open(caminho, "rb") as file:
                st.download_button(
                    label="Download do Relatório",
                    data=file,
                    file_name=nome_arquivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        st.success("Relatório gerado com sucesso!")

def exibir_analise_detalhada(produto_escolhido, agregacao):
    """Exibe a análise detalhada por produto."""
    if produto_escolhido == "Nenhum":
        return
    
    df_prod = st.session_state.df[st.session_state.df["Produto"] == produto_escolhido]
    if df_prod.empty:
        return
    
    st.subheader(f"Análise Detalhada - {produto_escolhido}")
    st.dataframe(df_prod, use_container_width=True)
    grafico_linha_evolucao(produto_escolhido, df_prod, agregacao)

def exibir_principais_produtos(df_filtrado):
    """Exibe os principais produtos por saldo."""
    st.subheader("Principais Produtos por Saldo")
    if df_filtrado.empty:
        st.info("Nenhum dado disponível para exibir os principais produtos.")
        return
    grafico_top_produtos(df_filtrado)


# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================

st.title("📦 Sistema de Controle de Mercadorias")

# Configuração da interface
configurar_insercao_dados()
df_filtrado = configurar_filtros(st.session_state.df)
produto_escolhido, agregacao = configurar_analise_detalhada()

# Exibição dos dados
exibir_dados_movimentacoes(st.session_state.df)
exibir_resumo_estoque(df_filtrado)
exibir_analise_detalhada(produto_escolhido, agregacao)
exibir_principais_produtos(df_filtrado)
