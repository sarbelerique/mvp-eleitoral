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

# No celular: faz as colunas quebrarem em 2 por linha (ex.: métricas 2x2) e ajusta fontes.
st.markdown(
    """
    <style>
    @media (max-width: 640px) {
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
        [data-testid="stHorizontalBlock"] > [data-testid="column"] {
            min-width: calc(50% - 0.5rem) !important;
            flex: 1 1 calc(50% - 0.5rem) !important;
        }
        [data-testid="stMetricValue"] { font-size: 1.35rem; }
        [data-testid="stMetricLabel"] { font-size: 0.8rem; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CORES = {"Alto potencial": "#1D9E75", "Consolidar": "#378ADD", "Solo difícil": "#B4B2A9"}

PRIORIDADE_DESC = {
    "Alto potencial": "muita esquerda, mas ele foi pouco votado → mais votos a conquistar",
    "Consolidar": "ele já vai bem aqui → manter e reforçar",
    "Solo difícil": "pouca esquerda na região → menor retorno",
}

DEPUTADOS = {
    "Federal": {
        "Chico Alencar": "data/dep_chico_alencar.csv",
        "Glauber Braga": "data/dep_glauber_braga.csv",
        "Henrique Vieira": "data/dep_henrique_vieira.csv",
        "Talíria Petrone": "data/dep_taliria_petrone.csv",
        "Tarcísio Motta": "data/dep_tarcisio_motta.csv",
    },
    "Estadual": {
        "Benny Briolly": "data/dep_benny_briolly.csv",
        "Dani Monteiro": "data/dep_dani_monteiro.csv",
        "Flávio Serafini": "data/dep_flavio_serafini.csv",
        "Josemar Carvalho": "data/dep_josemar_carvalho.csv",
        "Mônica Francisco": "data/dep_monica_francisco.csv",
        "Renata Souza": "data/dep_renata_souza.csv",
        "Yuri Moura": "data/dep_yuri_moura.csv",
    },
}

# Vereadores (PSOL, RJ 2024): análise por ZONA eleitoral dentro do município deles.
VEREADORES = {
    "Rick Azevedo": {"csv": "data/ver_zona_rick_azevedo.csv", "municipio": "Rio de Janeiro"},
    "Monica Benicio": {"csv": "data/ver_zona_monica_benicio.csv", "municipio": "Rio de Janeiro"},
    "William Siri": {"csv": "data/ver_zona_william_siri.csv", "municipio": "Rio de Janeiro"},
    "Thais Ferreira": {"csv": "data/ver_zona_thais_ferreira.csv", "municipio": "Rio de Janeiro"},
    "Luciana Boiteux": {"csv": "data/ver_zona_luciana_boiteux.csv", "municipio": "Rio de Janeiro"},
    "Paulo Pinheiro": {"csv": "data/ver_zona_paulo_pinheiro.csv", "municipio": "Rio de Janeiro"},
    "Clarice Chacon": {"csv": "data/ver_zona_clarice_chacon.csv", "municipio": "Rio de Janeiro"},
    "Professor Tulio": {"csv": "data/ver_zona_professor_tulio.csv", "municipio": "Niterói"},
    "Benny Briolly": {"csv": "data/ver_zona_benny_briolly.csv", "municipio": "Niterói"},
    "Júlia Casamasso": {"csv": "data/ver_zona_julia_casamasso.csv", "municipio": "Petrópolis"},
}

# Referência do eleitorado de esquerda por município (Dep. Estadual 2022) p/ a projeção.
REF_ESTADUAL = "data/dep_yuri_moura.csv"


def _norm(s):
    """Normaliza nome de município para casar com o geojson (maiúsculas, sem acento)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return s.upper().strip()


def _br(n):
    """Formata número inteiro no padrão brasileiro (ponto de milhar)."""
    return f"{n:,.0f}".replace(",", ".")


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


@st.cache_data
def carregar_tendencia(caminho="data/tendencia_federal.csv"):
    """Variação da fatia de esquerda por município, 2018→2022 (Dep. Federal)."""
    t = pd.read_csv(caminho)
    t["_norm"] = t["regiao"].map(_norm)
    return t


def leitura_automatica(nome, r, o, escopo="no estado", unidade_pl="regiões"):
    """Parágrafo-resumo em português claro para o candidato selecionado."""
    taxa = o["taxa_global"].iloc[0]
    alvos = o[o["potencial_extra"] > 0].head(3)["regiao"].tolist()
    if len(alvos) > 1:
        lugares = ", ".join(alvos[:-1]) + " e " + alvos[-1]
    else:
        lugares = alvos[0] if alvos else ""
    texto = (
        f"📌 **{nome}** somou **{_br(r['total_votos_candidato'])}** votos. "
        f"De cada 100 votos de esquerda {escopo}, ele levou cerca de **{taxa * 100:.0f}**. "
        f"Sobraram **{_br(r['total_voto_orfao'])}** votos de esquerda que foram para *outros* "
        f"candidatos — o estoque a conquistar."
    )
    if alvos:
        texto += f" As melhores {unidade_pl} para crescer são **{lugares}**."
    return texto


COLS_REDES = [
    "Instagram", "Seguidores IG", "TikTok", "Seguidores TikTok",
    "X (Twitter)", "Seguidores X", "Engajamento médio (%)", "Observações",
]


def carregar_redes(caminho="data/redes.csv"):
    """Dados de redes sociais (preenchidos à mão pela equipe). Colunas vazias se não houver.

    Lê tudo como texto (dtype=str) de propósito: se uma coluna tiver números só em
    algumas linhas (ex.: 'Seguidores X'), o pandas a leria como float e a mistura
    float+texto quebraria a serialização Arrow do st.data_editor no servidor.
    """
    try:
        return pd.read_csv(caminho, dtype=str).fillna("")
    except FileNotFoundError:
        return pd.DataFrame(columns=["Candidato", *COLS_REDES])


def tabela_comparativa():
    """Uma linha por candidato com os números eleitorais mais significativos + redes sociais."""
    linhas = []
    for cargo, deps in DEPUTADOS.items():
        for nm, caminho in deps.items():
            dd = carregar(caminho)
            oo = oportunidades(dd)
            alvos = oo[oo["potencial_extra"] > 0]
            linhas.append({
                "Candidato": nm,
                "Cargo": cargo,
                "Votos": int(dd["votos_candidato"].sum()),
                "% capta esquerda": round(oo["taxa_global"].iloc[0] * 100, 1),
                "Voto órfão": int(dd["voto_orfao"].sum()),
                "Reduto (mais votos)": dd.loc[dd["votos_candidato"].idxmax(), "regiao"],
                "Melhor alvo p/ crescer": alvos.iloc[0]["regiao"] if not alvos.empty else "—",
                "Regiões alto potencial": int((dd["prioridade"] == "Alto potencial").sum()),
            })
    base = pd.DataFrame(linhas)
    redes = carregar_redes()
    base = base.merge(redes, on="Candidato", how="left")
    for c in COLS_REDES:
        if c not in base.columns:
            base[c] = ""
    base["Seguidores IG"] = pd.to_numeric(base["Seguidores IG"], errors="coerce").astype("Int64")
    texto = [c for c in COLS_REDES if c != "Seguidores IG"]
    base[texto] = base[texto].fillna("")
    return base


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
    st.header("Escolha o candidato")
    cargo = st.radio("Cargo", ["Federal", "Estadual", "Vereador"], horizontal=True, key="cargo_sel")
    if cargo == "Vereador":
        nome = st.selectbox("Vereador(a)", sorted(VEREADORES, key=_norm), key="ver_sel")
        st.caption("Vereadores do PSOL (RJ 2024) — análise por **zona eleitoral** da cidade.")
    else:
        nome = st.selectbox("Deputado", sorted(DEPUTADOS[cargo], key=_norm), key="dep_sel")
        st.caption("Deputados do PSOL (RJ 2022) — dados reais do TSE, por **município**.")

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
is_vereador = cargo == "Vereador"
if is_vereador:
    municipio = VEREADORES[nome]["municipio"]
    d = carregar(VEREADORES[nome]["csv"]).copy()
    unidade, unidade_pl = "zona", "zonas"
    escopo = f"em {municipio}"
else:
    municipio = None
    d = carregar(DEPUTADOS[cargo][nome]).copy()
    unidade, unidade_pl = "município", "municípios"
    escopo = "no estado"

d["_norm"] = d["regiao"].map(_norm)
r = resumo(d)
o = oportunidades(d)

if is_vereador:
    st.caption(
        f"Mostrando: **{nome}** — Vereador(a) PSOL, {municipio} (2024). "
        "Análise por **zona eleitoral** da cidade."
    )
else:
    st.caption(f"Mostrando: **{nome}** — PSOL, Deputado {cargo}, RJ 2022 (dados reais do TSE).")

# Recado principal
alvo_top = o[o["potencial_extra"] > 0].head(1)
if not alvo_top.empty:
    linha = alvo_top.iloc[0]
    st.success(
        f"🎯 **Recado principal:** a melhor {unidade} para {nome} buscar votos novos é "
        f"**{linha['regiao']}** — cerca de **+{_br(linha['potencial_extra'])}** votos possíveis."
    )

# ────────────────────────────────────────────────────────────────────────────
# Abas
# ────────────────────────────────────────────────────────────────────────────
tab_geral, tab_mapa, tab_tend, tab_agir, tab_tab, tab_comp = st.tabs(
    ["📊 Visão geral", "🗺️ Mapa", "📈 Tendência", "🎯 Onde agir", "📋 Tabela", "⚖️ Comparar"]
)

# ── Visão geral ─────────────────────────────────────────────────────────────
with tab_geral:
    st.markdown(leitura_automatica(nome, r, o, escopo, unidade_pl))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Votos do candidato", _br(r["total_votos_candidato"]),
        help="Total de votos nominais que o candidato recebeu.",
    )
    c2.metric(
        "Voto de esquerda órfão", _br(r["total_voto_orfao"]),
        help="Votos que foram para partidos de esquerda, mas não para este candidato. "
        "É o 'estoque' potencial a conquistar.",
    )
    c3.metric(
        f"{unidade_pl.capitalize()} de alto potencial", r["regioes_alto_potencial"],
        help=f"{unidade_pl.capitalize()} com muita esquerda onde ele foi pouco votado.",
    )
    c4.metric(
        f"{unidade_pl.capitalize()} a consolidar", r["regioes_consolidar"],
        help=f"{unidade_pl.capitalize()} onde ele já vai bem e deve manter/reforçar.",
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
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(
        f"Cada bolha é uma {unidade} (tamanho = nº de eleitores). Bolhas mais à **direita** têm "
        "muita esquerda; mais **embaixo** = o candidato foi pouco votado. Direita + embaixo = "
        "🟢 alto potencial."
    )

# ── Mapa / Projeção ─────────────────────────────────────────────────────────
with tab_mapa:
    gj, nomes_geo = carregar_geojson()
    if is_vereador:
        st.subheader("🎯 Projeção como pré-candidato a deputado")
        st.caption(
            f"Se **{nome}** disputasse **deputado estadual** (o RJ inteiro), o eleitorado a "
            f"conquistar seria o voto de esquerda de todo o estado. Hoje a base está concentrada "
            f"em **{municipio}**."
        )
        ref = carregar(REF_ESTADUAL).copy()
        ref["_norm"] = ref["regiao"].map(_norm)
        home = _norm(municipio)
        total_esq = int(ref["votos_esquerda"].sum())
        esq_home = int(ref.loc[ref["_norm"] == home, "votos_esquerda"].sum())
        p1, p2, p3 = st.columns(3)
        p1.metric("Base atual (2024)", _br(r["total_votos_candidato"]),
                  help=f"Votos do vereador em {municipio} em 2024.")
        p2.metric("Esquerda no estado", _br(total_esq),
                  help="Voto de esquerda p/ Dep. Estadual (2022) no RJ inteiro — o 'mercado' de um deputado.")
        p3.metric(f"Esquerda em {municipio}", _br(esq_home),
                  help="Voto de esquerda no município-base, onde o nome já é conhecido.")

        ref["destaque"] = ref["_norm"].eq(home).map({True: "Base", False: "Estado"})
        fig_p = px.choropleth(
            ref, geojson=gj, locations="_norm", featureidkey="properties.norm",
            color="votos_esquerda", color_continuous_scale="Blues", hover_name="regiao",
            hover_data={"_norm": False, "votos_esquerda": ":,"},
            labels={"votos_esquerda": "Esquerda (Estadual 2022)"},
        )
        fig_p.update_geos(fitbounds="locations", visible=False)
        fig_p.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=500,
                            coloraxis_colorbar_title_text="")
        st.plotly_chart(fig_p, use_container_width=True)
        st.caption(
            "Azul mais forte = mais voto de esquerda naquele município. É o mapa do 'mercado' que "
            f"um deputado disputa — o desafio de {nome} seria levar o nome de {municipio} para os "
            "demais focos de esquerda."
        )
        topm = ref.sort_values("votos_esquerda", ascending=False).head(12)
        fig_pb = px.bar(
            topm.sort_values("votos_esquerda"), x="votos_esquerda", y="regiao", orientation="h",
            color="destaque", color_discrete_map={"Base": "#1D9E75", "Estado": "#8AB4D8"},
            labels={"votos_esquerda": "Voto de esquerda (Estadual 2022)", "regiao": ""},
        )
        fig_pb.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=360, legend_title_text="")
        st.plotly_chart(fig_pb, use_container_width=True)
        st.caption("🟢 = município-base do vereador · 🔵 = maiores reservatórios de esquerda a conquistar.")
    elif d["_norm"].isin(nomes_geo).mean() >= 0.8:
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
        st.plotly_chart(fig_mapa, use_container_width=True)
        st.caption(
            "Áreas mais **escuras** = mais voto de esquerda que **não** foi ao candidato. "
            "O maior reservatório absoluto costuma ser a capital — mas nem sempre é onde há mais "
            "espaço para crescer (veja a aba **Onde agir**)."
        )
    else:
        st.info("O mapa está disponível apenas para dados por município do RJ.")

# ── Tendência ───────────────────────────────────────────────────────────────
with tab_tend:
    st.subheader("📈 Tendência da esquerda: 2018 → 2022")
    st.caption(
        "Mudança na fatia de votos de **esquerda** (Deputado Federal) em cada município, de 2018 "
        "para 2022, em **pontos percentuais**. É o retrato do **campo como um todo** — não de um "
        "candidato específico —, então não muda com o deputado selecionado."
    )
    tend = carregar_tendencia()
    gj_t, _ = carregar_geojson()
    fig_t = px.choropleth(
        tend, geojson=gj_t, locations="_norm", featureidkey="properties.norm",
        color="delta_pp", color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
        hover_name="regiao",
        hover_data={"_norm": False, "esq_pct_2018": ":.1f", "esq_pct_2022": ":.1f",
                    "delta_pp": ":+.1f"},
        labels={"delta_pp": "Variação (p.p.)"},
    )
    fig_t.update_geos(fitbounds="locations", visible=False)
    fig_t.update_layout(margin=dict(l=0, r=0, t=0, b=0), height=520)
    st.plotly_chart(fig_t, use_container_width=True)
    st.caption("🟢 verde = a esquerda **cresceu**; 🔴 vermelho = **encolheu** (Dep. Federal).")

    ca, cb = st.columns(2)
    with ca:
        st.markdown("**📈 Onde a esquerda mais cresceu**")
        for row in tend.sort_values("delta_pp", ascending=False).head(6).itertuples():
            st.markdown(
                f"- **{row.regiao}**: {row.esq_pct_2018:.0f}% → {row.esq_pct_2022:.0f}% "
                f"(**+{row.delta_pp:.0f} p.p.**)"
            )
    with cb:
        st.markdown("**📉 Onde a esquerda mais encolheu**")
        for row in tend.sort_values("delta_pp").head(6).itertuples():
            st.markdown(
                f"- **{row.regiao}**: {row.esq_pct_2018:.0f}% → {row.esq_pct_2022:.0f}% "
                f"(**{row.delta_pp:.0f} p.p.**)"
            )
    st.caption(
        "No estado, a esquerda passou de ~21% (2018) para ~23% (2022) dos votos de Dep. Federal. "
        "Cruze com a aba **Onde agir**: crescimento + voto órfão = terreno mais promissor."
    )

# ── Onde agir ───────────────────────────────────────────────────────────────
with tab_agir:
    taxa_global = o["taxa_global"].iloc[0]
    st.subheader("🎯 Onde agir para captar mais votos")
    st.markdown(
        f"{unidade_pl.capitalize()} com **muita esquerda** onde o candidato rende **abaixo da "
        f"própria média** de captação (**{taxa_global:.1%}** dos votos de esquerda). É onde há mais "
        f"espaço para crescer num eleitorado que já existe — melhor relação **esforço × retorno**."
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
            st.plotly_chart(fig3, use_container_width=True)

    st.caption(
        "⚠️ Priorização **relativa**: mede onde há esquerda sub-aproveitada, não votos garantidos. "
        "As áreas onde o candidato já domina saem daqui de propósito — lá o crescimento marginal "
        "é menor."
    )

# ── Tabela ──────────────────────────────────────────────────────────────────
with tab_tab:
    st.subheader(f"Tabela por {unidade}")
    f1, f2, f3 = st.columns([1, 1, 2])
    so_alto = f1.checkbox("Só alto potencial", help=f"Mostrar apenas as {unidade_pl} de alto potencial.")
    topn = f2.slider("Top N (por voto órfão)", 5, len(d), len(d))
    busca = f3.text_input(f"🔎 Buscar {unidade}", placeholder="ex.: Niterói" if not is_vereador else "ex.: Zona 5")

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
        "regiao": unidade.capitalize(),
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
        use_container_width=True, hide_index=True,
    )
    st.caption(f"{len(t)} de {len(d)} {unidade_pl} exibidas.")

    buffer = io.BytesIO()
    o.drop(columns=["_norm"], errors="ignore").to_excel(buffer, index=False)
    st.download_button(
        "⬇️ Baixar tudo (Excel)", data=buffer.getvalue(),
        file_name=f"diagnostico_{_norm(nome).lower().replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ── Comparar ────────────────────────────────────────────────────────────────
with tab_comp:
    st.subheader("⚖️ Comparativo dos candidatos")
    st.caption(
        "O que cada candidato tem de mais significativo, lado a lado. As colunas de "
        "**redes sociais** e **Observações** são **editáveis** — clique numa célula e escreva. "
        "As edições valem nesta sessão; use o botão para baixar o resultado."
    )

    base = tabela_comparativa()
    somente_readonly = [
        "Candidato", "Cargo", "Votos", "% capta esquerda", "Voto órfão",
        "Reduto (mais votos)", "Melhor alvo p/ crescer", "Regiões alto potencial",
    ]
    editada = st.data_editor(
        base, use_container_width=True, hide_index=True, num_rows="fixed",
        disabled=somente_readonly,
        column_config={
            "Votos": st.column_config.NumberColumn("Votos", format="%d"),
            "Voto órfão": st.column_config.NumberColumn("Voto órfão", format="%d"),
            "% capta esquerda": st.column_config.NumberColumn("% capta esquerda", format="%.1f%%"),
            "Seguidores IG": st.column_config.NumberColumn("Seguidores IG", format="%d"),
        },
    )

    csv = editada.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Baixar comparativo (CSV)", data=csv,
        file_name="comparativo_candidatos.csv", mime="text/csv",
    )
    try:
        with open("data/redes_atualizado.txt", encoding="utf-8") as _f:
            st.caption(f"🔄 Seguidores do Instagram atualizados automaticamente em **{_f.read().strip()}**.")
    except OSError:
        pass
    st.caption(
        "📱 O **Instagram** é a rede mais relevante aqui. As demais colunas ficam a preencher. "
        "As edições feitas nesta tela **não ficam salvas** ao recarregar (para isso, os dados "
        "precisam ser gravados no repositório ou numa planilha conectada)."
    )

    st.divider()
    st.subheader("Votos × seguidores — força eleitoral × digital")
    graf = editada.copy()
    graf["Seguidores IG"] = pd.to_numeric(graf["Seguidores IG"], errors="coerce")
    graf = graf.dropna(subset=["Seguidores IG"])
    graf["Seguidores IG"] = graf["Seguidores IG"].astype(int)

    if graf.empty:
        st.info("Preencha os seguidores do Instagram para ver este gráfico.")
    else:
        fig_vs = px.scatter(
            graf, x="Seguidores IG", y="Votos", text="Candidato", color="Cargo",
            labels={"Seguidores IG": "Seguidores no Instagram", "Votos": "Votos (2022)"},
        )
        fig_vs.update_traces(textposition="top center", cliponaxis=False)
        tot_v, tot_s = graf["Votos"].sum(), graf["Seguidores IG"].sum()
        if tot_s:
            ratio = tot_v / tot_s
            mxs = int(graf["Seguidores IG"].max())
            fig_vs.add_shape(
                type="line", x0=0, y0=0, x1=mxs, y1=ratio * mxs,
                line=dict(dash="dash", color="gray"),
            )
        fig_vs.update_layout(height=520, legend_title_text="")
        st.plotly_chart(fig_vs, use_container_width=True)
        st.caption(
            "Cada ponto é um candidato; a linha tracejada é a **conversão média** do grupo "
            "(votos por seguidor). **Acima** da linha → transforma audiência em voto acima da "
            "média. **Abaixo** → tem **público online a ativar** para virar voto."
        )

    st.divider()
    st.subheader("📈 Crescimento de seguidores no tempo")
    try:
        hist = pd.read_csv("data/redes_historico.csv")
    except FileNotFoundError:
        hist = pd.DataFrame(columns=["data", "Candidato", "seguidores"])
    if hist["data"].nunique() < 2:
        st.info(
            "O histórico está **começando a acumular** (a coleta roda 2×/semana). Com mais alguns "
            "pontos ao longo das semanas, aparece aqui a curva de crescimento de cada candidato."
        )
    else:
        hist["data"] = pd.to_datetime(hist["data"])
        hist["seguidores"] = pd.to_numeric(hist["seguidores"], errors="coerce")
        fig_hist = px.line(
            hist.sort_values("data"), x="data", y="seguidores", color="Candidato", markers=True,
            labels={"data": "Data", "seguidores": "Seguidores no Instagram", "Candidato": ""},
        )
        fig_hist.update_layout(height=480, legend_title_text="")
        st.plotly_chart(fig_hist, use_container_width=True)
        st.caption("Evolução dos seguidores no Instagram desde o início da coleta automática.")
