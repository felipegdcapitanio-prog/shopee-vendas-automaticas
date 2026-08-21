@echo off
cd /d "C:\Users\User\OneDrive\shopee-vendas-automaticas"

echo. >> data\daily-post-run.log
echo ==== %date% %time% ==== >> data\daily-post-run.log

"C:\Users\User\AppData\Local\Python\bin\python.exe" scripts\post_to_telegram.py >> data\daily-post-run.log 2>&1

git add data\posted_ids.json data\log_postagens.json >> data\daily-post-run.log 2>&1
git commit -m "chore: registra postagens do dia (agendador local)" >> data\daily-post-run.log 2>&1
git push >> data\daily-post-run.log 2>&1
