# Boîte à outils Streamlit

Application Streamlit modulaire pour héberger plusieurs outils comptables. Le premier outil disponible est **Revue lettrage balance**.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Format CSV attendu (outil Revue lettrage balance)

Le fichier doit contenir les colonnes suivantes (avec exactement ces en-têtes) :

- Code Société
- No facture
- Code Tiers
- Raison sociale
- Libellé écriture
- Type de pièce
- Date facture
- Date d'échéance
- Montant Signé
- Devise comptabilisation
- Code du compte général
- Numéro d'écriture

Le parseur gère :
- séparateur `;` ou `,`
- dates françaises `dd/mm/yyyy`
- montants avec virgule décimale

## Limites et règles clés

- Seules les lignes avec `Code du compte général == "41100000"` et `Date d'échéance <= aujourd'hui` sont analysées.
- Les lettrages sont construits à l'intérieur d'un même **Code Tiers**.
- Tolérance par défaut : 0,05 €.
- Un lettrage doit inclure au moins un **RC** (Type de pièce == `RC`, négatif).
- Une ligne ne peut appartenir qu'à un seul lettrage final.
- La sélection finale privilégie la **proximité des dates d'échéance**.

## Ajouter un nouvel outil

1. Créer un nouveau dossier dans `tools/mon_outil/` avec :
   - `ui.py` : fonction `render()` pour l'interface Streamlit.
   - `logic.py` : logique pure testable.
2. Ajouter l'outil dans `app.py` :

```python
TOOLS = {
    "Revue lettrage balance": "tools.revue_lettrage_balance.ui",
    "Mon outil": "tools.mon_outil.ui",
}
```

3. Ajouter des tests unitaires dans `tests/` si nécessaire.

## Tests

```bash
pytest
```
