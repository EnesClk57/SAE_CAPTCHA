# Guide
## Résumé du Projet

Système de capchat  pour classifier d' images en **Oiseau** vs **Non-Oiseau**.

**Particularités :**
-  Stockage des images en **BLOB** dans DuckDB (pas de fichiers locaux)
-  Stratégie **Active Learning** intelligente (priorité : jamais vues → incertaines → aléatoires)
-  Interface graphique **OpenCV** (grille 3×3)
-  Export CSV pour analyse

---

##  Installation

### 1. Cloner et accéder au projet
```bash
git clone <url-du-repo>
cd SAE_CAPCHAT
```

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

**Dépendances installées :**
- `duckdb>=0.9.0` - Base de données embarquée
- `opencv-python>=4.8.0` - Interface graphique
- `Pillow>=10.0.0` - Traitement d'images
- `requests>=2.31.0` - Téléchargement dataset
- `numpy>=1.24.0` - Calculs numériques

---

##  Structure des Fichiers

###  Fichiers Principaux (Core)

| Fichier | Rôle | Utilisation |
|---------|------|-------------|
| **`database.py`** | Gestion BDD + Active Learning | Logique métier, requêtes SQL intelligentes |
| **`preprocess.py`** | ETL (Extract, Transform, Load) | `python preprocess.py` (1ère fois uniquement) |
| **`main.py`** | Interface de labellisation | `python main.py` (labelliser les images) |

### Fichiers Utilitaires

| Fichier | Rôle | Utilisation |
|---------|------|-------------|
| **`exporter_donnees.py`** | Export CSV pour analyse | `python exporter_donnees.py` |
| **`visualiser_images.py`** | Visualiser les images de la BDD | `python visualiser_images.py` |

### Documentation & Config

| Fichier | Description |
|---------|-------------|
| **`requirements.txt`** | Liste des dépendances Python |
| **`.gitignore`** | Exclusions Git (BDD, cache, venv) |

### Base de Données

| Fichier | Description |
|---------|-------------|
| **`labeling.duckdb`** | Base de données DuckDB (images BLOB + votes) |

**Schéma :**
- Table `images` : `id`, `image_blob`
- Table `votes` : `id`, `image_id`, `vote` (0/1), `timestamp`

---

## Workflow 

### Première utilisation
```bash
# 1. Charger le dataset
python preprocess.py

# 2. Labelliser les images
python main.py
```

### Utilisation courante
```bash
# Labelliser
python main.py

# Exporter pour analyse
python exporter_donnees.py
```

---

## Fichiers CSV Exportés

| Fichier | Contenu | Utilisation |
|---------|---------|-------------|
| **`votes.csv`** | Tous les votes individuels | Analyse temporelle, traçabilité |
| **`statistiques.csv`** | Stats par image (nb votes, moyenne, compteurs) | Vue d'ensemble |
| **`resume.csv`** | Classification finale (OISEAU/NON-OISEAU/INCERTAIN) | Résultats finaux |


##  Stratégie 

Le système ne sélectionne **pas aléatoirement** les images. Ordre de priorité :

1. **Priorité 0** : Images jamais vues (0 votes)
2. **Priorité 1** : Images incertaines (moyenne proche de 0.5)
3. **Priorité 2** : Reste (aléatoire)

---

## Commandes Utiles

### Inspecter la base de données
```bash
# Ouvrir DuckDB CLI
duckdb labeling.duckdb
```
