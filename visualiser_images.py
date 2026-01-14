# -*- coding: utf-8 -*-
"""
Visualiseur d'images de la base de donnees labeling.duckdb

Exemples:
    python visualiser_images.py          # Affiche l'image ID 1
    python visualiser_images.py 5        # Affiche l'image ID 5
"""

import duckdb
import cv2
import numpy as np
from PIL import Image
import io
import sys

def obtenir_stats_image(conn, image_id):
    """Recupere les statistiques d'une image."""
    stats = conn.execute("""
        SELECT 
            COUNT(v.id) as nb_votes,
            SUM(CASE WHEN v.vote = 1 THEN 1 ELSE 0 END) as votes_oiseau,
            SUM(CASE WHEN v.vote = 0 THEN 1 ELSE 0 END) as votes_non_oiseau,
            AVG(CAST(v.vote AS DOUBLE)) as moyenne_vote
        FROM images i
        LEFT JOIN votes v ON i.id = v.image_id
        WHERE i.id = ?
        GROUP BY i.id
    """, [image_id]).fetchone()
    
    if stats and stats[0] > 0:
        nb_votes, votes_oiseau, votes_non_oiseau, moyenne = stats
        return {
            'nb_votes': nb_votes,
            'votes_oiseau': votes_oiseau,
            'votes_non_oiseau': votes_non_oiseau,
            'moyenne': moyenne
        }
    else:
        return {
            'nb_votes': 0,
            'votes_oiseau': 0,
            'votes_non_oiseau': 0,
            'moyenne': None
        }


def charger_image(conn, image_id):
    """Charge une image depuis la base de donnees."""
    result = conn.execute("""
        SELECT image_blob 
        FROM images 
        WHERE id = ?
    """, [image_id]).fetchone()
    
    if not result:
        return None
    
    # Convertir BLOB -> PIL -> OpenCV
    blob = result[0]
    pil_image = Image.open(io.BytesIO(blob))
    opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    return opencv_image


def afficher_image_avec_stats(image_id):
    """Affiche une image avec ses statistiques."""
    conn = duckdb.connect('labeling.duckdb')
    
    # Verifier que l'image existe
    total_images = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    
    if image_id < 1 or image_id > total_images:
        print(f"[ERREUR] L'image ID {image_id} n'existe pas.")
        print(f"[INFO] IDs valides : 1 a {total_images}")
        conn.close()
        return
    
    # Charger l'image
    img = charger_image(conn, image_id)
    
    if img is None:
        print(f"[ERREUR] Impossible de charger l'image ID {image_id}")
        conn.close()
        return
    
    # Recuperer les stats
    stats = obtenir_stats_image(conn, image_id)
    
    # Agrandir l'image pour meilleure visibilite
    scale = 3
    img_display = cv2.resize(img, (img.shape[1] * scale, img.shape[0] * scale), 
                             interpolation=cv2.INTER_NEAREST)
    
    # Creer une zone pour afficher les stats
    stats_height = 200
    canvas = np.ones((img_display.shape[0] + stats_height, img_display.shape[1], 3), 
                     dtype=np.uint8) * 255
    
    # Placer l'image
    canvas[0:img_display.shape[0], 0:img_display.shape[1]] = img_display
    
    # Afficher les statistiques
    y_offset = img_display.shape[0] + 30
    
    infos = [
        f"IMAGE ID: {image_id} / {total_images}",
        f"Nombre de votes: {stats['nb_votes']}",
        f"Votes 'Oiseau': {stats['votes_oiseau']}",
        f"Votes 'Non-Oiseau': {stats['votes_non_oiseau']}",
    ]
    
    if stats['moyenne'] is not None:
        infos.append(f"Moyenne: {stats['moyenne']:.2f}")
        
        # Determiner le consensus
        if stats['nb_votes'] >= 3:
            if stats['moyenne'] >= 0.7:
                consensus = "CONSENSUS: OISEAU"
                color = (0, 200, 0)  # Vert
            elif stats['moyenne'] <= 0.3:
                consensus = "CONSENSUS: NON-OISEAU"
                color = (0, 0, 200)  # Rouge
            else:
                consensus = "INCERTAIN (desaccord)"
                color = (0, 165, 255)  # Orange
            
            infos.append(consensus)
    else:
        infos.append("Statut: JAMAIS VOTEE")
        color = (128, 128, 128)  # Gris
    
    # Afficher les infos
    for i, info in enumerate(infos):
        cv2.putText(canvas, info, (10, y_offset + i * 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
    
    # Instructions
    cv2.putText(canvas, "Touches: <- (precedent) | -> (suivant) | Q (quitter) | [ID] + ENTREE (aller a ID)",
               (10, canvas.shape[0] - 10),
               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
    
    conn.close()
    
    return canvas, total_images


def main():
    """Point d'entree principal."""
    
    # ID de depart
    if len(sys.argv) > 1:
        try:
            current_id = int(sys.argv[1])
        except ValueError:
            print("[ERREUR] L'ID doit etre un nombre entier")
            sys.exit(1)
    else:
        current_id = 1
    
    print("=" * 70)
    print("VISUALISEUR D'IMAGES - labeling.duckdb")
    print("=" * 70)
    print("\nCommandes:")
    print("  Fleche GAUCHE  : Image precedente")
    print("  Fleche DROITE  : Image suivante")
    print("  Q              : Quitter")
    print("  Tapez un ID et appuyez sur ENTREE : Aller a cette image")
    print("=" * 70)
    
    window_name = 'Visualiseur Images - labeling.duckdb'
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    
    input_buffer = ""
    
    while True:
        # Afficher l'image actuelle
        canvas, total_images = afficher_image_avec_stats(current_id)
        
        if canvas is None:
            break
        
        cv2.imshow(window_name, canvas)
        
        # Gestion des touches
        key = cv2.waitKey(0) & 0xFF
        
        # Q: Quitter
        if key == ord('q') or key == ord('Q'):
            print("\n[OK] Fermeture du visualiseur")
            break
        
        # Fleche droite: Image suivante
        elif key == 83 or key == 3:  # Fleche droite
            if current_id < total_images:
                current_id += 1
            else:
                print(f"[INFO] Derniere image atteinte (ID {total_images})")
        
        # Fleche gauche: Image precedente
        elif key == 81 or key == 2:  # Fleche gauche
            if current_id > 1:
                current_id -= 1
            else:
                print("[INFO] Premiere image atteinte (ID 1)")
        
        # Entree: Aller a l'ID saisi
        elif key == 13:  # Entree
            if input_buffer:
                try:
                    new_id = int(input_buffer)
                    if 1 <= new_id <= total_images:
                        current_id = new_id
                        print(f"[OK] Navigation vers image ID {current_id}")
                    else:
                        print(f"[ERREUR] ID invalide. Valeurs acceptees: 1-{total_images}")
                except ValueError:
                    print("[ERREUR] Veuillez entrer un nombre valide")
                input_buffer = ""
        
        # Chiffres: Construire l'ID
        elif 48 <= key <= 57:  # Touches 0-9
            input_buffer += chr(key)
            print(f"[INPUT] ID saisi: {input_buffer}")
    
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
