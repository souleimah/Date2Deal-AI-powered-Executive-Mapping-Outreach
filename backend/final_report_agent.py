import json
import os
import glob
from datetime import datetime
import re
import requests  # Pour l'appel à l'API Gemini
import sys  # Pour récupérer les arguments de la ligne de commande

# --- Configuration ---
# Remplacez par votre clé API Gemini. Gardez-la confidentielle.
GEMINI_API_KEY = "-"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + GEMINI_API_KEY

# Chemins des dossiers (relatifs à l'emplacement de ce script)
LINKEDIN_REPORTS_DIR = os.path.dirname(os.path.abspath(__file__))
YOUTUBE_REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube")


def call_gemini_api(prompt_text):
    """Appelle l'API Gemini pour générer du contenu."""
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": 0.2,  # Température basse pour des résultats factuels et cohérents
            "maxOutputTokens": 8192, # Capacité maximale pour des rapports détaillés
        }
    }
    try:
        response = requests.post(GEMINI_API_URL, headers=headers, json=data)
        response.raise_for_status()  # Lève une exception pour les codes d'état HTTP d'erreur
        result = response.json()
        if result and result.get('candidates'):
            for candidate in result['candidates']:
                if candidate.get('content') and candidate['content'].get('parts'):
                    for part in candidate['content']['parts']:
                        if part.get('text'):
                            return part['text'].strip()
        print("Avertissement : La réponse de l'API Gemini est valide mais ne contient pas de contenu textuel.")
        return "Aucune réponse textuelle de Gemini."
    except requests.exceptions.HTTPError as http_err:
        print(f"Erreur HTTP lors de l'appel à l'API Gemini: {http_err}")
        print(f"Corps de la réponse : {response.text}")
        return f"Erreur API Gemini: {http_err}"
    except Exception as e:
        print(f"Erreur lors de l'appel à l'API Gemini: {e}")
        return f"Erreur API Gemini: {e}"


def load_linkedin_reports(person_name):
    """Charge les rapports LinkedIn (fichiers JSON) pour une personne donnée."""
    linkedin_profiles = []
    safe_person_name = person_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    search_pattern = os.path.join(LINKEDIN_REPORTS_DIR, f"{safe_person_name}*.json")
    print(f"Recherche des rapports LinkedIn avec le motif '{search_pattern}'...")

    files = glob.glob(search_pattern)
    if not files:
        print(f"Aucun rapport LinkedIn trouvé pour '{person_name}'.")
        return []

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "name" in data and "job_title" in data:
                    linkedin_profiles.append(data)
                    print(f"Chargé profil LinkedIn: {data.get('name')} de {os.path.basename(file_path)}")
                else:
                    print(f"Fichier LinkedIn ignoré (format inattendu): {os.path.basename(file_path)}")
        except json.JSONDecodeError as e:
            print(f"Erreur de décodage JSON pour {os.path.basename(file_path)}: {e}")
        except Exception as e:
            print(f"Erreur lors du chargement de {os.path.basename(file_path)}: {e}")
    return linkedin_profiles


def load_youtube_reports(person_name):
    """Charge les rapports YouTube (fichiers Markdown) pour une personne donnée."""
    youtube_analyses = []
    safe_person_name = person_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    search_pattern = os.path.join(YOUTUBE_REPORTS_DIR, f"youtube_analysis_{safe_person_name}*.md")
    print(f"Recherche des rapports YouTube avec le motif '{search_pattern}'...")

    files = glob.glob(search_pattern)
    if not files:
        print(f"Aucun rapport YouTube trouvé pour '{person_name}'.")
        return []

    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                youtube_analyses.append(content)
                print(f"Chargé rapport YouTube: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Erreur lors du chargement de {os.path.basename(file_path)}: {e}")
    return youtube_analyses


def prepare_data_for_llm(linkedin_data, youtube_data):
    """Prépare et formate les données combinées pour l'analyse par le LLM."""
    combined_text = []

    if linkedin_data:
        combined_text.append("--- DONNÉES LINKEDIN ---")
        for i, profile in enumerate(linkedin_data):
            # Utilise json.dumps pour une sérialisation propre et complète du profil
            combined_text.append(f"### Profil LinkedIn {i + 1} de {profile.get('name', 'Nom Inconnu')}")
            combined_text.append(json.dumps(profile, indent=2, ensure_ascii=False))
            combined_text.append("-" * 30)
        combined_text.append("\n")

    if youtube_data:
        combined_text.append("--- DONNÉES YOUTUBE ---")
        for i, analysis in enumerate(youtube_data):
            combined_text.append(f"### Analyse YouTube {i + 1}")
            combined_text.append(f"Contenu Complet de l'Analyse YouTube:\n{analysis}")
            combined_text.append("-" * 30)
        combined_text.append("\n")

    return "\n".join(combined_text)


def generate_final_report(combined_data_text, person_name):
    """
    Demande à Gemini de générer un rapport final consolidé en suivant une structure précise.
    """
    # --- DÉBUT DE LA MODIFICATION PRINCIPALE ---
    prompt = f"""
    Tu es un analyste expert en intelligence économique de classe mondiale. Ta mission est de synthétiser toutes les informations disponibles à partir des données brutes fournies (extraits de LinkedIn, analyses YouTube, etc.) pour créer un rapport de profilage final, structuré et détaillé pour {person_name}.

    Le rapport doit suivre PRÉCISÉMENT la structure et le style demandés ci-dessous.

    **DONNÉES BRUTES À ANALYSER :**
    ---
    {combined_data_text}
    ---

    **INSTRUCTIONS ET STRUCTURE DU RAPPORT FINAL (FORMAT MARKDOWN OBLIGATOIRE) :**

    Rédige le rapport de profilage pour **{person_name}**. Sois factuel, analytique et base-toi UNIQUEMENT sur les données fournies. Si une information n'est pas disponible pour une section, indique "Information non disponible". Ne crée aucune information.

    # RAPPORT DE PROFILAGE FINAL SUR {person_name.upper()}

    ## 1. RÉSUMÉ EXÉCUTIF
    Rédige un paragraphe de synthèse qui résume le profil de {person_name} : son rôle actuel, son secteur, ses années d'expérience (si mentionnées), son expertise principale et sa mission ou sa particularité distinctive.

    ##2.lien réseaux sociaux 
    * **lister tous les profils sociaux trouvés avec leurs URLs
    * **organisées par les platformes (linkedin, Twitter/X, Facebook, Instagram, GitHub,etc)
    ## 3. RÔLE ACTUEL ET VISION
    * **Rôles actuels** : Liste le(s) poste(s) actuel(s), l'entreprise et les dates (si disponibles).
    * **Vision et Mission** : Décris sa vision professionnelle, sa mission et son approche en te basant sur la section "À propos" de LinkedIn, les descriptions de poste et les analyses de ses interventions (YouTube).

    ## 4. PARCOURS PROFESSIONNEL
    Liste de manière chronologique (du plus récent au plus ancien) les expériences professionnelles passées. Pour chaque poste, indique le titre, l'entreprise et les dates. Si des descriptions sont disponibles, synthétise-les.

    ## 5. FORMATION
    Liste les diplômes et formations, en précisant l'établissement, le diplôme/domaine d'études et les dates (si disponibles).

    ## 6. COMPÉTENCES ET DOMAINES D'EXPERTISE
    * **Compétences techniques** : Liste les compétences techniques spécifiques mentionnées (ex: Blockchain, IA, IA Générative, etc.).
    * **Domaines d'expertise** : Liste les compétences plus générales et stratégiques (ex: Innovation, gestion de projet, stratégie, leadership).

    ## 7. PROJETS ET RÉALISATIONS NOTABLES
    Liste les projets, publications, conférences ou autres réalisations significatives mentionnées dans les données.

    ## 8. PERSONNALITÉ ET VALEURS
    * **Traits de caractère** : Décris la personnalité qui se dégage des informations (ex: passionné, pragmatique, curieux).
    * **Style de communication** : Analyse son style de communication (ex: pédagogique, direct, structuré).
    * **Valeurs exprimées** : Identifie les valeurs qu'il/elle semble défendre (ex: collaboration, partage de connaissances, excellence).
    ## 9. OPINIONS ET PRISES DE POSITION
    Analyse les données fournies pour identifier les opinions, convictions ou prises de position exprimées par la personne sur des sujets variés (technologie, industrie, société, etc.). Pour chaque opinion trouvée, présente-la sous forme de liste en suivant ce format :
* **Sur [le thème abordé]** : [Synthèse de son opinion].
    ## 10. POINTS D'ATTENTION ET DONNÉES CRITIQUES
    Synthétise ici les points qui méritent une attention particulière : défis surmontés (ex: "plafond de verre"), prises de position, anecdotes révélatrices sur sa carrière ou ses motivations.

    ## 9. ACTIVITÉ RÉCENTE
    Résume l'activité récente de la personne, telle que décrite dans les posts LinkedIn ou autres sources. Indique la date ou le mois si disponible (ex: Juillet 2025).
    """
    # --- FIN DE LA MODIFICATION PRINCIPALE ---

    print(f"Génération du rapport final pour {person_name} avec la nouvelle structure...")
    return call_gemini_api(prompt)


def save_final_report(report_content, person_name):
    """Sauvegarde le rapport final dans un fichier Markdown."""
    safe_person_name = person_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"rapport_final_{safe_person_name}_{timestamp}.md"

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"✅ Rapport final sauvegardé avec succès sous : {filename}")
        return filename
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde du rapport final : {e}")
        return None


def main(person_name_arg=None):
    print("🚀 Lancement de l'Agent de Rapport Final 🚀")
    print("============================================")

    if person_name_arg is None:
        if len(sys.argv) > 1:
            person_name = sys.argv[1].strip()
        else:
            print("❌ Erreur: Aucun nom de personne fourni. Veuillez passer le nom de la personne en argument.")
            print("Exemple d'utilisation: python votre_script.py \"Imen Ayari\"")
            sys.exit(1)
    else:
        person_name = person_name_arg.strip()

    if not person_name:
        print("❌ Le nom de la personne est obligatoire. Annulation.")
        sys.exit(1)

    print(f"👤 Cible du rapport : {person_name}")

    # 1. Charger les rapports LinkedIn
    linkedin_data = load_linkedin_reports(person_name)

    # 2. Charger les rapports YouTube
    youtube_data = load_youtube_reports(person_name)

    if not linkedin_data and not youtube_data:
        print(f"⚠️ Aucun rapport LinkedIn ou YouTube trouvé pour '{person_name}'. Impossible de générer un rapport final.")
        sys.exit(1)

    # 3. Préparer les données pour le LLM
    prepared_data_text = prepare_data_for_llm(linkedin_data, youtube_data)
    if not prepared_data_text:
        print("⚠️ Aucune donnée pertinente à consolider. Annulation.")
        sys.exit(1)

    # 4. Générer le rapport final avec Gemini
    final_report_content = generate_final_report(prepared_data_text, person_name)

    # 5. Sauvegarder le rapport final
    if final_report_content and "Erreur API Gemini" not in final_report_content:
        save_final_report(final_report_content, person_name)
        print("\n============================================")
        print(f"🎉 Agent de Rapport Final terminé pour {person_name} ! 🎉")
        sys.exit(0)
    else:
        print(f"❌ Échec de la génération du rapport final par Gemini pour {person_name}.")
        sys.exit(1)


if __name__ == "__main__":
    main()
