@echo off
cd /d "C:\Users\User\OneDrive\shopee-vendas-automaticas"

echo. >> data\refresh-catalog-run.log
echo ==== %date% %time% ==== >> data\refresh-catalog-run.log

"C:\Users\User\AppData\Local\Python\bin\python.exe" scripts\find_products.py >> data\refresh-catalog-run.log 2>&1
"C:\Users\User\AppData\Local\Python\bin\python.exe" scripts\generate_whatsapp_digest.py >> data\refresh-catalog-run.log 2>&1

git add data\catalogo_produtos.json data\whatsapp_posted_ids.json data\whatsapp_digests\ >> data\refresh-catalog-run.log 2>&1
git commit -m "chore: renova catalogo de produtos (agendador local)" >> data\refresh-catalog-run.log 2>&1
git push >> data\refresh-catalog-run.log 2>&1
