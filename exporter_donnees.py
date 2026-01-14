# -*- coding: utf-8 -*-
"""
Export simple et robuste des donnees de labeling.duckdb vers CSV

Usage: python exporter_donnees.py
"""

import duckdb
import os
from datetime import datetime

def exporter_donnees():
    """Exporte toutes les donnees en CSV."""
    
    # Nom du dossier d'export
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dossier = f"export_{timestamp}"
    
    try:
        # Creer le dossier
        os.makedirs(dossier, exist_ok=True)
        print(f"\n[EXPORT] Dossier: {dossier}/\n")
        
        # Connexion a la base
        conn = duckdb.connect('labeling.duckdb', read_only=True)
        
        # 1. Export des votes
        print("[1/3] Export des votes...")
        conn.execute(f"""
            COPY (
                SELECT id, image_id, vote, timestamp
                FROM votes
                ORDER BY timestamp DESC
            ) TO '{dossier}/votes.csv' (HEADER, DELIMITER ',')
        """)
        nb_votes = conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        print(f"      {nb_votes} votes exportes\n")
        
        # 2. Export des statistiques par image
        print("[2/3] Export des statistiques...")
        conn.execute(f"""
            COPY (
                SELECT 
                    i.id as image_id,
                    COALESCE(COUNT(v.id), 0) as nb_votes,
                    COALESCE(ROUND(AVG(CAST(v.vote AS DOUBLE)), 3), 0) as moyenne,
                    COALESCE(SUM(CASE WHEN v.vote = 1 THEN 1 ELSE 0 END), 0) as votes_oiseau,
                    COALESCE(SUM(CASE WHEN v.vote = 0 THEN 1 ELSE 0 END), 0) as votes_non_oiseau
                FROM images i
                LEFT JOIN votes v ON i.id = v.image_id
                GROUP BY i.id
                ORDER BY i.id
            ) TO '{dossier}/statistiques.csv' (HEADER, DELIMITER ',')
        """)
        nb_images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        print(f"      {nb_images} images traitees\n")
        
        # 3. Export du resume (consensus + incertitudes)
        print("[3/3] Export du resume...")
        conn.execute(f"""
            COPY (
                SELECT 
                    image_id,
                    nb_votes,
                    moyenne,
                    CASE 
                        WHEN nb_votes = 0 THEN 'Jamais votee'
                        WHEN nb_votes < 3 THEN 'Pas assez de votes'
                        WHEN moyenne >= 0.7 THEN 'OISEAU'
                        WHEN moyenne <= 0.3 THEN 'NON-OISEAU'
                        ELSE 'INCERTAIN'
                    END as classification
                FROM (
                    SELECT 
                        i.id as image_id,
                        COALESCE(COUNT(v.id), 0) as nb_votes,
                        COALESCE(ROUND(AVG(CAST(v.vote AS DOUBLE)), 3), 0) as moyenne
                    FROM images i
                    LEFT JOIN votes v ON i.id = v.image_id
                    GROUP BY i.id
                )
                ORDER BY 
                    CASE classification
                        WHEN 'OISEAU' THEN 1
                        WHEN 'NON-OISEAU' THEN 2
                        WHEN 'INCERTAIN' THEN 3
                        WHEN 'Pas assez de votes' THEN 4
                        ELSE 5
                    END,
                    image_id
            ) TO '{dossier}/resume.csv' (HEADER, DELIMITER ',')
        """)
        print(f"      Resume genere\n")
        
        # Fermeture
        conn.close()
        
        # Succes
        print("=" * 60)
        print("[OK] EXPORT TERMINE")
        print("=" * 60)
        print(f"\nFichiers exportes dans: {dossier}/")
        print("  - votes.csv         : Tous les votes")
        print("  - statistiques.csv  : Stats par image")
        print("  - resume.csv        : Classification finale")
        print()
        
        return True
        
    except FileNotFoundError:
        print("[ERREUR] Fichier labeling.duckdb introuvable")
        return False
    
    except Exception as e:
        print(f"[ERREUR] {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("EXPORT DES DONNEES - labeling.duckdb")
    print("=" * 60)
    
    success = exporter_donnees()
    
    if not success:
        exit(1)
