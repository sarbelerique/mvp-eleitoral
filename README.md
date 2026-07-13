# MVP — Diagnóstico eleitoral

Ferramenta que responde, por região: onde o candidato é forte, onde a esquerda
vota mas não nele (voto órfão) e onde não vale gastar energia.

## Como rodar

1. Instale o Python 3.10+ (python.org)
2. No terminal, dentro desta pasta:

```
pip install -r requirements.txt
streamlit run app.py
```

3. O navegador abre sozinho em http://localhost:8501

## Como usar

- Sem arquivo, o app mostra **dados de exemplo** (ilustrativos).
- Para dados reais, envie um CSV/Excel com as colunas:
  `regiao, votos_candidato, votos_validos, votos_esquerda`
- A exportação do Politique pode ser adaptada a esse formato (uma linha por
  região; some os partidos de esquerda para a coluna `votos_esquerda`).

## Estrutura

- `engine.py` — a lógica do diagnóstico (testável, reutilizável)
- `app.py` — a interface Streamlit
- `data/exemplo.csv` — dados ilustrativos
