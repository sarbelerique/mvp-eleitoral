# Atualiza os seguidores do Instagram e envia para o GitHub.
# Roda na MÁQUINA LOCAL (IP residencial), que o Instagram aceita — ao contrário
# dos IPs de datacenter do GitHub Actions. Pensado para o Agendador de Tarefas
# do Windows rodar 2x/semana. Ao dar push, o Streamlit Cloud redeploya sozinho.

Set-Location -Path $PSScriptRoot

python atualizar_redes.py
if ($LASTEXITCODE -ne 0) {
    Write-Output "Script de atualização falhou; nada será enviado."
    exit 1
}

git add data/redes.csv data/redes_atualizado.txt
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Atualiza seguidores automaticamente ($(Get-Date -Format dd/MM/yyyy))"
    git push
    Write-Output "Enviado para o GitHub."
} else {
    Write-Output "Nenhuma mudança nos números."
}
