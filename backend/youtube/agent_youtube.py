import json
import os
from datetime import datetime
from typing import Dict, List, Optional
import re
import requests
import glob  # Ensure glob is imported for pattern matching


class YouTubeAnalysisAgent:
    GEMINI_API_KEY = "-"

    def __init__(self):
        if not self.GEMINI_API_KEY or self.GEMINI_API_KEY == "VOTRE_CLÉ_API_GEMINI_ICI":
            raise ValueError(
                "Clé API Gemini requise. Veuillez remplacer 'VOTRE_CLÉ_API_GEMINI_ICI' par votre clé réelle.")
        print("Agent d'analyse YouTube initialisé avec la clé API Gemini.")

    def load_latest_json_data(self) -> Optional[Dict]:
        """
        Charge le fichier JSON le plus récent généré par youtube_search.py ou le script précédent.
        Recherche les fichiers dans le répertoire du script agent_youtube.py.

        Returns:
            Dictionnaire contenant les données extraites ou None si erreur
        """
        try:
            print("🔍 Recherche du fichier JSON le plus récent...")

            # Get the directory of the current script (agent_youtube.py)
            script_dir = os.path.dirname(os.path.abspath(__file__))

            # Search for files using glob with the script's directory
            search_pattern_old = os.path.join(script_dir, 'youtube_results_*.json')
            search_pattern_new = os.path.join(script_dir, 'youtube_search_*.json')

            json_files_old_format = glob.glob(search_pattern_old)
            json_files_new_format = glob.glob(search_pattern_new)

            all_json_files = sorted(json_files_old_format + json_files_new_format, key=os.path.getmtime, reverse=True)

            if not all_json_files:
                print("❌ Aucun fichier JSON de résultats YouTube trouvé dans le répertoire du script.")
                print(f"💡 Vérifié dans : {script_dir}")
                print("💡 Assurez-vous d'avoir exécuté le script de recherche et de sauvegarde d'abord.")
                return None

            latest_file = all_json_files[0]
            print(f"📄 Fichier le plus récent trouvé: {latest_file}")

            # Read JSON data
            with open(latest_file, 'r', encoding='utf-8') as f:
                raw_data_from_file = json.load(f)

            processed_data = {}
            # Detect JSON file format
            if isinstance(raw_data_from_file, dict) and 'videos' in raw_data_from_file:
                processed_data['search_query'] = raw_data_from_file.get('search_query', 'Inconnu')
                processed_data['search_date'] = raw_data_from_file.get('search_date', 'Inconnue')
                processed_data['videos'] = raw_data_from_file.get('videos', [])
            elif isinstance(raw_data_from_file, list):
                # This is the old format (direct list of videos)
                processed_data['videos'] = raw_data_from_file
                # Deduce search_query and search_date from filename for old format
                search_query_from_filename = ""
                if latest_file.startswith('youtube_results_'):
                    parts = os.path.basename(latest_file).replace('youtube_results_', '').replace('.json', '').split(
                        '_')
                    if len(parts) > 2 and re.match(r'\d{8}', parts[-2]) and re.match(r'\d{6}', parts[-1]):
                        search_query_from_filename = ' '.join(parts[:-2])
                    else:
                        search_query_from_filename = ' '.join(parts)
                processed_data['search_query'] = search_query_from_filename.replace('_', ' ').strip()
                processed_data['search_date'] = datetime.fromtimestamp(os.path.getctime(latest_file)).strftime(
                    "%Y-%m-%d %H:%M:%S")
            else:
                print(f"❌ Format de fichier JSON inattendu: {latest_file}")
                return None

            print(f"✅ Données chargées: {len(processed_data.get('videos', []))} vidéos")
            print(f"📅 Date de recherche: {processed_data.get('search_date', 'Inconnue')}")
            print(f"🔍 Terme recherché (déduit du fichier): '{processed_data.get('search_query', 'Inconnu')}'")

            return processed_data

        except json.JSONDecodeError as e:
            print(f"❌ Erreur lors du décodage JSON: {e}")
            return None
        except Exception as e:
            print(f"❌ Erreur lors du chargement des données: {e}")
            return None

    def clean_and_prepare_data(self, raw_data: Dict) -> str:
        """
        Nettoie et prépare les données pour l'analyse LLM

        Args:
            raw_data: Données brutes du scraping YouTube

        Returns:
            Texte formaté pour le LLM
        """
        if not raw_data or not raw_data.get('videos'):
            return "Aucune donnée vidéo disponible."

        print("🧹 Nettoyage et préparation des données...")

        formatted_text = f"RECHERCHE YOUTUBE: {raw_data['search_query']}\n"
        formatted_text += f"DATE DE RECHERCHE: {raw_data['search_date']}\n"
        formatted_text += f"NOMBRE DE VIDÉOS ANALYSÉES: {len(raw_data['videos'])}\n\n"

        videos_with_subtitles = sum(1 for video in raw_data['videos'] if
                                    isinstance(video, dict) and video.get('subtitles_available', False) and video.get(
                                        'full_speech'))
        formatted_text += f"VIDÉOS AVEC SOUS-TITRES DISPONIBLES: {videos_with_subtitles}/{len(raw_data['videos'])}\n\n"

        for i, video in enumerate(raw_data['videos'], 1):
            if not isinstance(video, dict):
                print(
                    f"⚠️ Avertissement: L'élément {i} dans la liste des vidéos n'est pas un dictionnaire et sera ignoré: {video}")
                continue

            formatted_text += f"=== VIDÉO {i} ===\n"
            formatted_text += f"Titre: {video.get('title', 'Titre non disponible')}\n"
            formatted_text += f"ID Vidéo: {video.get('video_id', 'ID non disponible')}\n"
            formatted_text += f"URL: {video.get('url', 'URL non disponible')}\n"

            if video.get('subtitles_available', False) and video.get('full_speech'):
                clean_speech = self._clean_subtitle_text(video['full_speech'])
                formatted_text += f"Contenu (sous-titres): {clean_speech}\n"
                formatted_text += f"Longueur du contenu: {len(clean_speech)} caractères\n"
            else:
                error_msg = video.get('error', 'Raison inconnue')
                formatted_text += f"Contenu: Sous-titres non disponibles ({error_msg})\n"

            formatted_text += "\n" + "-" * 80 + "\n\n"

        print(f"✅ Données préparées: {len(formatted_text)} caractères au total")
        return formatted_text

    def _clean_subtitle_text(self, text: str) -> str:
        if not text:
            return ""

        text = re.sub(r'&#\d+;', '', text)
        text = re.sub(r'&[a-zA-Z]+;', '', text)
        text = re.sub(r'&[a-zA-Z0-9#]+;', '', text)

        text = text.replace('&#39;', "'").replace('&quot;', '"').replace('&amp;', '&')

        text = re.sub(r'\b(\w+)(\s+\1\b)+', r'\1', text)

        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\t+', ' ', text)

        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)

        if len(text) > 12000:
            text = text[:12000] + "... [TEXTE TRONQUÉ]"

        return text.strip()

    def analyze_with_llm(self, prepared_data: str, person_focus: str = None) -> str:
        try:
            print("🤖 Analyse en cours avec le LLM (Gemini)...")

            focus_text = person_focus if person_focus else "la personnalité ou le sujet principal"

            system_instruction = f"""Tu es un analyste expert spécialisé dans l'analyse de contenu YouTube et le profiling de personnalités. 
                Ta mission est d'analyser les transcriptions de vidéos pour créer un profil complet, détaillé et professionnel de {focus_text}.

                INSTRUCTIONS DÉTAILLÉES:
                1. Analyse TOUS les contenus disponibles avec attention.
                2. Extrait TOUTES les informations pertinentes sur {focus_text}.
                3. Distingue clairement les FAITS des OPINIONS.
                4. Identifie les patterns de comportement et de communication.
                5. Note les évolutions dans le temps si détectées.
                6. Crée une synthèse cohérente, complète et bien structurée.
                7. Utilise des citations directes quand c'est pertinent.
                8. Indique le niveau de confiance pour chaque information.

                FORMAT DE RÉPONSE OBLIGATOIRE:
                # PROFIL COMPLET DE {focus_text.upper()}

                ## 🎯 RÉSUMÉ EXÉCUTIF
                [Synthèse complète en 3-4 phrases qui capture l'essence de la personne/sujet]

                ## 📋 INFORMATIONS BIOGRAPHIQUES
                - **Nom complet:** [Si mentionné]
                - **Âge/Date de naissance:** [Si mentionné]
                - **Origine géographique:** [Si mentionné]
                - **Formation:** [Si mentionné]
                - **Parcours personnel:** [Éléments de vie personnelle mentionnés]

                ## 💼 ACTIVITÉS PROFESSIONNELLES
                - **Métier principal:** [Profession actuelle]
                - **Projets en cours:** [Projets mentionnés]
                - **Collaborations:** [Partenaires, équipes]
                - **Réalisations:** [Succès, accomplissements]
                - **Objectifs futurs:** [Projets à venir mentionnés]

                ## 🎭 PERSONNALITÉ ET STYLE
                - **Traits de caractère:** [Personnalité observée]
                - **Style de communication:** [Façon de s'exprimer]
                - **Humour et ton:** [Type d'humour, ambiance]
                - **Valeurs exprimées:** [Principes, valeurs mentionnées]
                - **Rapport au public:** [Relation avec l'audience]

                ## 🔥 CENTRES D'INTÉRÊT ET EXPERTISE
                - **Sujets de prédilection:** [Thèmes favoris récurrents]
                - **Domaines d'expertise:** [Compétences démontrées]
                - **Passions personnelles:** [Hobbies, intérêts]
                - **Tendances récurrentes:** [Sujets qui reviennent souvent]

                ## 💭 OPINIONS ET POSITIONS
                - **Prises de position:** [Opinions clairement exprimées]
                - **Controverses:** [Sujets sensibles abordés]
                - **Évolutions d'opinion:** [Changements détectés]
                - **Nuances:** [Subtilités dans les positions]

                ## 🎬 ANALYSE DU CONTENU VIDÉO
                - **Nombre de vidéos analysées:** [Statistique]
                - **Thèmes principaux:** [Sujets les plus abordés]
                - **Évolution du contenu:** [Changements dans le temps]
                - **Qualité des informations:** [Fiabilité des sous-titres]
                - **Citations marquantes:** [Phrases importantes extraites]

                ## ⚠️ NOTES MÉTHODOLOGIQUES
                - **Sources d'information:** [Vidéos analysées]
                - **Limites de l'analyse:** [Ce qui manque]
                - **Niveau de confiance:** [Fiabilité des informations]
                - **Recommandations:** [Pour une analyse plus poussée]
                """

            user_prompt_full = f"""{system_instruction}

Voici les données extraites des vidéos YouTube à analyser en détail:

{prepared_data}

Analyse ces contenus de manière EXHAUSTIVE et fournis une synthèse COMPLÈTE selon les instructions. N'omets aucune information importante et sois aussi détaillé que possible."""

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": user_prompt_full}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.9,
                    "maxOutputTokens": 3000
                }
            }

            gemini_api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.GEMINI_API_KEY}"

            response = requests.post(gemini_api_url, headers={'Content-Type': 'application/json'}, json=payload)
            response.raise_for_status()

            gemini_response = response.json()

            analysis = ""
            if gemini_response and gemini_response.get('candidates'):
                for candidate in gemini_response['candidates']:
                    if candidate.get('content') and candidate['content'].get('parts'):
                        for part in candidate['content']['parts']:
                            if part.get('text'):
                                analysis += part['text']

            if not analysis:
                print(f"⚠️ La réponse de Gemini ne contient pas de texte. Réponse brute: {gemini_response}")
                return "Erreur: Le modèle Gemini n'a pas retourné de texte analysé."

            print("✅ Analyse LLM (Gemini) terminée avec succès")
            return analysis

        except requests.exceptions.HTTPError as errh:
            print(f"❌ Erreur HTTP lors de l'appel à l'API Gemini : {errh}")
            print(f"Détails de la réponse : {response.text}")
            return f"Erreur lors de l'analyse: Erreur HTTP - {errh}"
        except requests.exceptions.RequestException as err:
            print(f"❌ Erreur de Requête lors de l'appel à l'API Gemini : {err}")
            return f"Erreur lors de l'analyse: Erreur de Requête - {err}"
        except json.JSONDecodeError:
            print(f"❌ Erreur : Impossible de décoder la réponse JSON de l'API Gemini. Réponse brute : {response.text}")
            return "Erreur lors de l'analyse: Erreur de décodage JSON de la réponse Gemini."
        except Exception as e:
            print(f"❌ Erreur inattendue lors de l'analyse LLM : {e}")
            return f"Erreur lors de l'analyse: {str(e)}"

    def save_analysis(self, analysis: str, original_search_term: str) -> str:
        """
        Sauvegarde l'analyse dans un fichier Markdown
        Sauvegarde le fichier dans le répertoire du script agent_youtube.py.

        Args:
            analysis: Texte de l'analyse
            original_search_term: Terme de recherche original

        Returns:
            Nom du fichier sauvegardé
        """
        script_dir = os.path.dirname(os.path.abspath(__file__))
        safe_term = "".join(c for c in original_search_term if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_term = safe_term.replace(' ', '_')
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"youtube_analysis_{safe_term}_{timestamp}.md"

        full_file_path = os.path.join(script_dir, filename)

        try:
            with open(full_file_path, 'w', encoding='utf-8') as f:
                f.write(f"# Analyse YouTube Complète - {original_search_term}\n\n")
                f.write(f"**Date de génération:** {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n\n")
                f.write(f"**Terme de recherche original:** {original_search_term}\n\n")
                f.write("---\n\n")
                f.write(analysis)
                f.write("\n\n---\n\n")
                f.write("*Analyse générée automatiquement par YouTubeAnalysisAgent (avec Gemini)*\n")

            print(f"💾 Analyse sauvegardée dans: {full_file_path}")
            return full_file_path

        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde: {e}")
            return ""

    def run_complete_analysis(self, person_focus: str = None) -> Optional[str]:
        """
        Exécute l'analyse complète: chargement -> nettoyage -> analyse LLM -> sauvegarde

        Args:
            person_focus: Nom de la personne à analyser (optionnel)

        Returns:
            Nom du fichier d'analyse généré ou None si erreur
        """
        print("🚀 Démarrage de l'analyse complète des données YouTube")
        print("=" * 70)

        # 1. Chargement des données JSON
        raw_data = self.load_latest_json_data()
        if not raw_data:
            print("❌ Impossible de charger les données YouTube")
            return None

        search_term = raw_data.get('search_query', 'Recherche inconnue')
        print(f"✅ Données chargées pour la recherche: '{search_term}'")

        # 2. Nettoyage et préparation des données
        prepared_data = self.clean_and_prepare_data(raw_data)
        if not prepared_data or "Aucune donnée vidéo disponible." in prepared_data:
            print("❌ Aucune donnée utilisable après nettoyage ou aucun sous-titre disponible pour l'analyse.")
            return None

        print("✅ Données nettoyées et préparées pour l'analyse")

        # 3. Analyse avec LLM
        effective_person_focus = person_focus if person_focus else search_term
        print(f"🎯 Focus de l'analyse: {effective_person_focus}")
        analysis = self.analyze_with_llm(prepared_data, effective_person_focus)

        if "Erreur lors de l'analyse" in analysis:
            print("❌ Erreur lors de l'analyse LLM")
            return None

        # 4. Sauvegarde
        filename = self.save_analysis(analysis, search_term)
        if not filename:
            print("❌ Erreur lors de la sauvegarde")
            return None

        print("=" * 70)
        print("🎉 ANALYSE TERMINÉE AVEC SUCCÈS!")
        print(f"📄 Fichier généré: {filename}")
        print(f"📊 Longueur de l'analyse: {len(analysis)} caractères")

        print("\n" + "=" * 70)
        print("📋 APERÇU DE L'ANALYSE:")
        print("=" * 70)


        return filename


def main():
    """
    Fonction principale pour utiliser l'agent
    """
    print("🎬 AGENT D'ANALYSE YOUTUBE - DONNÉES EXISTANTES")
    print("=" * 60)
    print("Ce programme analyse le fichier JSON le plus récent")
    print("généré par le script de recherche YouTube.")
    print("=" * 60)

    try:
        agent = YouTubeAnalysisAgent()

        raw_data = agent.load_latest_json_data()
        if not raw_data:
            print("❌ Impossible de charger les données YouTube. L'analyse ne peut pas continuer.")
            return

        person_focus = raw_data.get('search_query', 'Analyse générale')
        print(f"\n👤 Focus de l'analyse déduit du fichier: '{person_focus}'")

        print(f"\n🔄 Lancement de l'analyse...")
        print(f"📊 Analyse du contenu avec focus sur: {person_focus}")

        result = agent.run_complete_analysis(person_focus)

        if result:
            print(f"\n✅ Analyse terminée avec succès!")
            print(f"📁 Consultez le fichier: {result}")
            print("\n💡 Le fichier contient une analyse complète et détaillée.")
        else:
            print("\n❌ L'analyse a échoué. Vérifiez les logs ci-dessus.")
            print("💡 Assurez-vous qu'un fichier JSON de résultats existe (exécutez le script de recherche d'abord).")

    except ValueError as e:
        print(f"❌ Erreur de configuration: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")


if __name__ == "__main__":
    main()
