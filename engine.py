"""Motor de análise eleitoral — lógica do diagnóstico (seção 3.2 da especificação)."""

import pandas as pd

COLUNAS_OBRIGATORIAS = ["regiao", "votos_candidato", "votos_validos", "votos_esquerda"]

LIMIAR_SOLO_DIFICIL = 0.15   # % da esquerda abaixo disso => Solo difícil
LIMIAR_ALTO_POTENCIAL = 0.60 # % não capturado acima disso => Alto potencial


def validar(df: pd.DataFrame) -> list[str]:
    """Retorna lista de problemas encontrados (vazia = ok)."""
    problemas = []
    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in df.columns]
    if faltando:
        problemas.append(f"Colunas faltando: {', '.join(faltando)}")
        return problemas
    for col in COLUNAS_OBRIGATORIAS[1:]:
        if not pd.api.types.is_numeric_dtype(df[col]):
            problemas.append(f"Coluna '{col}' precisa ser numérica.")
    if not problemas:
        if (df["votos_validos"] <= 0).any():
            problemas.append("Há regiões com votos_validos igual a zero ou negativo.")
        if (df["votos_candidato"] > df["votos_esquerda"]).any():
            problemas.append(
                "Atenção: em alguma região o candidato tem mais votos que a esquerda somada. "
                "Verifique se 'votos_esquerda' inclui os votos do próprio candidato."
            )
    return problemas


def diagnosticar(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica o diagnóstico por região. Espera as colunas obrigatórias."""
    d = df.copy()
    d["pct_candidato"] = d["votos_candidato"] / d["votos_validos"]
    d["pct_esquerda"] = d["votos_esquerda"] / d["votos_validos"]
    d["voto_orfao"] = (d["votos_esquerda"] - d["votos_candidato"]).clip(lower=0)
    d["pct_nao_capturado"] = (d["voto_orfao"] / d["votos_esquerda"]).where(d["votos_esquerda"] > 0, 0)

    def prioridade(row):
        if row["pct_esquerda"] < LIMIAR_SOLO_DIFICIL:
            return "Solo difícil"
        if row["pct_nao_capturado"] > LIMIAR_ALTO_POTENCIAL:
            return "Alto potencial"
        return "Consolidar"

    d["prioridade"] = d.apply(prioridade, axis=1)
    return d.sort_values("voto_orfao", ascending=False).reset_index(drop=True)


def resumo(d: pd.DataFrame) -> dict:
    """Números-síntese para o topo do dashboard."""
    return {
        "total_votos_candidato": int(d["votos_candidato"].sum()),
        "total_voto_orfao": int(d["voto_orfao"].sum()),
        "regioes_alto_potencial": int((d["prioridade"] == "Alto potencial").sum()),
        "regioes_consolidar": int((d["prioridade"] == "Consolidar").sum()),
        "regioes_solo_dificil": int((d["prioridade"] == "Solo difícil").sum()),
    }


def oportunidades(d: pd.DataFrame) -> pd.DataFrame:
    """Ranqueia regiões por *potencial de crescimento* do candidato.

    Ideia: onde há muita esquerda mas o candidato captura MENOS do que a sua
    própria média estadual, existe eleitorado de esquerda sub-aproveitado.

    - `taxa_captura`  = votos do candidato / votos de esquerda na região
    - `taxa_global`   = a mesma taxa, agregada em todas as regiões (a "média dele")
    - `potencial_extra` = votos_esquerda × (taxa_global − taxa_captura), só onde
      é positivo. Ou seja: quantos votos ele somaria SE, naquela região,
      capturasse a esquerda na sua média habitual.

    É um sinal RELATIVO de onde agir (esforço x retorno), não uma promessa: o
    voto órfão pertence a outros candidatos/partidos e não migra sozinho.
    """
    o = d.copy()
    total_esq = o["votos_esquerda"].sum()
    taxa_global = o["votos_candidato"].sum() / total_esq if total_esq else 0.0
    o["taxa_captura"] = (o["votos_candidato"] / o["votos_esquerda"]).where(
        o["votos_esquerda"] > 0, 0.0
    )
    o["taxa_global"] = taxa_global
    o["potencial_extra"] = (
        (o["votos_esquerda"] * (taxa_global - o["taxa_captura"]))
        .clip(lower=0)
        .round()
        .astype(int)
    )
    return o.sort_values("potencial_extra", ascending=False).reset_index(drop=True)
