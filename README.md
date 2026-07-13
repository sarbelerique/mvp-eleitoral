# Diagnóstico eleitoral

Ferramenta que mostra, região por região, onde um candidato de esquerda é forte,
onde a esquerda vota mas não nele (**voto órfão**) e **onde vale a pena agir** para
captar mais votos.

Dados **reais do TSE** — deputados do PSOL (RJ, 2022), por município.

## Como rodar (local)

1. Instale o Python 3.10+ (python.org)
2. No terminal, dentro desta pasta:

```
pip install -r requirements.txt
streamlit run app.py
```

3. O navegador abre em http://localhost:8501

> Se mudar o `engine.py`, reinicie o servidor — o Streamlit só recarrega o `app.py`.

## O que o app mostra

- **Visão geral**: números-chave, uma leitura automática em português e o gráfico
  força do candidato × força da esquerda.
- **Mapa**: coroplético do RJ por município (voto órfão, % não capturado ou prioridade).
- **Onde agir**: ranking de municípios com melhor relação esforço × retorno.
- **Tabela**: dados por município, com filtros (só alto potencial, Top N, busca) e
  exportação para Excel.
- **Comparar**: dois deputados lado a lado.

## Dados

Cada deputado é um CSV em `data/` com as colunas
`regiao, votos_candidato, votos_validos, votos_esquerda` (uma linha por município).
`votos_esquerda` = soma de PDT, PT, PSTU, REDE, PCB, PCO, PSB, PV, PSOL e PCdoB
(nominais + legenda). O app não aceita upload: novos conjuntos são adicionados ao
repositório pelo responsável.

## Estrutura

- `engine.py` — a lógica do diagnóstico (testável, reutilizável)
- `app.py` — a interface Streamlit
- `data/` — CSVs por deputado + contorno geográfico do RJ (`rj_municipios.geojson`)
