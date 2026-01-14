"""
Fonctionnalités:
- Affichage d'une mosaïque 3x3 d'images (récupérées intelligemment)
- Sélection/désélection par clic (cadre vert)
- Validation par Entrée/Espace
- Enregistrement des votes (1 = Oiseau, 0 = Non-Oiseau)
- Affichage des statistiques de progression
"""

import cv2
import numpy as np
from PIL import Image
import io
from typing import List, Tuple, Set
import database

# Configuration de l'interface
GRID_SIZE = 3  # Grille 3x3
IMAGE_SIZE = 150  # Taille des images
PADDING = 10  # Espacement entre les images
BORDER_WIDTH = 4  # Épaisseur du cadre de sélection
COLOR_SELECTED = (0, 255, 0)  # Vert pour sélection
COLOR_BORDER = (200, 200, 200)  # Gris pour bordure normale

# Calcul des dimensions de la fenêtre
WINDOW_WIDTH = GRID_SIZE * IMAGE_SIZE + (GRID_SIZE + 1) * PADDING
WINDOW_HEIGHT = GRID_SIZE * IMAGE_SIZE + (GRID_SIZE + 1) * PADDING + 100  # +100 pour les stats


class InterfaceLabeling:
    """
    Interface de labélisation avec gestion des clics et validation.
    """
    
    def __init__(self):
        """Initialise l'interface."""
        self.images_data: List[Tuple[int, bytes]] = []  # [(image_id, blob), ...]
        self.images_affichees: List[np.ndarray] = []  # Images converties pour OpenCV
        self.selections: Set[int] = set()  # Indices des images sélectionnées
        self.canvas = None
        self.session_votes = 0  # Compteur de votes pour cette session
        
    def blob_vers_opencv(self, blob: bytes) -> np.ndarray:
        """
        Convertit un BLOB en image OpenCV (numpy array).
        
        Args:
            blob: Données binaires de l'image
        
        Returns:
            Image au format OpenCV (BGR)
        """
        # Conversion BLOB -> PIL -> OpenCV
        pil_image = Image.open(io.BytesIO(blob))
        opencv_image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
        return opencv_image
    
    def charger_batch(self) -> bool:
        """
        Charge un nouveau batch d'images depuis la base de données.
        
        Returns:
            True si des images ont été chargées, False sinon
        """
        # Récupération des images intelligentes 
        self.images_data = database.get_images_intelligentes(GRID_SIZE * GRID_SIZE)
        
        if not self.images_data:
            return False
        
        # Conversion des BLOB en images OpenCV
        self.images_affichees = [
            self.blob_vers_opencv(blob) for _, blob in self.images_data
        ]
        
        # Réinitialisation des sélections
        self.selections.clear()
        
        return True
    
    def dessiner_interface(self) -> np.ndarray:
        """
        Dessine l'interface complète (mosaïque + statistiques).
        
        Returns:
            Canvas complet à afficher
        """
        # Création du canvas
        canvas = np.ones((WINDOW_HEIGHT, WINDOW_WIDTH, 3), dtype=np.uint8) * 255
        
        # Dessin de la grille d'images
        for i, img in enumerate(self.images_affichees):
            row = i // GRID_SIZE
            col = i % GRID_SIZE
            
            # Position de l'image
            x = PADDING + col * (IMAGE_SIZE + PADDING)
            y = PADDING + row * (IMAGE_SIZE + PADDING)
            
            # Placement de l'image
            canvas[y:y+IMAGE_SIZE, x:x+IMAGE_SIZE] = img
            
            # Dessin du cadre (vert si sélectionné, gris sinon)
            color = COLOR_SELECTED if i in self.selections else COLOR_BORDER
            cv2.rectangle(
                canvas, 
                (x - BORDER_WIDTH//2, y - BORDER_WIDTH//2),
                (x + IMAGE_SIZE + BORDER_WIDTH//2, y + IMAGE_SIZE + BORDER_WIDTH//2),
                color, 
                BORDER_WIDTH
            )
        
        # Zone de statistiques
        stats_y = GRID_SIZE * IMAGE_SIZE + (GRID_SIZE + 1) * PADDING + 10
        
        # Récupération des statistiques
        stats = database.get_statistiques()
        
        # Affichage des informations
        infos = [
            f"Images selectionnees: {len(self.selections)}/{len(self.images_affichees)}",
            f"Total images: {stats['total_images']} | Labellisees: {stats['images_labellisees']} ({stats['taux_labellisation']}%)",
            f"Votes cette session: {self.session_votes}",
            "",
            "CLIC GAUCHE: Selectionner/Deselectionner | ENTREE/ESPACE: Valider | Q: Quitter"
        ]
        
        for i, info in enumerate(infos):
            cv2.putText(
                canvas,
                info,
                (10, stats_y + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 0, 0),
                1
            )
        
        return canvas
    
    def gerer_clic(self, x: int, y: int) -> None:
        """
        Gère un clic de souris sur la mosaïque.
        
        Args:
            x: Coordonnée X du clic
            y: Coordonnée Y du clic
        """
        # Calcul de l'indice de l'image cliquée
        col = (x - PADDING) // (IMAGE_SIZE + PADDING)
        row = (y - PADDING) // (IMAGE_SIZE + PADDING)
        
        # Vérification des limites
        if 0 <= row < GRID_SIZE and 0 <= col < GRID_SIZE:
            index = row * GRID_SIZE + col
            
            if index < len(self.images_affichees):
                # Toggle de la sélection
                if index in self.selections:
                    self.selections.remove(index)
                else:
                    self.selections.add(index)
    
    def valider_page(self) -> None:
        """
        Valide la page actuelle et enregistre les votes.
        
        Logique:
        - Image sélectionnée (cadre vert) -> vote = 1 (Oiseau)
        - Image non sélectionnée -> vote = 0 (Non-Oiseau)
        """
        # Préparation des votes
        votes = []
        
        for i, (image_id, _) in enumerate(self.images_data):
            vote = 1 if i in self.selections else 0
            votes.append((image_id, vote))
        
        # Sauvegarde dans la base
        database.sauvegarder_votes(votes)
        
        # Mise à jour du compteur de session
        self.session_votes += len(votes)
        
        print(f"[OK] Page validee: {len(self.selections)} oiseaux detectes sur {len(votes)} images")
    
    def lancer(self) -> None:
        """
        Lance l'interface graphique (boucle principale).
        """
        print("=" * 60)
        print("INTERFACE DE LABÉLISATION")
        print("=" * 60)
        print("\nInstructions:")
        print("  - CLIC GAUCHE: Sélectionner/Désélectionner une image")
        print("  - ENTRÉE ou ESPACE: Valider la page et passer à la suivante")
        print("  - Q: Quitter l'application")
        print("\nStratégie de sélection:")
        print("  1. Images jamais vues (priorité)")
        print("  2. Images incertaines (désaccord)")
        print("  3. Images aléatoires")
        print("=" * 60)
        
        # Vérification de la base
        stats = database.get_statistiques()
        if stats['total_images'] == 0:
            print("\n[ERREUR] Aucune image en base. Lancez d'abord: python preprocess.py")
            return
        
        # Création de la fenêtre
        cv2.namedWindow('Labeling - Oiseau vs Non-Oiseau', cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback('Labeling - Oiseau vs Non-Oiseau', self.callback_souris)
        
        # Chargement du premier batch
        if not self.charger_batch():
            print("\n[ERREUR] Impossible de charger des images.")
            return
        
        # Boucle principale
        while True:
            # Dessin de l'interface
            self.canvas = self.dessiner_interface()
            cv2.imshow('Labeling - Oiseau vs Non-Oiseau', self.canvas)
            
            # Gestion des touches
            key = cv2.waitKey(1) & 0xFF
            
            # Q: Quitter
            if key == ord('q') or key == ord('Q'):
                print("\n[>>] Fermeture de l'application")
                break
            
            # Entrée ou Espace: Valider
            elif key == 13 or key == 32:  # 13 = Entrée, 32 = Espace
                self.valider_page()
                
                # Chargement du batch suivant
                if not self.charger_batch():
                    print("\n[OK] Toutes les images ont ete labellisees!")
                    print(f"  Total de votes cette session: {self.session_votes}")
                    break
        
        # Fermeture
        cv2.destroyAllWindows()
        
        # Statistiques finales
        print("\n" + "=" * 60)
        print("SESSION TERMINEE")
        print("=" * 60)
        stats = database.get_statistiques()
        print(f"[OK] Images labellisees: {stats['images_labellisees']}/{stats['total_images']} ({stats['taux_labellisation']}%)")
        print(f"[OK] Total de votes: {stats['total_votes']}")
        print(f"[OK] Votes cette session: {self.session_votes}")
    
    def callback_souris(self, event, x, y, flags, param):
        """
        Callback pour les événements de souris.
        
        Args:
            event: Type d'événement
            x, y: Coordonnées du clic
            flags, param: Paramètres additionnels (non utilisés)
        """
        if event == cv2.EVENT_LBUTTONDOWN:
            self.gerer_clic(x, y)


def main():
    """Point d'entrée principal."""
    # Initialisation de la base (au cas où)
    database.init_db()
    
    # Lancement de l'interface
    interface = InterfaceLabeling()
    interface.lancer()


if __name__ == "__main__":
    main()
