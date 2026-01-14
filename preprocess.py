""" 
système de labélisation.
Fonctionnalités:
- Téléchargement automatique du ZIP depuis Google Drive
- Extraction et redimensionnement des images (150x150)
- Conversion en BLOB (format PNG)
- Insertion dans la base de données DuckDB
- Nettoyage des fichiers temporaires
"""

import requests
import zipfile
import os
import shutil
from pathlib import Path
from PIL import Image
import io
from typing import Optional
import database

# URL du dataset (Google Drive)
# Format: https://drive.google.com/uc?export=download&id=FILE_ID
GOOGLE_DRIVE_FILE_ID = "1ynZLpShH5VriNBy6ohAmSDTj_be38s3d"
URL_DATASET_ZIP = f"https://drive.google.com/uc?export=download&id={GOOGLE_DRIVE_FILE_ID}"

# Configuration
TEMP_DIR = "temp_images"
TARGET_SIZE = (150, 150)
FORMATS_SUPPORTES = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}


def telecharger_zip(url: str, destination: str) -> bool:
    """
    Télécharge un fichier ZIP depuis une URL (avec support Google Drive).
    
    Args:
        url: URL du fichier ZIP
        destination: Chemin de destination pour le fichier téléchargé
    
    Returns:
        True si le téléchargement a réussi, False sinon
    """
    print(f"[>>] Telechargement du dataset depuis Google Drive...")
    
    try:
        # Session pour gérer les redirections Google Drive
        session = requests.Session()
        response = session.get(url, stream=True)
        
        # Gestion du warning Google Drive pour les gros fichiers
        if 'download_warning' in response.cookies:
            params = {'confirm': response.cookies['download_warning']}
            response = session.get(url, params=params, stream=True)
        
        # Vérification du statut
        response.raise_for_status()
        
        # Téléchargement avec barre de progression
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r  Progression: {progress:.1f}%", end='')
        
        print(f"\n[OK] Telechargement termine ({downloaded / 1024 / 1024:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors du telechargement: {e}")
        return False


def extraire_zip(zip_path: str, extract_dir: str) -> bool:
    """
    Extrait un fichier ZIP dans un répertoire.
    
    Args:
        zip_path: Chemin du fichier ZIP
        extract_dir: Répertoire de destination
    
    Returns:
        True si l'extraction a réussi, False sinon
    """
    print(f"[>>] Extraction du ZIP...")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Compter les fichiers extraits
        nb_fichiers = sum(1 for _ in Path(extract_dir).rglob('*') if _.is_file())
        print(f"[OK] {nb_fichiers} fichiers extraits")
        return True
        
    except Exception as e:
        print(f"[ERREUR] Erreur lors de l'extraction: {e}")
        return False


def image_vers_blob(image_path: str) -> Optional[bytes]:
    """
    Charge une image, la redimensionne et la convertit en BLOB.
    
    Args:
        image_path: Chemin de l'image source
    
    Returns:
        Données BLOB (PNG) ou None en cas d'erreur
    """
    try:
        # Chargement et redimensionnement
        img = Image.open(image_path)
        img = img.convert('RGB')  # Conversion en RGB (au cas où)
        img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
        
        # Conversion en BLOB (format PNG en mémoire)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        blob = buffer.getvalue()
        
        return blob
        
    except Exception as e:
        print(f"  [!] Erreur avec {image_path}: {e}")
        return None


def traiter_images(source_dir: str) -> int:
    """
    Parcourt récursivement un répertoire, traite les images et les insère en base.
    
    Args:
        source_dir: Répertoire contenant les images
    
    Returns:
        Nombre d'images traitées avec succès
    """
    print(f"[>>] Traitement des images...")
    
    # Recherche récursive de toutes les images
    images_paths = []
    for ext in FORMATS_SUPPORTES:
        images_paths.extend(Path(source_dir).rglob(f'*{ext}'))
        images_paths.extend(Path(source_dir).rglob(f'*{ext.upper()}'))
    
    total = len(images_paths)
    print(f"  {total} images trouvees")
    
    if total == 0:
        print("  [!] Aucune image trouvee dans le repertoire")
        return 0
    
    # Traitement et insertion
    compteur_succes = 0
    
    for i, img_path in enumerate(images_paths, 1):
        # Conversion en BLOB
        blob = image_vers_blob(str(img_path))
        
        if blob:
            # Insertion dans la base
            image_id = database.ajouter_image_brute(blob)
            compteur_succes += 1
            
            # Affichage de la progression
            if i % 10 == 0 or i == total:
                print(f"\r  Progression: {i}/{total} ({compteur_succes} réussies)", end='')
    
    print(f"\n[OK] {compteur_succes} images inserees en base de donnees")
    return compteur_succes


def nettoyer_fichiers_temporaires(temp_dir: str, zip_path: str) -> None:
    """
    Supprime les fichiers temporaires (ZIP et répertoire d'extraction).
    
    Args:
        temp_dir: Répertoire temporaire à supprimer
        zip_path: Fichier ZIP à supprimer
    """
    print(f"[>>] Nettoyage des fichiers temporaires...")
    
    try:
        # Suppression du répertoire temporaire
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"  [OK] Repertoire {temp_dir} supprime")
        
        # Suppression du ZIP
        if os.path.exists(zip_path):
            os.remove(zip_path)
            print(f"  [OK] Fichier {zip_path} supprime")
            
    except Exception as e:
        print(f"  [!] Erreur lors du nettoyage: {e}")


def main():
    """
    Pipeline complet de prétraitement:
    1. Initialisation de la base de données
    2. Téléchargement du ZIP
    3. Extraction
    4. Traitement et insertion des images
    5. Nettoyage
    """
    print("=" * 60)
    print("PREPROCESSING - Chargement du dataset")
    print("=" * 60)
    
    # Étape 1: Initialisation de la base
    print("\n[1/5] Initialisation de la base de données")
    database.init_db()
    
    # Vérifier si des images existent déjà
    stats = database.get_statistiques()
    if stats['total_images'] > 0:
        reponse = input(f"\n[!] La base contient deja {stats['total_images']} images. Continuer? (o/N): ")
        if reponse.lower() != 'o':
            print("Annulation.")
            return
    
    # Étape 2: Téléchargement
    print("\n[2/5] Téléchargement du dataset")
    zip_path = "dataset.zip"
    
    if not telecharger_zip(URL_DATASET_ZIP, zip_path):
        print("\n[ERREUR] Echec du telechargement. Verifiez l'URL ou votre connexion.")
        return
    
    # Étape 3: Extraction
    print("\n[3/5] Extraction du ZIP")
    
    if not extraire_zip(zip_path, TEMP_DIR):
        print("\n[ERREUR] Echec de l'extraction.")
        nettoyer_fichiers_temporaires(TEMP_DIR, zip_path)
        return
    
    # Étape 4: Traitement des images
    print("\n[4/5] Traitement et insertion en base")
    nb_images = traiter_images(TEMP_DIR)
    
    if nb_images == 0:
        print("\n[ERREUR] Aucune image n'a pu etre traitee.")
        nettoyer_fichiers_temporaires(TEMP_DIR, zip_path)
        return
    
    # Étape 5: Nettoyage
    print("\n[5/5] Nettoyage")
    nettoyer_fichiers_temporaires(TEMP_DIR, zip_path)
    
    # Statistiques finales
    print("\n" + "=" * 60)
    print("PREPROCESSING TERMINÉ")
    print("=" * 60)
    stats = database.get_statistiques()
    print(f"[OK] {stats['total_images']} images pretes pour la labelisation")
    print(f"\nVous pouvez maintenant lancer: python main.py")


if __name__ == "__main__":
    main()
