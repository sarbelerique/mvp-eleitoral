"""MVP — Diagnóstico eleitoral (Streamlit).

Rodar:  streamlit run app.py
"""

import io
import json
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

from engine import COLUNAS_OBRIGATORIAS, diagnosticar, oportunidades, resumo, validar

st.set_page_config(page_title="Diagnóstico eleitoral", page_icon="🗳️", layout="wide")

CORES = {"Alto potencial": "#1D9E75", "Consolidar": "#378ADD", "Solo difícil": "#B4B2A9"}


def _norm(s):
    """Normaliza nome de município para casar com o geojson (maiúsculas, sem acento)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.upper().strip()


@st.cache_data
def carregar_geojson(caminho="data/rj_municipios.geojson"):
    with open(caminho, encoding="utf-8") as fh:
        gj = json.load(fh)
    for f in gj["features"]:
        f["properties"]["norm"] = _norm(f["properties"]["name"])
    return gj, {f["properties"]["norm"] for f in gj["features"]}

st.title("Diagnóstico eleitoral")
st.caption(
    "Onde o candidato é forte, onde a esquerda vota mas não nele (voto órfão), "
    "e onde não vale gastar energia."
)

with st.sidebar:
    st.header("1. Dados")
    st.markdown(
        "Envie um **CSV ou Excel** com uma linha por região e estas colunas:\n\n"
        "`regiao` · `votos_candidato` · `votos_validos` · `votos_esquerda`\n\n"
        "*(votos_esquerda = soma dos partidos de esquerda, incluindo o candidato)*"
    )
    arquivo = st.file_uploader("Arquivo", type=["csv", "xlsx"])
    DATASETS = {
        "Exemplo (ilustrativo)": "data/exemplo.csv",
        "Fed · Tarcísio Motta": "data/dep_tarcisio_motta.csv",
        "Fed · Talíria Petrone": "data/dep_taliria_petrone.csv",
        "Fed · Chico Alencar": "data/dep_chico_alencar.csv",
        "Fed · Glauber Braga": "data/dep_glauber_braga.csv",
        "Fed · Henrique Vieira": "data/dep_henrique_vieira.csv",
        "Est · Renata Souza": "data/dep_renata_souza.csv",
        "Est · Flávio Serafini": "data/dep_flavio_serafini.csv",
        "Est · Dani Monteiro": "data/dep_dani_monteiro.csv",
        "Est · Mônica Francisco": "data/dep_monica_francisco.csv",
        "Est · Benny Briolly": "data/dep_benny_briolly.csv",
        "Est · Josemar Carvalho": "data/dep_josemar_carvalho.csv",
    }
    dataset = st.selectbox(
        "Ou use um deputado do PSOL (RJ 2022)", list(DATASETS),
        index=0, disabled=arquivo is not None,
    )
    st.divider()
    st.header("2. Sobre os limiares")
    st.markdown(
        "- **Solo difícil**: esquerda < 15% dos válidos\n"
        "- **Alto potencial**: mais de 60% do voto de esquerda não é do candidato\n"
        "- **Consolidar**: o resto"
    )

if arquivo is not None:
    df = pd.read_csv(arquivo) if arquivo.name.endswith(".csv") else pd.read_excel(arquivo)
else:
    df = pd.read_csv(DATASETS[dataset])
    if dataset.startswith(("Fed ·", "Est ·")):
        cargo = "Deputado Federal" if dataset.startswith("Fed") else "Deputado Estadual"
        st.info(
            f"Dados **reais do TSE** — {dataset[6:]} (PSOL, {cargo}, RJ 2022), por município. "
            "`votos_esquerda` = PDT, PT, PSTU, REDE, PCB, PCO, PSB, PV, PSOL e PCdoB "
            "(nominais + legenda)."
        )
    else:
        st.info("Mostrando **dados de exemplo** (ilustrativos). Envie seu arquivo na barra lateral.")

problemas = validar(df)
erros = [p for p in problemas if not p.startswith("Atenção")]
avisos = [p for p in problemas if p.startswith("Atenção")]
for a in avisos:
    st.warning(a)
if erros:
    for e in erros:
        st.error(e)
    st.stop()

d = diagnosticar(df)
r = resumo(d)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Votos do candidato", f"{r['total_votos_candidato']:,}".replace(",", "."))
c2.metric("Voto de esquerda órfão", f"{r['total_voto_orfao']:,}".replace(",", "."))
c3.metric("Regiões de alto potencial", r["regioes_alto_potencial"])
c4.metric("Regiões a consolidar", r["regioes_consolidar"])

st.divider()

# --- Mapa coroplético (só quando as regiões são municípios do RJ) ---
gj, nomes_geo = carregar_geojson()
d["_norm"] = d["regiao"].map(_norm)
if d["_norm"].isin(nomes_geo).mean() >= 0.8:
    st.subheader("Mapa por município")
    metrica = st.radio(
        "Colorir por", ["Voto órfão", "% não capturado", "Prioridade"],
        horizontal=True, key="mapa_metrica",
    )
    dm = d[d["_norm"].isin(nomes_geo)]
    comuns = dict(
        geojson=gj, locations="_norm", featureidkey="properties.norm",
        hover_name="regiao",
        hover_data={"_norm": False, "votos_candidato": ":,", "voto_orfao": ":,"},
    )
    if metrica == "Prioridade":
        fig_mapa = px.choropleth(
            dm, color="prioridade", color_discrete_map=CORES,
            category_orders={"prioridade": ["Alto potencial", "Consolidar", "Solo difícil"]},
            **comuns,
        )
    else:
        col = "voto_orfao" if metrica == "Voto órfão" else "pct_nao_capturado"
        fig_mapa = px.choropleth(dm, color=col, color_continuous_scale="YlOrRd", **comuns)
        fig_mapa.update_layout(coloraxis_colorbar_title_text="")
    fig_mapa.update_geos(fitbounds="locations", visible=False)
    fig_mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520, legend_title_text="")
    st.plotly_chart(fig_mapa, width="stretch")
    st.caption(
        "Áreas mais escuras = mais voto de esquerda que **não** foi ao candidato. "
        "O maior reservatório absoluto costuma ser a capital."
    )
    st.divider()

col_esq, col_dir = st.columns([3, 2])

with col_esq:
    st.subheader("Diagnóstico por região")
    exibicao = d[[
        "regiao", "votos_candidato", "pct_candidato", "pct_esquerda",
        "voto_orfao", "pct_nao_capturado", "prioridade",
    ]].rename(columns={
        "regiao": "Região",
        "votos_candidato": "Votos",
        "pct_candidato": "% candidato",
        "pct_esquerda": "% esquerda",
        "voto_orfao": "Voto órfão",
        "pct_nao_capturado": "% não capturado",
        "prioridade": "Prioridade",
    })
    st.dataframe(
        exibicao.style.format({
            "Votos": "{:,.0f}", "Voto órfão": "{:,.0f}",
            "% candidato": "{:.1%}", "% esquerda": "{:.1%}", "% não capturado": "{:.1%}",
        }),
        width="stretch", hide_index=True,
    )

with col_dir:
    st.subheader("Onde está o voto órfão")
    fig = px.bar(
        d, x="voto_orfao", y="regiao", color="prioridade",
        color_discrete_map=CORES, orientation="h",
        labels={"voto_orfao": "Voto de esquerda órfão", "regiao": "", "prioridade": "Prioridade"},
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, legend_title_text="")
    st.plotly_chart(fig, width="stretch")

st.subheader("Força do candidato vs. força da esquerda")
fig2 = px.scatter(
    d, x="pct_esquerda", y="pct_candidato", size="votos_validos",
    color="prioridade", color_discrete_map=CORES, hover_name="regiao",
    labels={"pct_esquerda": "% da esquerda na região", "pct_candidato": "% do candidato"},
)
fig2.update_xaxes(tickformat=".0%")
fig2.update_yaxes(tickformat=".0%")
st.plotly_chart(fig2, width="stretch")
st.caption(
    "Cada bolha é uma região (tamanho = eleitorado). Bolhas à direita e embaixo = "
    "muita esquerda, pouco candidato → alto potencial."
)

st.divider()

# --- Onde agir: alvos com melhor relação esforço/retorno ---
o = oportunidades(d)
taxa_global = o["taxa_global"].iloc[0]


def _br(n):
    return f"{n:,.0f}".replace(",", ".")


st.subheader("🎯 Onde agir para captar mais votos")
st.markdown(
    f"Regiões com **muita esquerda** onde o candidato rende **abaixo da própria média** de "
    f"captação (**{taxa_global:.1%}** dos votos de esquerda). É onde há mais espaço para crescer "
    f"num eleitorado que já existe — melhor relação esforço/retorno."
)

alvos = o[o["potencial_extra"] > 0].head(5)
if alvos.empty:
    st.success("O candidato já rende acima da própria média em toda parte — foco em consolidar.")
else:
    linhas = [
        f"1. **{row.regiao}** — capta {row.taxa_captura:.1%} da esquerda (média: {taxa_global:.0%}); "
        f"{_br(row.voto_orfao)} votos órfãos → potencial de **+{_br(row.potencial_extra)}** votos"
        for row in alvos.itertuples()
    ]
    st.markdown("\n".join(linhas))

col_a, col_b = st.columns([2, 3])
with col_a:
    st.metric(
        "Teto de crescimento (na própria média)",
        f"+{_br(o['potencial_extra'].sum())} votos",
        help="Soma do potencial de todas as regiões onde ele rende abaixo da média. "
        "Sinal relativo de priorização — o voto órfão é de outros candidatos e não migra sozinho.",
    )
with col_b:
    top = o.head(12)
    fig3 = px.bar(
        top, x="potencial_extra", y="regiao", orientation="h",
        color="potencial_extra", color_continuous_scale="Tealgrn",
        labels={"potencial_extra": "Potencial de votos a ganhar", "regiao": ""},
    )
    fig3.update_layout(
        yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=0, b=0), height=380,
    )
    st.plotly_chart(fig3, width="stretch")

st.caption(
    "⚠️ Priorização **relativa**: mede onde há esquerda sub-aproveitada, não votos garantidos. "
    "Os redutos onde o candidato já domina (ex.: capital) saem daqui de propósito — lá o crescimento "
    "marginal é menor."
)

buffer = io.BytesIO()
o.drop(columns=["_norm"], errors="ignore").to_excel(buffer, index=False)
st.download_button(
    "⬇️ Baixar diagnóstico + onde agir (Excel)", data=buffer.getvalue(),
    file_name="diagnostico.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
