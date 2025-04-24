import streamlit as st
import pandas as pd
from datetime import datetime, date
import tempfile
import os
import plotly.express as px
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuração da página
st.set_page_config(page_title="Controle de Mercadorias", layout="wide")

# CSS personalizado (mantido igual ao original)
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
            color: #1A3C5A;
        }
        .css-1avcm0n {
            font-family: 'Segoe UI', sans-serif;
            color: #1A3C5A;
        }
        .stButton>button {
            background-color: #2E7D32;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: bold;
        }
        .stButton>button:hover {
            background-color: #4CAF50;
            cursor: pointer;
        }
        .css-kniuvf {
            background-color: #F5F7FA;
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
        .form-container {
            background-color: #F5F7FA;
            padding: 1.5rem;
            border-radius: 8px;
            margin-bottom: 2rem;
            border: 1px solid #E0E0E0;
        }
        .stTextInput>div>input,
        .stNumberInput>div>input,
        .stSelectbox>div>select,
        .stDateInput>div>input {
            border-radius: 4px;
            border: 1px solid #E0E0E0;
            background-color: #FFFFFF;
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

if "form_data" not in st.session_state:
    st.session_state.form_data = {
        "data": date.today(),
        "produto": "",
        "tipo": "entrada",
        "quantidade": 0,
        "custo_unitario": 0.0,
        "preco_venda": 0.0
    }

if "confirmar_limpeza" not in st.session_state:
    st.session_state.confirmar_limpeza = False

# ==============================================================================
# FUNÇÕES DE MANIPULAÇÃO DE DADOS
# ==============================================================================

def inserir_registro_manual():
    """Permite a inserção manual de um registro usando st.form."""
    st.markdown("### Inserção de Novo Registro", unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="form-container">', unsafe_allow_html=True)
        
        with st.form(key="insercao_form", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                data_registro = st.date_input(
                    "Data", 
                    value=st.session_state.form_data["data"],
                    help="Selecione a data do registro"
                )
            
            with col2:
                produto = st.text_input(
                    "Produto",
                    value=st.session_state.form_data["produto"],
                    help="Digite o nome do produto"
                )
            
            with col3:
                tipo = st.selectbox(
                    "Tipo",
                    ["entrada", "saída"],
                    index=["entrada", "saída"].index(st.session_state.form_data["tipo"]),
                    help="Escolha o tipo de movimentação"
                )
            
            col4, col5, col6 = st.columns(3)
            with col4:
                quantidade = st.number_input(
                    "Quantidade",
                    min_value=0,
                    step=1,
                    value=st.session_state.form_data["quantidade"],
                    help="Digite a quantidade movimentada"
                )
            
            with col5:
                custo_unit = st.number_input(
                    "Custo Unitário",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=st.session_state.form_data["custo_unitario"],
                    help="Digite o custo unitário do produto"
                )
            
            with col6:
                preco_venda = st.number_input(
                    "Preço de Venda",
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    value=st.session_state.form_data["preco_venda"],
                    help="Digite o preço de venda (obrigatório para saídas)"
                )
            
            submit_button = st.form_submit_button("Adicionar Registro")
            
            if submit_button:
                if not produto.strip():
                    st.error("O campo 'Produto' não pode estar vazio.")
                    return
                
                if quantidade <= 0:
                    st.error("A quantidade deve ser maior que 0.")
                    return
                
                if tipo == "saída" and preco_venda <= 0:
                    st.error("O 'Preço de Venda' deve ser maior que 0 para saídas.")
                    return
                
                if tipo == "entrada" and custo_unit <= 0:
                    st.error("O 'Custo Unitário' deve ser maior que 0 para entradas.")
                    return
                
                # Validar Custo Unitário para entradas do mesmo produto
                produto = produto.lower().strip()
                entradas_produto = st.session_state.df[
                    (st.session_state.df["Produto"] == produto) & 
                    (st.session_state.df["Tipo"] == "entrada")
                ]
                if not entradas_produto.empty:
                    custo_existente = entradas_produto["Custo Unitário"].iloc[0]
                    if round(custo_unit, 2) != round(custo_existente, 2):
                        st.error(
                            f"O produto '{produto}' já possui entradas com Custo Unitário R$ {custo_existente:.2f}. "
                            f"Não é permitido registrar com um valor diferente (R$ {custo_unit:.2f})."
                        )
                        return
                
                # Validar se há estoque suficiente para saídas
                if tipo == "saída":
                    saldo_atual = calcular_saldo(st.session_state.df)
                    if produto in saldo_atual.index:
                        saldo_qty = saldo_atual.loc[produto, "Saldo Atual"]
                        if quantidade > saldo_qty:
                            st.error(
                                f"Estoque insuficiente para o produto '{produto}'. "
                                f"Saldo atual: {saldo_qty}, Quantidade solicitada: {quantidade}."
                            )
                            return
                    else:
                        st.error(f"O produto '{produto}' não possui entradas registradas.")
                        return
                
                registro = {
                    "Data": data_registro,
                    "Produto": produto,
                    "Tipo": tipo,
                    "Quantidade": quantidade,
                    "Custo Unitário": custo_unit,
                    "Preço de Venda": preco_venda
                }
                st.session_state.df = pd.concat(
                    [st.session_state.df, pd.DataFrame([registro])],
                    ignore_index=True
                )
                # Resetar valores padrão do formulário
                st.session_state.form_data = {
                    "data": date.today(),
                    "produto": "",
                    "tipo": "entrada",
                    "quantidade": 0,
                    "custo_unitario": 0.0,
                    "preco_venda": 0.0
                }
                st.success("Registro adicionado com sucesso!")
        
        st.markdown('</div>', unsafe_allow_html=True)

@st.cache_data
def calcular_saldo(df):
    """Calcula o resumo do estoque por produto."""
    try:
        logger.info("Iniciando cálculo do saldo")
        
        # Verificar saídas inválidas
        saidas_invalidas = df[(df["Tipo"] == "saída") & (df["Preço de Venda"] <= 0)]
        if not saidas_invalidas.empty:
            st.warning(
                "Existem saídas com 'Preço de Venda' igual a 0. "
                "Por favor, corrija os registros para cálculos precisos."
            )
        
        # Calcular quantidades de entradas e saídas
        entradas_qty = df[df["Tipo"] == "entrada"].groupby("Produto")["Quantidade"].sum()
        saidas_qty = df[df["Tipo"] == "saída"].groupby("Produto")["Quantidade"].sum()
        saldo_qty = entradas_qty.subtract(saidas_qty, fill_value=0)
        
        # Calcular valores de entradas
        df_entradas = df[df["Tipo"] == "entrada"].copy()
        df_entradas["Valor Entradas"] = df_entradas["Quantidade"] * df_entradas["Custo Unitário"]
        entradas_valor = df_entradas.groupby("Produto")["Valor Entradas"].sum()
        
        # Calcular valores de saídas
        df_saidas = df[df["Tipo"] == "saída"].copy()
        df_saidas["Valor Saídas"] = df_saidas["Quantidade"] * df_saidas["Preço de Venda"]
        saidas_valor = df_saidas.groupby("Produto")["Valor Saídas"].sum()
        
        # Calcular custo médio e lucro
        custo_medio = df[df["Tipo"] == "entrada"].groupby("Produto")["Custo Unitário"].mean()
        df_saidas = df_saidas.join(custo_medio.rename("Custo Médio"), on="Produto")
        df_saidas["Custo Médio"] = df_saidas["Custo Médio"].fillna(0.0)
        df_saidas["Lucro"] = df_saidas["Quantidade"] * (df_saidas["Preço de Venda"] - df_saidas["Custo Médio"])
        lucro = df_saidas.groupby("Produto")["Lucro"].sum().fillna(0)
        
        # Criar DataFrame de saldo
        saldo = pd.DataFrame({
            "Entradas": entradas_qty,
            "Saídas": saidas_qty,
            "Saldo Atual": saldo_qty,
            "Valor Entradas": entradas_valor,
            "Valor Saídas": saidas_valor,
            "Lucro": lucro
        }).fillna(0)
        
        # Formatar valores monetários
        saldo["Valor Entradas"] = saldo["Valor Entradas"].apply(lambda x: f"R$ {x:,.2f}")
        saldo["Valor Saídas"] = saldo["Valor Saídas"].apply(lambda x: f"R$ {x:,.2f}")
        saldo["Lucro"] = saldo["Lucro"].apply(lambda x: f"R$ {x:,.2f}")
        
        logger.info("Cálculo do saldo concluído")
        return saldo.sort_values("Saldo Atual", ascending=False)
    
    except Exception as e:
        logger.error(f"Erro ao calcular saldo: {str(e)}")
        st.error("Ocorreu um erro ao calcular o saldo. Verifique os dados inseridos.")
        return pd.DataFrame()

# ==============================================================================
# FUNÇÕES DE VISUALIZAÇÃO
# ==============================================================================

def create_bar_chart(data, x, y, title, labels, barmode="group"):
    """Cria um gráfico de barras com Plotly."""
    if data.empty:
        st.warning("Nenhum dado disponível para o gráfico.")
        return
    data_clean = data.copy()
    for col in y:
        if data[col].dtype == object and "R$" in str(data[col].iloc[0]):
            data_clean[col] = data[col].str.replace("R$ ", "").str.replace(",", "").astype(float)
    
    fig = px.bar(
        data_clean.reset_index(),
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
    """Gera um gráfico de barras comparativo de quantidades."""
    create_bar_chart(
        saldo,
        x="Produto",
        y=["Entradas", "Saídas"],
        title="Comparativo de Quantidades (Entradas x Saídas)",
        labels={"value": "Quantidade", "variable": "Tipo"}
    )

def grafico_barra_valor(saldo):
    """Gera um gráfico de barras comparativo de valores."""
    create_bar_chart(
        saldo,
        x="Produto",
        y=["Valor Entradas", "Valor Saídas"],
        title="Comparativo de Valores (Entradas x Saídas)",
        labels={"value": "Valor (R$)", "variable": "Tipo"}
    )

def grafico_linha_evolucao(produto, df_produto, agregacao="Diária"):
    """Gera um gráfico de linha com a evolução da quantidade."""
    if df_produto.empty:
        st.warning("Nenhum dado disponível para o gráfico.")
        return
    
    df_resumo = df_produto.copy()
    df_resumo["Data"] = pd.to_datetime(df_resumo["Data"])
    
    if agregacao == "Semanal":
        df_resumo["Data"] = df_resumo["Data"].dt.to_period("W").apply(lambda r: r.start_time)
    elif agregacao == "Mensal":
        df_resumo["Data"] = df_resumo["Data"].dt.to_period("M").apply(lambda r: r.start_time)
    
    df_resumo["Quantidade"] = df_resumo.apply(
        lambda row: row["Quantidade"] if row["Tipo"] == "entrada" else -row["Quantidade"], axis=1
    )
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
    if principais.empty:
        st.warning("Nenhum dado disponível para exibir os principais produtos.")
        return
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
    try:
        data_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        nome_arquivo = f"Relatorio_Controle_Mercadorias_{data_atual}.xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            caminho_arquivo = tmp.name
        with pd.ExcelWriter(caminho_arquivo, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Dados")
            saldo.to_excel(writer, sheet_name="Resumo")
        return caminho_arquivo, nome_arquivo
    except Exception as e:
        logger.error(f"Erro ao exportar relatório: {str(e)}")
        st.error("Erro ao gerar o relatório. Tente novamente.")
        return None, None

def formatar_tabela_resumo(saldo):
    """Formata a tabela de resumo do estoque."""
    def color_lucro(val):
        try:
            val_float = float(val.replace("R$ ", "").replace(",", ""))
            return "color: red" if val_float < 0 else "color: green" if val_float > 0 else "color: black"
        except:
            return "color: black"
    
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
    """Configura os filtros na sidebar."""
    st.sidebar.header("Filtros")
    if df.empty:
        st.sidebar.info("Nenhum dado para filtrar.")
        return df
    
    datas = pd.to_datetime(df["Data"]).dropna()
    data_min, data_max = min(datas, default=date.today()), max(datas, default=date.today())
    intervalo = st.sidebar.date_input(
        "Período",
        value=[data_min, data_max],
        help="Selecione o intervalo de datas para filtrar"
    )
    
    df_filtrado = df
    if isinstance(intervalo, (list, tuple)) and len(intervalo) == 2:
        inicio, fim = intervalo
        if inicio > fim:
            st.error("A data inicial não pode ser posterior à data final.")
            return df
        df_filtrado = df_filtrado[
            (pd.to_datetime(df_filtrado["Data"]) >= pd.to_datetime(inicio)) &
            (pd.to_datetime(df_filtrado["Data"]) <= pd.to_datetime(fim))
        ]
    
    produtos_disp = sorted(df_filtrado["Produto"].unique())
    produtos_sel = st.sidebar.multiselect(
        "Produtos",
        options=produtos_disp,
        default=produtos_disp,
        help="Selecione os produtos a serem exibidos"
    )
    if produtos_sel:
        df_filtrado = df_filtrado[df_filtrado["Produto"].isin(produtos_sel)]
    
    tipo_mov = st.sidebar.multiselect(
        "Tipo de Movimentação",
        ["entrada", "saída"],
        default=["entrada", "saída"],
        help="Selecione os tipos de movimentação"
    )
    if tipo_mov:
        df_filtrado = df_filtrado[df_filtrado["Tipo"].isin(tipo_mov)]
    
    return df_filtrado

def configurar_limpeza_dados():
    """Configura a seção de limpeza de dados na sidebar."""
    st.sidebar.header("Limpar Dados")
    st.session_state.confirmar_limpeza = st.sidebar.checkbox(
        "Confirmar limpeza dos dados",
        value=st.session_state.confirmar_limpeza
    )
    
    if st.sidebar.button("Limpar Dados"):
        if st.session_state.confirmar_limpeza:
            st.session_state.df = pd.DataFrame(
                columns=["Data", "Produto", "Tipo", "Quantidade", "Custo Unitário", "Preço de Venda"]
            )
            st.session_state.form_data = {
                "data": date.today(),
                "produto": "",
                "tipo": "entrada",
                "quantidade": 0,
                "custo_unitario": 0.0,
                "preco_venda": 0.0
            }
            st.session_state.confirmar_limpeza = False
            st.sidebar.success("Dados limpos com sucesso!")
        else:
            st.sidebar.warning("Marque a caixa de confirmação para limpar os dados.")

def configurar_analise_detalhada():
    """Configura a seção de análise detalhada por produto."""
    st.sidebar.header("Análise Detalhada por Produto")
    produtos_analise = sorted(st.session_state.df["Produto"].unique().tolist())
    produto_escolhido = st.sidebar.selectbox(
        "Selecione um produto",
        options=["Nenhum"] + produtos_analise,
        help="Escolha um produto para análise detalhada"
    )
    agregacao = st.sidebar.selectbox(
        "Agregação Temporal",
        ["Diária", "Semanal", "Mensal"],
        help="Selecione o nível de agregação temporal"
    )
    return produto_escolhido, agregacao

def aggregate_movimentacoes(df):
    """Agrega os dados de movimentações por Produto, Tipo e Custo Unitário, tratando saídas corretamente."""
    if df.empty:
        return df
    
    # Ajustar quantidades para saídas (negativas)
    df = df.copy()
    df["Quantidade Ajustada"] = df.apply(
        lambda row: row["Quantidade"] if row["Tipo"] == "entrada" else -row["Quantidade"], axis=1
    )
    
    # Agrupar por Produto, Tipo e Custo Unitário
    grouped = df.groupby(["Produto", "Tipo", "Custo Unitário"]).agg({
        "Quantidade Ajustada": "sum",  # Somar quantidades ajustadas
        "Data": "max",                 # Pegar a data mais recente
        "Preço de Venda": "last"       # Pegar o último preço de venda
    }).reset_index()
    
    # Renomear coluna para manter consistência
    grouped = grouped.rename(columns={"Quantidade Ajustada": "Quantidade"})
    
    # Reordenar colunas
    return grouped[["Data", "Produto", "Tipo", "Quantidade", "Custo Unitário", "Preço de Venda"]]

def exibir_dados_movimentacoes(df):
    """Exibe a tabela de movimentações com agregação por produto e custo unitário."""
    st.subheader("Dados de Movimentações")
    if df.empty:
        st.info("Nenhum dado inserido até o momento.")
        return
    
    # Agregar os dados antes de exibir
    df_aggregated = aggregate_movimentacoes(df)
    
    # Criar uma cópia para formatação
    df_display = df_aggregated.copy()
    df_display["Custo Unitário"] = df_display["Custo Unitário"].apply(lambda x: f"R$ {x:,.2f}")
    df_display["Preço de Venda"] = df_display["Preço de Venda"].apply(lambda x: f"R$ {x:,.2f}")
    
    def color_tipo(val):
        color = '#E3F2FD' if val == "entrada" else '#FFEBEE'
        return f'background-color: {color}'
    
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
    """Exibe o resumo do estoque e gráficos."""
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
    
    # Cálculos globais
    total_entradas_qty = df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"].sum()
    total_saidas_qty = df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"].sum()
    total_valor_entradas = (
        df_filtrado[df_filtrado["Tipo"]=="entrada"]["Quantidade"] *
        df_filtrado[df_filtrado["Tipo"]=="entrada"]["Custo Unitário"]
    ).sum()
    total_valor_saidas = (
        df_filtrado[df_filtrado["Tipo"]=="saída"]["Quantidade"] *
        df_filtrado[df_filtrado["Tipo"]=="saída"]["Preço de Venda"]
    ).sum()
    
    # Cálculo do lucro global
    df_saidas = df_filtrado[df_filtrado["Tipo"] == "saída"].copy()
    custo_medio = df_filtrado[df_filtrado["Tipo"] == "entrada"].groupby("Produto")["Custo Unitário"].mean()
    df_saidas = df_saidas.join(custo_medio.rename("Custo Médio"), on="Produto")
    df_saidas["Custo Médio"] = df_saidas["Custo Médio"].fillna(0.0)
    df_saidas["Lucro"] = df_saidas["Quantidade"] * (df_saidas["Preço de Venda"] - df_saidas["Custo Médio"])
    lucro_global = df_saidas["Lucro"].sum()
    
    st.subheader("Resumo Global")
    col_res1, col_res2, col_res3, col_res4, col_res5 = st.columns(5)
    col_res1.metric("Entradas (Qtd)", value=int(total_entradas_qty))
    col_res2.metric("Saídas (Qtd)", value=int(total_saidas_qty))
    col_res3.metric("Valor Entradas", value=f"R$ {total_valor_entradas:,.2f}")
    col_res4.metric("Valor Saídas", value=f"R$ {total_valor_saidas:,.2f}")
    
    lucro_label = "Lucro (Perda)" if lucro_global < 0 else "Lucro"
    lucro_value = abs(lucro_global) if lucro_global < 0 else lucro_global
    delta = f"-R$ {abs(lucro_global):,.2f}" if lucro_global < 0 else f"+R$ {lucro_global:,.2f}"
    delta_color = "inverse" if lucro_global < 0 else "normal"
    col_res5.metric(lucro_label, value=f"R$ {lucro_value:,.2f}", delta=delta, delta_color=delta_color)
    
    if st.button("Exportar Relatório para Excel"):
        with st.spinner("Gerando relatório..."):
            caminho, nome_arquivo = exportar_relatorio(df_filtrado, saldo)
            if caminho and nome_arquivo:
                with open(caminho, "rb") as file:
                    st.download_button(
                        label="Download do Relatório",
                        data=file,
                        file_name=nome_arquivo,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                os.unlink(caminho)
                st.success("Relatório gerado com sucesso!")

def exibir_analise_detalhada(produto_escolhido, agregacao):
    """Exibe a análise detalhada por produto."""
    if produto_escolhido == "Nenhum":
        return
    
    df_prod = st.session_state.df[st.session_state.df["Produto"] == produto_escolhido]
    if df_prod.empty:
        st.info(f"Nenhum dado disponível para o produto {produto_escolhido}.")
        return
    
    st.subheader(f"Análise Detalhada - {produto_escolhido}")
    st.dataframe(df_prod, use_container_width=True)
    grafico_linha_evolucao(produto_escolhido, df_prod, agregacao)

def exibir_principais_produtos(df_filtrado):
    """Exibe os principais produtos por saldo."""
    st.subheader("Principais Produtos por Saldo")
    grafico_top_produtos(df_filtrado)

# ==============================================================================
# EXECUÇÃO PRINCIPAL
# ==============================================================================

st.title("📦 Sistema de Controle de Mercadorias 📦")

# Configuração da interface
inserir_registro_manual()
configurar_limpeza_dados()
df_filtrado = configurar_filtros(st.session_state.df)
produto_escolhido, agregacao = configurar_analise_detalhada()

# Exibição dos dados
exibir_dados_movimentacoes(st.session_state.df)
exibir_resumo_estoque(df_filtrado)
exibir_analise_detalhada(produto_escolhido, agregacao)
exibir_principais_produtos(df_filtrado)
