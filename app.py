"""MVP — Diagnóstico eleitoral (Streamlit).

Rodar:  streamlit run app.py
"""

import io
import json
import unicodedata

import pandas as pd
import plotly.express as px
import streamlit as st

from engine import diagnosticar, oportunidades, resumo

st.set_page_config(page_title="Diagnóstico eleitoral", page_icon="🗳️", layout="wide")

CORES = {"Alto potencial": "#1D9E75", "Consolidar": "#378ADD", "Solo difícil": "#B4B2A9"}

PRIORIDADE_DESC = {
    "Alto potencial": "muita esquerda, mas ele foi pouco votado → mais votos a conquistar",
    "Consolidar": "ele já vai bem aqui → manter e reforçar",
    "Solo difícil": "pouca esquerda na região → menor retorno",
}

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


def _norm(s):
    """Normaliza nome de município para casar com o geojson (maiúsculas, sem acento)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.upper().strip()


def _br(n):
    """Formata número inteiro no padrão brasileiro (ponto de milhar)."""
    return f"{n:,.0f}".replace(",", ".")


def nome_dep(chave):
    """Nome limpo do deputado a partir da chave do seletor (tira 'Fed · ' / 'Est · ')."""
    return chave[6:] if chave.startswith(("Fed ·", "Est ·")) else chave


@st.cache_data
def carregar_geojson(caminho="data/rj_municipios.geojson"):
    with open(caminho, encoding="utf-8") as fh:
        gj = json.load(fh)
    for f in gj["features"]:
        f["properties"]["norm"] = _norm(f["properties"]["name"])
    return gj, {f["properties"]["norm"] for f in gj["features"]}


@st.cache_data
def carregar(caminho):
    """Lê o CSV e já aplica o diagnóstico (com cache)."""
    return diagnosticar(pd.read_csv(caminho))


def leitura_automatica(nome, r, o):
    """Parágrafo-resumo em português claro para o deputado selecionado."""
    taxa = o["taxa_global"].iloc[0]
    alvos = o[o["potencial_extra"] > 0].head(3)["regiao"].tolist()
    if len(alvos) > 1:
        lugares = ", ".join(alvos[:-1]) + " e " + alvos[-1]
    else:
        lugares = alvos[0] if alvos else ""
    texto = (
        f"📌 **{nome}** somou **{_br(r['total_votos_candidato'])}** votos. "
        f"De cada 100 votos de esquerda no estado, ele levou cerca de **{taxa * 100:.0f}**. "
        f"Sobraram **{_br(r['total_voto_orfao'])}** votos de esquerda que foram para *outros* "
        f"candidatos — o estoque a conquistar."
    )
    if alvos:
        texto += f" Os melhores lugares para crescer são **{lugares}**."
    return texto


# ────────────────────────────────────────────────────────────────────────────
# Cabeçalho
# ────────────────────────────────────────────────────────────────────────────
st.title("🗳️ Diagnóstico eleitoral")
st.caption("Onde o candidato é forte, onde a esquerda vota mas não nele, e onde não vale a energia.")

with st.expander("👋 Como ler este painel (clique para abrir)"):
    st.markdown(
        "Este é um **raio-x, município por município**, de onde um candidato de esquerda é forte "
        "e onde existe **voto órfão** — pessoas que votaram na esquerda, mas em *outro* candidato. "
        "Serve para decidir **onde vale a pena investir a campanha**.\n\n"
        "- Escolha o **deputado** na barra lateral (à esquerda).\n"
        "- Navegue pelas **abas** abaixo: visão geral, mapa, onde agir, tabela e comparação.\n"
        "- Passe o mouse sobre os **números (❓)** e os gráficos para ver explicações.\n"
        "- Todos os dados são **reais, do TSE (RJ, 2022)**."
    )

# ────────────────────────────────────────────────────────────────────────────
# Barra lateral
# ────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Escolha o deputado")
    st.caption("Dados reais do TSE (PSOL, RJ 2022), por município.")
    dataset = st.selectbox(
        "Deputado", list(DATASETS), index=0, label_visibility="collapsed", key="dep_sel"
    )

    with st.expander("📖 Glossário — o que cada termo significa"):
        st.markdown(
            "- **Voto órfão**: votos que foram para a esquerda, mas para *outro* candidato — "
            "não para este.\n"
            "- **Esquerda (aqui)**: soma de PDT, PT, PSTU, REDE, PCB, PCO, PSB, PV, PSOL e PCdoB "
            "(votos nominais + de legenda).\n"
            "- **% da esquerda que não votou nele**: de todo o voto de esquerda da região, "
            "quanto *não* foi para o candidato.\n"
            "- 🟢 **Alto potencial**: " + PRIORIDADE_DESC["Alto potencial"] + "\n"
            "- 🔵 **Consolidar**: " + PRIORIDADE_DESC["Consolidar"] + "\n"
            "- ⚪ **Solo difícil**: " + PRIORIDADE_DESC["Solo difícil"]
        )

    with st.expander("⚙️ Como as regiões são classificadas"):
        st.markdown(
            "- **Solo difícil**: esquerda < 15% dos votos válidos\n"
            "- **Alto potencial**: mais de 60% do voto de esquerda *não* é do candidato\n"
            "- **Consolidar**: o resto"
        )

# ────────────────────────────────────────────────────────────────────────────
# Dados do deputado selecionado
# ────────────────────────────────────────────────────────────────────────────
d = carregar(DATASETS[dataset]).copy()
d["_norm"] = d["regiao"].map(_norm)
r = resumo(d)
o = oportunidades(d)
nome = nome_dep(dataset)

if dataset.startswith(("Fed ·", "Est ·")):
    cargo = "Deputado Federal" if dataset.startswith("Fed") else "Deputado Estadual"
    st.caption(f"Mostrando: **{nome}** — PSOL, {cargo}, RJ 2022 (dados reais do TSE).")
else:
    st.caption("Mostrando **dados de exemplo** (ilustrativos).")

# Recado principal
alvo_top = o[o["potencial_extra"] > 0].head(1)
if not alvo_top.empty:
    linha = alvo_top.iloc[0]
    st.success(
        f"🎯 **Recado principal:** o melhor lugar para {nome} buscar votos novos é "
        f"**{linha['regiao']}** — cerca de **+{_br(linha['potencial_extra'])}** votos possíveis."
    )

# ────────────────────────────────────────────────────────────────────────────
# Abas
# ────────────────────────────────────────────────────────────────────────────
tab_geral, tab_mapa, tab_agir, tab_tab, tab_comp = st.tabs(
    ["📊 Visão geral", "🗺️ Mapa", "🎯 Onde agir", "📋 Tabela", "⚖️ Comparar"]
)

# ── Visão geral ─────────────────────────────────────────────────────────────
with tab_geral:
    st.markdown(leitura_automatica(nome, r, o))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Votos do candidato", _br(r["total_votos_candidato"]),
        help="Total de votos nominais que o candidato recebeu no estado.",
    )
    c2.metric(
        "Voto de esquerda órfão", _br(r["total_voto_orfao"]),
        help="Votos que foram para partidos de esquerda, mas não para este candidato. "
        "É o 'estoque' potencial a conquistar.",
    )
    c3.metric(
        "Regiões de alto potencial", r["regioes_alto_potencial"],
        help="Municípios com muita esquerda onde ele foi pouco votado.",
    )
    c4.metric(
        "Regiões a consolidar", r["regioes_consolidar"],
        help="Municípios onde ele já vai bem e deve manter/reforçar.",
    )

    st.markdown(
        "**Legenda das cores:**  \n"
        f"🟢 **Alto potencial** — {PRIORIDADE_DESC['Alto potencial']}  \n"
        f"🔵 **Consolidar** — {PRIORIDADE_DESC['Consolidar']}  \n"
        f"⚪ **Solo difícil** — {PRIORIDADE_DESC['Solo difícil']}"
    )

    st.subheader("Força do candidato × força da esquerda")
    fig2 = px.scatter(
        d, x="pct_esquerda", y="pct_candidato", size="votos_validos",
        color="prioridade", color_discrete_map=CORES, hover_name="regiao",
        labels={
            "pct_esquerda": "% de votos de esquerda na região",
            "pct_candidato": "% de votos do candidato",
            "prioridade": "Prioridade",
        },
    )
    fig2.update_xaxes(tickformat=".0%")
    fig2.update_yaxes(tickformat=".0%")
    fig2.update_layout(legend_title_text="")
    st.plotly_chart(fig2, width="stretch")
    st.caption(
        "Cada bolha é um município (tamanho = nº de eleitores). Bolhas mais à **direita** têm "
        "muita esquerda; mais **embaixo** = o candidato foi pouco votado. Direita + embaixo = "
        "🟢 alto potencial."
    )

# ── Mapa ────────────────────────────────────────────────────────────────────
with tab_mapa:
    gj, nomes_geo = carregar_geojson()
    if d["_norm"].isin(nomes_geo).mean() >= 0.8:
        st.subheader("Mapa por município")
        rotulos = {
            "Voto órfão": "voto_orfao",
            "% da esquerda que não votou nele": "pct_nao_capturado",
            "Prioridade": "prioridade",
        }
        escolha = st.radio("Colorir o mapa por", list(rotulos), horizontal=True, key="mapa_metrica")
        col = rotulos[escolha]
        dm = d[d["_norm"].isin(nomes_geo)]
        comuns = dict(
            geojson=gj, locations="_norm", featureidkey="properties.norm",
            hover_name="regiao",
            hover_data={"_norm": False, "votos_candidato": ":,", "voto_orfao": ":,"},
        )
        if col == "prioridade":
            fig_mapa = px.choropleth(
                dm, color="prioridade", color_discrete_map=CORES,
                category_orders={"prioridade": ["Alto potencial", "Consolidar", "Solo difícil"]},
                **comuns,
            )
        else:
            fig_mapa = px.choropleth(dm, color=col, color_continuous_scale="YlOrRd", **comuns)
            fig_mapa.update_layout(coloraxis_colorbar_title_text="")
        fig_mapa.update_geos(fitbounds="locations", visible=False)
        fig_mapa.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=560, legend_title_text="")
        st.plotly_chart(fig_mapa, width="stretch")
        st.caption(
            "Áreas mais **escuras** = mais voto de esquerda que **não** foi ao candidato. "
            "O maior reservatório absoluto costuma ser a capital — mas nem sempre é onde há mais "
            "espaço para crescer (veja a aba **Onde agir**)."
        )
    else:
        st.info("O mapa está disponível apenas para dados por município do RJ.")

# ── Onde agir ───────────────────────────────────────────────────────────────
with tab_agir:
    taxa_global = o["taxa_global"].iloc[0]
    st.subheader("🎯 Onde agir para captar mais votos")
    st.markdown(
        f"Regiões com **muita esquerda** onde o candidato rende **abaixo da própria média** de "
        f"captação (**{taxa_global:.1%}** dos votos de esquerda). É onde há mais espaço para "
        f"crescer num eleitorado que já existe — melhor relação **esforço × retorno**."
    )

    alvos = o[o["potencial_extra"] > 0]
    if alvos.empty:
        st.success("O candidato já rende acima da própria média em toda parte — foco em consolidar.")
    else:
        quantos = st.slider("Quantos alvos mostrar", 5, 20, 8, key="n_alvos")
        lista = alvos.head(quantos)
        linhas = [
            f"{i}. **{row.regiao}** — leva {row.taxa_captura:.1%} da esquerda (média: "
            f"{taxa_global:.0%}); {_br(row.voto_orfao)} votos órfãos → potencial de "
            f"**+{_br(row.potencial_extra)}** votos"
            for i, row in enumerate(lista.itertuples(), start=1)
        ]
        st.markdown("\n".join(linhas))

        col_a, col_b = st.columns([2, 3])
        with col_a:
            st.metric(
                "Teto de crescimento", f"+{_br(o['potencial_extra'].sum())} votos",
                help="Soma do potencial de todas as regiões onde ele rende abaixo da média. "
                "Sinal relativo de priorização — o voto órfão é de outros candidatos e não "
                "migra sozinho.",
            )
        with col_b:
            fig3 = px.bar(
                lista, x="potencial_extra", y="regiao", orientation="h",
                color="potencial_extra", color_continuous_scale="Tealgrn",
                labels={"potencial_extra": "Votos a ganhar (potencial)", "regiao": ""},
            )
            fig3.update_layout(
                yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=0, b=0), height=380,
            )
            st.plotly_chart(fig3, width="stretch")

    st.caption(
        "⚠️ Priorização **relativa**: mede onde há esquerda sub-aproveitada, não votos garantidos. "
        "Os redutos onde o candidato já domina (ex.: a capital) saem daqui de propósito — lá o "
        "crescimento marginal é menor."
    )

# ── Tabela ──────────────────────────────────────────────────────────────────
with tab_tab:
    st.subheader("Tabela por município")
    f1, f2, f3 = st.columns([1, 1, 2])
    so_alto = f1.checkbox("Só alto potencial", help="Mostrar apenas os municípios de alto potencial.")
    topn = f2.slider("Top N (por voto órfão)", 5, len(d), len(d))
    busca = f3.text_input("🔎 Buscar município", placeholder="ex.: Niterói")

    t = d.copy()
    if so_alto:
        t = t[t["prioridade"] == "Alto potencial"]
    if busca:
        t = t[t["regiao"].str.contains(busca, case=False, na=False)]
    t = t.head(topn)

    exibicao = t[[
        "regiao", "votos_candidato", "pct_candidato", "pct_esquerda",
        "voto_orfao", "pct_nao_capturado", "prioridade",
    ]].rename(columns={
        "regiao": "Município",
        "votos_candidato": "Votos dele",
        "pct_candidato": "% do candidato",
        "pct_esquerda": "% de esquerda",
        "voto_orfao": "Voto órfão",
        "pct_nao_capturado": "% da esquerda que não votou nele",
        "prioridade": "Prioridade",
    })
    st.dataframe(
        exibicao.style.format({
            "Votos dele": "{:,.0f}", "Voto órfão": "{:,.0f}",
            "% do candidato": "{:.1%}", "% de esquerda": "{:.1%}",
            "% da esquerda que não votou nele": "{:.1%}",
        }),
        width="stretch", hide_index=True,
    )
    st.caption(f"{len(t)} de {len(d)} municípios exibidos.")

    buffer = io.BytesIO()
    o.drop(columns=["_norm"], errors="ignore").to_excel(buffer, index=False)
    st.download_button(
        "⬇️ Baixar tudo (Excel)", data=buffer.getvalue(),
        file_name=f"diagnostico_{_norm(nome).lower().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ── Comparar ────────────────────────────────────────────────────────────────
with tab_comp:
    st.subheader("⚖️ Comparar dois deputados")
    st.caption("Veja onde cada um é mais forte e onde a esquerda está 'dividida' entre eles.")

    deps = [k for k in DATASETS if k != "Exemplo (ilustrativo)"]
    cc1, cc2 = st.columns(2)
    da = cc1.selectbox("Deputado A", deps, index=0, key="cmpA")
    db = cc2.selectbox("Deputado B", deps, index=1, key="cmpB")

    if da == db:
        st.warning("Escolha dois deputados diferentes para comparar.")
    else:
        na, nb = nome_dep(da), nome_dep(db)
        A = carregar(DATASETS[da])[["regiao", "votos_candidato"]].rename(columns={"votos_candidato": "A"})
        B = carregar(DATASETS[db])[["regiao", "votos_candidato"]].rename(columns={"votos_candidato": "B"})
        m = A.merge(B, on="regiao")

        lidera_a = int((m["A"] > m["B"]).sum())
        lidera_b = int((m["B"] > m["A"]).sum())
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric(f"Votos · {na}", _br(m["A"].sum()))
        mc2.metric(f"Votos · {nb}", _br(m["B"].sum()))
        mc3.metric("Municípios em que cada um lidera", f"{lidera_a}  ×  {lidera_b}",
                   help=f"{lidera_a} municípios onde {na} teve mais votos; {lidera_b} onde {nb} teve mais.")

        mx = int(max(m["A"].max(), m["B"].max()))
        figc = px.scatter(
            m, x="A", y="B", hover_name="regiao",
            labels={"A": f"Votos de {na}", "B": f"Votos de {nb}"},
        )
        figc.add_shape(type="line", x0=0, y0=0, x1=mx, y1=mx, line=dict(dash="dash", color="gray"))
        figc.update_layout(height=480)
        st.plotly_chart(figc, width="stretch")
        st.caption(
            f"Cada ponto é um município. **Acima** da linha → {nb} teve mais votos ali; "
            f"**abaixo** → {na}. Pontos longe da linha são redutos de um deles; pontos sobre a "
            "linha = a esquerda se dividiu igualmente entre os dois."
        )
