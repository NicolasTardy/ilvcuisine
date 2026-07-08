# ILV Cuisine — guide de maintenance

Générateur d'ILV crédit (PLV Cetelem « Payez à votre rythme ») pour les projets
cuisine BUT / Cetelem. Backend Flask + rendu PDF/PNG via PyMuPDF (`fitz`). Tout le
métier tient dans **`app.py`** (~250 lignes) ; `index.html` est l'interface.

Les deux tâches de maintenance récurrentes sont documentées ci-dessous :
**(A) mettre à jour les TAEG / le barème** et **(B) mettre à jour les mentions légales**.

## Lancer et vérifier en local (à faire avant/après toute modif)

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt   # 1re fois
./venv/bin/python app.py            # http://127.0.0.1:8770
```

Vérifier un rendu sans navigateur (contrôle rapide d'une offre) :
```bash
curl "http://127.0.0.1:8770/api/render?montant=5000&offer=24x_comp&fmt=png" -o /tmp/test.png
```
Ou ouvrir http://127.0.0.1:8770 et cliquer « Générer l'ILV ». **Toujours** regarder
le rendu réel après une modif : mensualité, TAEG affiché, et le bloc mentions en bas
(sa police s'auto-ajuste, il ne doit jamais déborder ni être coupé).

## (A) Mettre à jour les TAEG et le barème

Tous les taux sont regroupés en haut de `app.py`. Points à modifier selon le cas :

- **TAEG client des offres compensées** → `TAEG_CLIENT_COMPENSE` (actuellement `0.049`
  = 4,90 %). C'est le seul taux client des offres « compensé ». La mensualité et le
  texte « TAEG fixe de 4,90 % » en découlent automatiquement — ne pas coder « 4,90 % »
  en dur ailleurs.
- **Barème des offres gratuites** → `GAMME_GRAT` : pour chaque offre gratuite,
  `(taux débiteur TNC, TAEG)`. Ces valeurs ne changent PAS la mensualité (gratuit =
  montant ÷ durée) mais servent à recalculer, dans les mentions, le coût réellement
  pris en charge par le magasin (intérêts « fictifs »). Les reprendre telles quelles
  depuis le barème EASY PLV BUT.
- **Assurance facultative DIM** → `ASSURANCE_DIM_BORNES` : liste
  `(durée minimale en mois, taux)`. `_dim_rate(duree)` prend le taux de la dernière
  borne dont la durée est atteinte. Mettre à jour si le barème Cardif change.
- **Date des conditions** → `DATE_CONDITIONS` (ex. `"01/01/2026"`). **À changer à
  chaque nouveau barème** — elle apparaît dans les mentions (« Conditions en vigueur
  au … »).
- **Offres proposées / durées / montants min-max** → dictionnaire `CUISINE_OFFERS`.
  Chaque clé = une offre (`duree` en mois, `min`/`max` = bornes du montant finançable,
  `fam` = `"gratuit"` ou `"compense"`). Ajouter/retirer une offre ici, puis l'ajouter
  aussi dans le `<select id="offer">` de `index.html` (les deux doivent rester
  synchronisés). Une offre gratuite doit avoir une entrée correspondante dans
  `GAMME_GRAT`.

Après toute modif de taux : régénérer une ILV de chaque famille (une gratuite, une
compensée ≥ 12 mois pour voir l'assurance) et vérifier que TAEG, mensualité et TAEA
sont cohérents.

## (B) Mettre à jour les mentions légales

Tout le texte réglementaire est produit par **`mentions_cuisine(offer_key, montant, c)`**
dans `app.py`. Structure du texte, dans l'ordre :

1. **Phrase d'offre** (bornes de montant, durée, prise en charge magasin si gratuit).
2. **TAEG + date + exemple chiffré** (mensualités × durée, montant total dû).
   Les nombres sont calculés, pas écrits en dur — ne pas les figer.
3. **Coût pris en charge par le magasin** (offres gratuites uniquement) : TAEG,
   taux débiteur et intérêts recalculés depuis `GAMME_GRAT`.
4. **Assurance facultative Cardif** (durées ≥ 12 mois) : mensualité d'assurance,
   coût total, **TAEA** calculé par `calculer_taea` (Newton-Raphson, ne pas y toucher
   sauf changement de méthode réglementaire).
5. **Bloc Cetelem** → constante `_CETELEM`.
6. **Bloc BUT** → constante `_BUT`.

Pour un changement de texte réglementaire (nouveau capital social, adresse, n° ORIAS,
mention de rétractation…) : modifier les constantes **`_CETELEM`** et **`_BUT`** —
c'est là que vit le texte « fixe ». Pour un changement de formulation de l'exemple
ou de l'assurance : modifier la construction de la chaîne `s` dans `mentions_cuisine`.

Helpers de formatage à réutiliser (ne pas reformater à la main) :
`_e(v)` → montant format français « 1 234,56 » ; `_pct(x)` → pourcentage « 4,90% ».

Après modif : générer une ILV et **relire le bloc de mentions en entier** dans le
rendu — c'est un texte réglementaire, la moindre valeur fausse ou coupée est un
problème de conformité.

## Déploiement (VPS)

Voir `deploy/` (service systemd `ilvcuisine.service` + snippet nginx). Gunicorn sur
le port dédié **8770**, derrière Basic Auth nginx, même VPS que les autres ILV crédit.
Après un push, se reporter à `deploy/DEPLOY.md` pour la procédure de mise à jour prod.

## Règles

- Ne jamais coder un taux ou un TAEG en dur dans du texte : le faire dériver des
  constantes en haut de `app.py`, sinon les mentions et le rendu divergent.
- Garder `CUISINE_OFFERS` (app.py) et le `<select>` (index.html) synchronisés.
- Toujours vérifier le rendu réel (PNG ou PDF) avant de committer — surtout le bloc
  mentions légales.
