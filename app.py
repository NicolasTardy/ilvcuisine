"""ILV Cuisine — générateur d'ILV crédit pour les projets cuisine BUT/Cetelem.

Projet dédié (séparé de l'app produits standard). Offres « cuisine » du barème
EASY PLV BUT : gratuit (10/12/20X) et compensé (12→60X, TAEG client 4,90 %).
Design : reproduction de la PLV Cetelem « Payez à votre rythme ».
"""
import io
import os

import fitz
from flask import Flask, request, send_file, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
FONT_PATH = os.path.join(BASE, "fonts", "ArchivoSemiCondensed-Bold.ttf")
_font = fitz.Font(fontfile=FONT_PATH) if os.path.exists(FONT_PATH) else fitz.Font("helv")
PORT = int(os.environ.get("PORT", "8770"))

# ── Offres cuisine (barème onglet « gamme ») ──────────────────────────────────
CUISINE_OFFERS = {
    "10x_grat": {"label": "10X gratuit cuisine",  "fam": "gratuit",  "duree": 10, "min": 160,  "max": 25000},
    "12x_grat": {"label": "12X gratuit cuisine",  "fam": "gratuit",  "duree": 12, "min": 200,  "max": 25000},
    "12x_comp": {"label": "12X compensé cuisine", "fam": "compense", "duree": 12, "min": 1000, "max": 25000},
    "24x_comp": {"label": "24X compensé cuisine", "fam": "compense", "duree": 24, "min": 1000, "max": 25000},
    "36x_comp": {"label": "36X compensé cuisine", "fam": "compense", "duree": 36, "min": 1000, "max": 25000},
    "48x_comp": {"label": "48X compensé cuisine", "fam": "compense", "duree": 48, "min": 1000, "max": 25000},
    "60x_comp": {"label": "60X compensé cuisine", "fam": "compense", "duree": 60, "min": 1000, "max": 25000},
}
TAEG_CLIENT_COMPENSE = 0.049  # 4,90 % (compensé : le magasin compense le reste)
# Barème gratuit (gamme) : (taux débiteur TNC, TAEG) → détail du coût pris en charge
GAMME_GRAT = {"10x_grat": (0.0443, 0.0452), "12x_grat": (0.0375, 0.03815)}
DATE_CONDITIONS = "01/01/2026"

# ── Assurance facultative DIM (repris du barème EASY PLV) ──────────────────────
ASSURANCE_DIM_BORNES = [
    (12, 0.0286), (19, 0.0341), (25, 0.0374), (37, 0.06407),
    (49, 0.07519), (61, 0.08393), (73, 0.09031), (85, 0.10318),
]


def _dim_rate(duree):
    rate = None
    for borne, r in ASSURANCE_DIM_BORNES:
        if duree >= borne:
            rate = r
        else:
            break
    return rate


def calculer_assurance(mensualite, duree):
    r = _dim_rate(duree)
    if r is None:
        return None
    am = round(mensualite * r, 2)
    return {"m": am, "tot": round(am * duree, 2)}


def calculer_taea(montant, duree, tdf_annuel, mensualite, assurance_m):
    def solve(pmt, capital, n):
        r = 0.01
        for _ in range(200):
            if r <= -1:
                r = 0.001
            rn = (1 + r) ** n
            pv = pmt * (rn - 1) / (r * rn)
            dpv = pmt * ((1 - rn + n * r * rn / (1 + r)) / (r * rn) - (rn - 1) * n / ((1 + r) * r * rn))
            d = pv - capital
            if abs(d) < 1e-8:
                break
            r -= d / dpv
        return (1 + r) ** 12 - 1
    return round((solve(mensualite + assurance_m, montant, duree) - solve(mensualite, montant, duree)) * 100, 2)


# ── Calcul de la mensualité ───────────────────────────────────────────────────
def calc_cuisine(offer_key, montant):
    o = CUISINE_OFFERS[offer_key]
    d = o["duree"]
    if o["fam"] == "gratuit":
        return {"mensu": round(montant / d, 2), "taeg": "0 %", "total": round(montant, 2), "fam": "gratuit"}
    nominal = 12 * ((1 + TAEG_CLIENT_COMPENSE) ** (1 / 12) - 1)
    rm = nominal / 12
    f = (1 + rm) ** d
    m = round(montant * rm * f / (f - 1), 2)
    return {"mensu": m, "taeg": "4,90 %", "total": round(m * d, 2), "fam": "compense"}


# ── Mentions légales (reproduction template PLV Excel B25-B37) ─────────────────
_CETELEM = ("Sous réserve d'étude et d'acceptation du dossier par BNP Paribas Personal Finance. Cetelem est une "
            "marque de BNP Paribas Personal Finance S.A au capital de 634 574 115 € - 542 097 902 RCS Paris - "
            "Siège social : 1 bd Haussmann 75 009 Paris. N° Orias : 07 023 128 (www.orias.fr). Vous disposez "
            "d'un droit de rétractation.")
_BUT = ("Publicité diffusée par But International 722041860 RCS Meaux, 1 avenue Spinoza 77184 Emerainville "
        "ORIAS 10055338 en qualité d'intermédiaire en opérations de banques immatriculé dans la catégorie "
        "mandataire exclusif de BNP Paribas Personal Finance. Cet intermédiaire apporte son concours à la "
        "réalisation d'opérations de crédit sans agir en qualité de prêteur.")


def _e(v):
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def _pct(x):
    return f"{x * 100:.2f}".replace(".", ",") + "%"


def mentions_cuisine(offer_key, montant, c):
    o = CUISINE_OFFERS[offer_key]
    d = o["duree"]; mn, mx = o["min"], o["max"]
    mensu = c["mensu"]; total = c["total"]; gratuit = (c["fam"] == "gratuit")
    hors = ", hors assurance facultative." if d >= 12 else "."
    tdb = "0,00%" if gratuit else _pct(12 * ((1 + TAEG_CLIENT_COMPENSE) ** (1 / 12) - 1))

    s = (f"Offre de crédit accessoire à une vente de {_e(mn)}€ à {_e(mx)}€, sur une durée de {d} mois, "
         f"pour un achat de {_e(mn)}€ à {_e(mx)}€")
    s += ". Le coût du crédit est pris en charge par votre magasin. " if gratuit else ". "
    s += (f"Taux Annuel Effectif Global fixe de {c['taeg']}. Conditions en vigueur au {DATE_CONDITIONS}. "
          f"Exemple pour un achat et un crédit accessoire à une vente de {_e(montant)} € sur {d} mois au Taux "
          f"Annuel Effectif Global (TAEG) fixe de {c['taeg']} (taux débiteur fixe de {tdb}), vous remboursez "
          f"{d} mensualités de {_e(mensu)} €{hors} Montant total dû par l'emprunteur : {_e(total)} €{hors}")
    if gratuit:
        tnc, taeg_f = GAMME_GRAT[offer_key]
        nom_f = 12 * ((1 + taeg_f) ** (1 / 12) - 1)
        rm = nom_f / 12; f = (1 + rm) ** d
        interets_f = round((montant * rm * f / (f - 1)) * d - montant)
        s += (f" Le coût du crédit (TAEG fixe : {_pct(taeg_f)}, taux débiteur fixe de {_pct(nom_f)} intérêts : "
              f"{interets_f} €) est pris en charge par votre magasin.")
    if d >= 12:
        ass = calculer_assurance(mensu, d)
        if ass:
            taux_deb = 0.0 if gratuit else 12 * ((1 + TAEG_CLIENT_COMPENSE) ** (1 / 12) - 1)
            taea = calculer_taea(montant, d, taux_deb, mensu, ass["m"])
            s += (f" Le coût de l'assurance facultative (Décès, perte totale et Irréversible d'Autonomie et "
                  f"incapacité temporaire totale de travail) souscrite auprès de Cardif Assurance Vie et Cardif "
                  f"Assurances Risques Divers jusqu'à 64 ans est de {_e(ass['m'])} € et s'ajoute au montant de la "
                  f"mensualité de l'exemple ci-dessus. Le coût total de l'assurance facultative est de "
                  f"{_e(ass['tot'])} €, le taux annuel effectif de l'assurance (TAEA) est de "
                  f"{f'{taea:.2f}'.replace('.', ',')}%.")
    return s + " " + _CETELEM + " " + _BUT


# ── Rendu de l'ILV (design PLV Cetelem) ───────────────────────────────────────
def _aspect(p):
    px = fitz.Pixmap(p)
    return px.width / px.height


def render_cuisine(desig, precision, montant, offer_key, eco=0.0):
    c = calc_cuisine(offer_key, montant)
    o = CUISINE_OFFERS[offer_key]; d = o["duree"]
    doc = fitz.open(); W, H = 480, 800
    p = doc.new_page(width=W, height=H)
    DARK = (0.13, 0.13, 0.13); RED = (0.85, 0.07, 0.10); GREY = (0.45, 0.45, 0.45)

    def T(x, y, s, sz, col=DARK):
        tw = fitz.TextWriter(p.rect, color=col)
        tw.append(fitz.Point(x, y), s, font=_font, fontsize=sz)
        tw.write_text(p)

    TEAL = (0.0, 0.627, 0.690)
    p.draw_rect(fitz.Rect(14, 14, W - 14, H - 14), color=TEAL, width=3.5, radius=0.02)
    bw = 215; bh = bw / _aspect(os.path.join(ASSETS, "bandeau.png"))
    p.insert_image(fitz.Rect(28, 24, 28 + bw, 24 + bh), filename=os.path.join(ASSETS, "bandeau.png"))
    T(28, 120, desig.upper(), 17)
    T(452 - _font.text_length(_e(montant) + " €", 17), 120, _e(montant) + " €", 17, RED)
    next_y = 144
    if eco and eco > 0:
        eco_txt = f"dont {_e(eco)} € d'éco-participation"
        T(452 - _font.text_length(eco_txt, 10.5), next_y, eco_txt, 10.5, GREY)
        next_y += 18
    if precision:
        T(28, next_y, precision, 10.5, GREY)
    # Mensualité (très gros, centré)
    mensu = c["mensu"]; mstr = f"{int(mensu)}"; cstr = "," + f"{int(round((mensu - int(mensu)) * 100)):02d}"
    S = 108; SC = 44
    iw = _font.text_length(mstr, S); cw = _font.text_length(cstr, SC)
    xmois = "x " + str(d) + " mois"; xw = _font.text_length(xmois, 33)
    x0 = (W - (iw + cw + 32 + xw)) / 2; base = 296
    T(x0, base, mstr, S)
    T(x0 + iw + 4, base - 48, cstr, SC)
    T(x0 + iw + 4, base, "€", SC)
    T(x0 + iw + cw + 32, base - 33, xmois, 33)
    T(28, 356, "Montant total dû : " + _e(c["total"]) + " €", 14.5)
    T(28, 384, "TAEG Fixe : " + c["taeg"], 14.5)
    note = ("Offre " + o["label"] + " — coût pris en charge par le magasin" if c["fam"] == "gratuit"
            else "Offre " + o["label"] + " — taux client compensé par le magasin")
    T(28, 406, note, 9.5, GREY)
    # Avertissement (centré)
    aw = 322; ah = aw / _aspect(os.path.join(ASSETS, "avertissement.png")); ax = (W - aw) / 2
    p.insert_image(fitz.Rect(ax, 424, ax + aw, 424 + ah), filename=os.path.join(ASSETS, "avertissement.png"))
    # Pied de page (en bas)
    fw = W - 56; fh = fw / _aspect(os.path.join(ASSETS, "pied.png")); fy = H - fh - 18
    p.insert_image(fitz.Rect(28, fy, 28 + fw, fy + fh), filename=os.path.join(ASSETS, "pied.png"))
    # Mentions légales — police auto-ajustée pour remplir la zone entre l'avertissement et le pied
    mtxt = mentions_cuisine(offer_key, montant, c)
    mrect = fitz.Rect(28, 424 + ah + 12, 452, fy - 10)
    mfs = 5.7
    for fs in (8.5, 8, 7.6, 7.2, 6.9, 6.6, 6.3, 6.0, 5.7):
        _tmp = fitz.open(); _lo = _tmp.new_page(width=W, height=H).insert_textbox(
            mrect, mtxt, fontsize=fs, fontfile=FONT_PATH, fontname="archivo"); _tmp.close()
        if _lo >= 0:
            mfs = fs; break
    p.insert_textbox(mrect, mtxt, fontsize=mfs, fontfile=FONT_PATH, fontname="archivo",
                     color=(0.3, 0.3, 0.3), align=3)
    return doc


# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "offers": list(CUISINE_OFFERS)}


@app.get("/api/render")
def api_render():
    desig = request.args.get("desig", "PROJET CUISINE")
    prec = request.args.get("prec", "")
    offer = request.args.get("offer", "10x_grat")
    fmt = request.args.get("fmt", "png")
    try:
        montant = float(request.args.get("montant", 5000) or 5000)
    except ValueError:
        montant = 5000.0
    try:
        eco = float(request.args.get("eco", 0) or 0)
    except ValueError:
        eco = 0.0
    if offer not in CUISINE_OFFERS:
        return {"error": "offre inconnue"}, 400
    doc = render_cuisine(desig, prec, montant, offer, eco=eco)
    if fmt == "pdf":
        buf = io.BytesIO(doc.tobytes(garbage=4, deflate=True,
                                     deflate_images=True, deflate_fonts=True)); buf.seek(0)
        return send_file(buf, mimetype="application/pdf", as_attachment=True,
                         download_name=f"ILV_cuisine_{offer}.pdf")
    png = doc[0].get_pixmap(matrix=fitz.Matrix(2.2, 2.2)).tobytes("png")
    return send_file(io.BytesIO(png), mimetype="image/png")


if __name__ == "__main__":
    print(f"ILV Cuisine → http://127.0.0.1:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
