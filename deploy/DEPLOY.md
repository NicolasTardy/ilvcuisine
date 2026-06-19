# Déploiement ILV Cuisine (VPS vps-819e6242, sous ilvcredit.triangleoffensif.fr/cuisine/)

1. Cloner :
   cd /home/ubuntu && git clone https://github.com/NicolasTardy/ilvcuisine.git
2. Venv + deps :
   cd /home/ubuntu/ilvcuisine && python3.14 -m venv venv
   ./venv/bin/pip install -r requirements.txt
   ./venv/bin/python -c "import fitz, flask; print('deps OK')"
3. Service systemd :
   sudo cp deploy/ilvcuisine.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now ilvcuisine
   curl -s http://172.17.0.1:3024/api/health   # doit répondre via le bridge
4. nginx : insérer le contenu de deploy/nginx-cuisine.snippet.conf dans
   /home/ubuntu/challengeBut/nginx/conf/ilvcredit.conf (server 443), puis :
   sudo docker exec challengebut-nginx-1 nginx -t
   sudo docker exec challengebut-nginx-1 nginx -s reload
5. Tester : https://ilvcredit.triangleoffensif.fr/cuisine/ (login ILVCREDIT)

Port 3024 — vérifier qu'il est libre avant (ss -tlnp | grep 3024).
