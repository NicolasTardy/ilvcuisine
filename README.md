# ILV Cuisine

Générateur d'ILV crédit dédié aux **projets cuisine** BUT / Cetelem.

Offres « cuisine » du barème EASY PLV BUT :
- **Gratuit** : 10X / 12X / 20X (TAEG 0 %, coût pris en charge par le magasin)
- **Compensé** : 12X / 24X / 36X / 48X / 60X (TAEG client 4,90 %, le magasin compense la différence)

Design : reproduction de la PLV Cetelem « Payez à votre rythme ».
Mentions légales reproduites du template PLV de l'Excel (offre + exemple + assurance Cardif + Cetelem/BUT).

## Lancer en local
```
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py        # http://127.0.0.1:8770
```

## API
- `GET /` — interface
- `GET /api/render?desig=&prec=&montant=&offer=&fmt=png|pdf` — génère l'ILV
- `GET /api/health`

## Déploiement
Voir `deploy/` (service systemd + vhost nginx). Servi derrière Basic Auth nginx
sur le même VPS que les autres ILV (gunicorn sur port dédié).
