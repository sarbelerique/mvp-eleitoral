"""Atualiza os seguidores de Instagram em data/redes.csv (gratuito, best-effort).

Usa o endpoint público `web_profile_info` do Instagram (o mesmo que ferramentas
como instaloader usam), que devolve o número exato de seguidores de perfis
públicos. É gratuito, mas não oficial: o Instagram pode limitar/bloquear (em
especial IPs de servidor). Em caso de falha para um perfil, o número antigo é
mantido — nunca zera, nunca quebra.

Uso:  python atualizar_redes.py
"""

import csv
import datetime
import sys
import time

import requests

CSV_PATH = "data/redes.csv"
STAMP_PATH = "data/redes_atualizado.txt"
COL = "Seguidores IG"

API = "https://www.instagram.com/api/v1/users/web_profile_info/?username={}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
    "x-ig-app-id": "936619743392459",
    "Accept-Language": "en-US,en;q=0.9",
}


def seguidores(username: str):
    """Nº de seguidores do perfil público, ou None se não conseguir."""
    try:
        r = requests.get(API.format(username), headers=HEADERS, timeout=25)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    try:
        return int(r.json()["data"]["user"]["edge_followed_by"]["count"])
    except (ValueError, KeyError, TypeError):
        return None


def main():
    with open(CSV_PATH, encoding="utf-8") as f:
        leitor = csv.DictReader(f)
        campos = leitor.fieldnames
        linhas = list(leitor)

    atualizados = 0
    for linha in linhas:
        handle = (linha.get("Instagram") or "").strip().lstrip("@")
        if not handle:
            continue
        n = seguidores(handle)
        if n:
            linha[COL] = str(n)
            atualizados += 1
            print(f"  ok  {handle}: {n}")
        else:
            print(f"  --  {handle}: falhou (mantém {linha.get(COL) or 'vazio'})")
        time.sleep(4)  # gentil com o servidor

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(linhas)
    with open(STAMP_PATH, "w", encoding="utf-8") as f:
        f.write(datetime.date.today().strftime("%d/%m/%Y"))

    print(f"Atualizados {atualizados}/{len(linhas)} perfis.")
    if atualizados == 0:
        sys.exit("Nenhum perfil atualizado (Instagram provavelmente bloqueou).")


if __name__ == "__main__":
    main()
