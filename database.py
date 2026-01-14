"""
Module de gestion de la base de données DuckDB .

Architecture:
- Table 'images': Stockage des images en BLOB
- Table 'votes': Historique de tous les votes utilisateurs

Stratégie :
1. Priorité 1 (Exploration): Images jamais montrées (0 votes)
2. Priorité 2 (Incertitude): Images avec désaccord entre utilisateurs
3. Priorité 3: Reste des images (aléatoire)
"""

import duckdb
from datetime import datetime
from typing import List, Tuple, Optional
import io

# Nom du fichier de base de données
DB_PATH = "labeling.duckdb"


def init_db() -> None:
    """
    Initialise la base de données avec le schéma relationnel.
    
    Crée deux tables:
    - images: Stocke les images en BLOB
    - votes: Stocke l'historique des votes (FK vers images)
    """
    conn = duckdb.connect(DB_PATH)
    
    # Création des séquences pour auto-incrémentation
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_images_id START 1")
    conn.execute("CREATE SEQUENCE IF NOT EXISTS seq_votes_id START 1")
    
    # Table des images (stockage BLOB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER DEFAULT nextval('seq_images_id'),
            image_blob BLOB NOT NULL,
            PRIMARY KEY (id)
        )
    """)
    
    # Table des votes (historique complet)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER DEFAULT nextval('seq_votes_id'),
            image_id INTEGER NOT NULL,
            vote INTEGER NOT NULL CHECK (vote IN (0, 1)),
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    """)
    
    conn.close()
    print("[OK] Base de donnees initialisee avec succes")


def ajouter_image_brute(blob: bytes) -> int:
    """
    Ajoute une image en BLOB dans la table images.
    
    Args:
        blob: Données binaires de l'image (format PNG/JPEG)
    
    Returns:
        L'ID de l'image insérée
    """
    conn = duckdb.connect(DB_PATH)
    
    # Insertion de l'image
    result = conn.execute("""
        INSERT INTO images (image_blob)
        VALUES (?)
        RETURNING id
    """, [blob]).fetchone()
    
    image_id = result[0]
    conn.close()
    
    return image_id


def sauvegarder_votes(liste_tuples: List[Tuple[int, int]]) -> None:
    """
    Enregistre une liste de votes dans la base de données.
    
    Args:
        liste_tuples: Liste de tuples (image_id, vote)
                     vote = 1 pour "Oiseau", 0 pour "Non-Oiseau"
    
    Exemple:
        sauvegarder_votes([(1, 1), (2, 0), (3, 1)])
    """
    if not liste_tuples:
        return
    
    conn = duckdb.connect(DB_PATH)
    
    # Insertion en batch pour performance
    conn.executemany("""
        INSERT INTO votes (image_id, vote, timestamp)
        VALUES (?, ?, ?)
    """, [(img_id, vote, datetime.now()) for img_id, vote in liste_tuples])
    
    conn.close()
    print(f"[OK] {len(liste_tuples)} votes enregistres")


def get_images_intelligentes(batch_size: int = 9) -> List[Tuple[int, bytes]]:
    """
    Récupère un batch d'images.
    
    Stratégie de sélection (par ordre de priorité):
    1. Images jamais vues (LEFT JOIN avec votes WHERE NULL)
    2. Images incertaines (moyenne de votes proche de 0.5)
       - Calcul: ABS(AVG(vote) - 0.5) → Plus proche de 0 = plus d'incertitude
    3. Images restantes (aléatoire)
    
    Args:
        batch_size: Nombre d'images à récupérer (défaut: 9 pour grille 3x3)
    
    Returns:
        Liste de tuples (image_id, image_blob)
    
    Exemple de requête SQL:
        - CTE 'stats_votes': Calcule statistiques par image
        - CTE 'images_jamais_vues': Images sans aucun vote
        - CTE 'images_incertaines': Images triées par incertitude
        - UNION ALL: Combine les 3 priorités
        - ORDER BY priorite, RANDOM(): Tri final
    """
    conn = duckdb.connect(DB_PATH)
    
    # Requête SQL complexe avec Common Table Expressions (CTE)
    query = """
    WITH stats_votes AS (
        -- Calcul des statistiques de votes par image
        SELECT 
            image_id,
            COUNT(*) as nb_votes,
            AVG(CAST(vote AS DOUBLE)) as moyenne_vote,
            ABS(AVG(CAST(vote AS DOUBLE)) - 0.5) as distance_incertitude
        FROM votes
        GROUP BY image_id
    ),
    images_jamais_vues AS (
        -- Priorité 1: Images jamais montrées (exploration)
        SELECT 
            i.id, 
            i.image_blob, 
            0 as priorite,
            RANDOM() as ordre_aleatoire
        FROM images i
        LEFT JOIN votes v ON i.id = v.image_id
        WHERE v.id IS NULL
    ),
    images_incertaines AS (
        -- Priorité 2: Images avec désaccord (incertitude)
        -- Plus distance_incertitude est proche de 0, plus il y a de désaccord
        -- Ajout d'un tri aléatoire pour augmenter la diversité des images affichées
        -- Ratio aléatoire augmenté pour plus de variété
        SELECT 
            i.id, 
            i.image_blob, 
            1 as priorite,
            sv.distance_incertitude + (RANDOM() * 0.5) as ordre_aleatoire
        FROM images i
        JOIN stats_votes sv ON i.id = sv.image_id
        WHERE sv.nb_votes > 0
    ),
    images_restantes AS (
        -- Priorité 3: Reste des images (aléatoire)
        SELECT 
            i.id, 
            i.image_blob, 
            2 as priorite,
            RANDOM() as ordre_aleatoire
        FROM images i
        WHERE i.id NOT IN (SELECT id FROM images_jamais_vues)
          AND i.id NOT IN (SELECT id FROM images_incertaines)
    )
    -- Combinaison des 3 sources avec tri par priorité
    SELECT id, image_blob 
    FROM (
        SELECT * FROM images_jamais_vues
        UNION ALL
        SELECT * FROM images_incertaines
        UNION ALL
        SELECT * FROM images_restantes
    )
    ORDER BY priorite ASC, ordre_aleatoire ASC
    LIMIT ?
    """
    
    results = conn.execute(query, [batch_size]).fetchall()
    conn.close()
    
    return results


def get_statistiques() -> dict:
    """
    Récupère des statistiques sur l'état de la labélisation.
    
    Returns:
        Dictionnaire avec:
        - total_images: Nombre total d'images
        - images_labellisees: Nombre d'images ayant au moins 1 vote
        - total_votes: Nombre total de votes
        - taux_labellisation: Pourcentage d'images labellisées
    """
    conn = duckdb.connect(DB_PATH)
    
    stats = conn.execute("""
        SELECT 
            (SELECT COUNT(*) FROM images) as total_images,
            (SELECT COUNT(DISTINCT image_id) FROM votes) as images_labellisees,
            (SELECT COUNT(*) FROM votes) as total_votes
    """).fetchone()
    
    conn.close()
    
    total_images, images_labellisees, total_votes = stats
    taux = (images_labellisees / total_images * 100) if total_images > 0 else 0
    
    return {
        'total_images': total_images,
        'images_labellisees': images_labellisees,
        'total_votes': total_votes,
        'taux_labellisation': round(taux, 2)
    }

if __name__ == "__main__":
    # Test d'initialisation
    init_db()
    stats = get_statistiques()
    print(f"\nStatistiques:")
    print(f"  - Total images: {stats['total_images']}")
    print(f"  - Images labellisées: {stats['images_labellisees']}")
    print(f"  - Total votes: {stats['total_votes']}")
    print(f"  - Taux de labellisation: {stats['taux_labellisation']}%")
