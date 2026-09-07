import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from urllib.parse import urlparse
import time
from datetime import datetime
import re
import os
import sys # Ajouté pour sys.exit() et sys.argv


class ProfileOrchestratorAgent:
    def __init__(self, gemini_api_key, google_api_key, google_cse_id):
        """
        Initialise l'orchestrateur avec toutes les clés API nécessaires
        """
        # Configuration Gemini
        genai.configure(api_key=gemini_api_key)
        try:
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        except Exception as e:
            print(f"Avertissement: Impossible d'initialiser gemini-1.5-flash: {e}. Essai avec gemini-1.5-pro.")
            try:
                self.model = genai.GenerativeModel('gemini-1.5-pro')
            except Exception as e_pro:
                print(f"Avertissement: Impossible d'initialiser gemini-1.5-pro: {e_pro}. Essai avec models/gemini-1.5-flash-latest.")
                try:
                    self.model = genai.GenerativeModel('models/gemini-1.5-flash-latest')
                except Exception as e_latest:
                    print(f"Erreur critique: Impossible d'initialiser aucun modèle Gemini: {e_latest}")
                    raise

        # Configuration Google Custom Search
        self.google_api_key = google_api_key
        self.google_cse_id = google_cse_id

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        print("🚀 Orchestrateur initialisé avec succès!")

    def search_google(self, query, num_results=10):
        """
        Recherche Google personnalisée
        """
        print(f"🔍 Recherche Google pour: {query}")

        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={self.google_api_key}&cx={self.google_cse_id}&num={num_results}"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("items", []):
                results.append({
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                })

            print(f"✅ {len(results)} résultats trouvés")
            return results

        except Exception as e:
            print(f"❌ Erreur lors de la recherche Google: {e}")
            return []

    def enrich_snippet(self, url, snippet_google):
        """
        Enrichit le snippet avec du contenu scrapé si possible
        """
        # Domaines protégés à ne pas scraper
        protected_domains = ["linkedin.com", "facebook.com", "pinterest.com"]
        domain = urlparse(url).netloc.lower()

        if any(prot in domain for prot in protected_domains):
            return f"[🔒 Contenu protégé] {snippet_google}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            resp.raise_for_status() # Lève une exception pour les codes d'état HTTP d'erreur
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = soup.find_all("p")
            for p in paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 80:
                    return text
            return f"[🟡 Aucun paragraphe significatif trouvé] {snippet_google}"
        except Exception as e:
            return f"[❌ Erreur lors de l'extraction] {snippet_google} (Détails: {e})"

    def extract_and_save_search_results(self, nom, contexte, num_results=10):
        """
        Effectue la recherche et sauvegarde les résultats enrichis
        """
        print(f"📊 Phase 1: Extraction des données pour {nom}")

        # Construction de la requête
        query = f'"{nom}" "{contexte}"' if contexte else f'"{nom}"'

        # Recherche Google
        results = self.search_google(query, num_results)

        if not results:
            print("❌ Aucun résultat trouvé")
            return None

        # Enrichissement des snippets
        print("📝 Enrichissement des snippets...")
        enriched_results = []

        for i, r in enumerate(results, 1):
            print(f"   Traitement {i}/{len(results)}: {r['title'][:50]}...")
            enriched_text = self.enrich_snippet(r["link"], r["snippet"])
            enriched_results.append({
                "title": r["title"],
                "link": r["link"],
                "original_snippet": r["snippet"],
                "enriched_snippet": enriched_text
            })
            # Petite pause pour éviter le rate limiting
            time.sleep(0.5)

        # Sauvegarde
        # Assurez-vous que le fichier est sauvegardé dans le même répertoire que cet agent
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(script_dir, f"{nom.replace(' ', '_')}_google_results.json")
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(enriched_results, f, ensure_ascii=False, indent=4)
            print(f"✅ Résultats sauvegardés dans {filename}")
            return filename
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde: {e}")
            return None

    def extract_content_from_url(self, url):
        """
        Extrait le contenu textuel d'une URL
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Supprime les scripts et styles
            for script in soup(["script", "style"]):
                script.decompose()

            # Extrait le texte principal
            text = soup.get_text()

            # Nettoie le texte
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text[:5000]  # Limite à 5000 caractères

        except Exception as e:
            print(f"⚠️  Erreur lors de l'extraction de {url}: {e}")
            return None

    def categorize_url(self, url):
        """
        Catégorise l'URL selon sa source
        """
        domain = urlparse(url).netloc.lower()

        if 'linkedin.com' in domain:
            return 'LinkedIn'
        elif 'twitter.com' in domain or 'x.com' in domain:
            return 'Twitter/X'
        elif 'facebook.com' in domain:
            return 'Facebook'
        elif 'github.com' in domain:
            return 'GitHub'
        elif 'medium.com' in domain:
            return 'Medium'
        elif 'instagram.com' in domain:
            return 'Instagram'
        elif 'youtube.com' in domain: # Ajout de YouTube
            return 'YouTube'
        else:
            return 'Autre'

    def analyze_search_results(self, json_file_path, person_name):
        """
        Analyse les résultats de recherche et génère un rapport
        """
        print(f"🤖 Phase 2: Analyse des données pour {person_name}")

        # Charge le fichier JSON
        try:
            with open(json_file_path, 'r', encoding='utf-8') as file:
                search_results = json.load(file)
        except Exception as e:
            print(f"❌ Erreur lors du chargement du fichier: {e}")
            return None

        # Prépare les données pour l'analyse
        extracted_data = {
            'person_info': {'name': person_name},
            'sources': []
        }

        print("📄 Extraction du contenu des liens...")
        for i, result in enumerate(search_results, 1):
            url = result.get('link', '')
            if not url or not url.startswith('http'):
                continue

            print(f"   Analyse {i}/{len(search_results)}: {url}")

            content = result.get('enriched_snippet', '')

            if len(content) < 200 and not any(marker in content for marker in ['🔒', '🟡', '❌']):
                extracted_content = self.extract_content_from_url(url)
                if extracted_content and len(extracted_content) > len(content):
                    content = extracted_content

            if content:
                source_info = {
                    'url': url,
                    'title': result.get('title', ''),
                    'category': self.categorize_url(url),
                    'description': result.get('original_snippet', ''),
                    'content': content,
                    'extracted_at': datetime.now().isoformat()
                }
                extracted_data['sources'].append(source_info)

            time.sleep(1)

        # Génère le rapport avec Gemini
        print("🧠 Génération du rapport avec Gemini...")
        report = self.generate_profile_report(extracted_data, person_name)

        return report

    def extract_social_media_links(self, extracted_data):
        """
        Extrait les liens vers les réseaux sociaux
        """
        social_links = {
            'LinkedIn': [],
            'Twitter/X': [],
            'Facebook': [],
            'Instagram': [],
            'GitHub': [],
            'Medium': [],
            'YouTube': [], # Ajout de YouTube
            'Autres': []
        }

        for source in extracted_data.get('sources', []):
            url = source.get('url', '')
            category = source.get('category', 'Autre')

            if category in social_links:
                social_links[category].append({
                    'url': url,
                    'title': source.get('title', '')
                })
            elif category == 'Autre':
                domain = urlparse(url).netloc.lower()
                if any(social in domain for social in ['youtube.com', 'tiktok.com', 'snapchat.com', 'discord.com']):
                    social_links['Autres'].append({
                        'url': url,
                        'title': source.get('title', '')
                    })

        return {k: v for k, v in social_links.items() if v}

    def generate_profile_report(self, extracted_data, person_name):
        """
        Génère un rapport détaillé avec Gemini
        """
        social_links = self.extract_social_media_links(extracted_data)

        prompt = f"""
        Analysez les informations suivantes sur {person_name} et générez un rapport complet et professionnel.

        Informations extraites des sources en ligne:
        """

        for i, source in enumerate(extracted_data.get('sources', []), 1):
            prompt += f"""

        Source {i} - {source['category']} ({source['url']}):
        Titre: {source.get('title', 'N/A')}
        Description: {source.get('description', 'N/A')}
        Contenu: {source['content'][:2000]}...
        """

        if social_links:
            prompt += f"""

        LIENS RÉSEAUX SOCIAUX IDENTIFIÉS:
        """
            for platform, links in social_links.items():
                prompt += f"\n{platform}:"
                for link in links:
                    prompt += f"\n- {link['url']} ({link['title']})"

        prompt += """

        Veuillez générer un rapport structuré qui inclut:

        1. **RÉSUMÉ EXÉCUTIF**
           - Vue d'overview de la personne
           - Points clés à retenir

        2. **LIENS RÉSEAUX SOCIAUX**
           - Liste tous les profils sociaux trouvés avec leurs URLs
           - Organisés par plateforme (LinkedIn, Twitter/X, Facebook, Instagram, GitHub, YouTube, etc.)

        3. **PROFIL PROFESSIONNEL**
           - Expérience et compétences
           - Domaines d'expertise
           - Réalisations notables

        4. **PRÉSENCE NUMÉRIQUE**
           - Analyse de la présence en ligne
           - Cohérence du message professionnel
           - Niveau d'activité sur les réseaux

        5. **COMPÉTENCES ET EXPERTISE**
           - Compétences techniques identifiées
           - Domaines de spécialisation
           - Projets ou réalisations mentionnés

        6. **RÉSEAU ET INFLUENCE**
           - Connections professionnelles
           - Influence dans le secteur
           - Participation à des communautés

        7. **RECOMMANDATIONS**
           - Points forts identifiés
           - Opportunités d'amélioration
           - Suggestions pour l'engagement

        Le rapport doit être factuel, objectif et basé uniquement sur les informations publiques disponibles.
        Utilisez un format markdown pour une meilleure lisibilité.
        IMPORTANT: Incluez systématiquement la section "LIENS RÉSEAUX SOCIAUX" avec tous les profils trouvés.
        """

        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"❌ Erreur lors de la génération du rapport: {e}")
            return None

    def save_report(self, report, person_name):
        """
        Sauvegarde le rapport dans un fichier
        """
        # Assurez-vous que le fichier est sauvegardé dans le même répertoire que cet agent
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filename = os.path.join(script_dir, f"rapport_{person_name.replace(' ', '_')}_google_search.md")
        try:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(report)
            print(f"✅ Rapport sauvegardé dans: {filename}")
            return filename
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde: {e}")
            return None

    def analyze_complete_profile(self, nom, contexte="", num_results=10, verbose=True):
        """
        Méthode principale orchestrant le processus complet

        Args:
            nom (str): Nom de la personne à analyser
            contexte (str): Contexte professionnel ou autre
            num_results (int): Nombre de résultats à analyser
            verbose (bool): Afficher les logs détaillés ou non

        Returns:
            dict: Résultats de l'analyse avec fichiers générés
        """
        if verbose:
            print("=" * 60)
            print(f"🎯 ANALYSE COMPLÈTE DU PROFIL DE: {nom.upper()}")
            print("=" * 60)

        start_time = time.time()

        # Phase 1: Recherche et extraction
        json_file = self.extract_and_save_search_results(nom, contexte, num_results)

        if not json_file:
            if verbose:
                print("❌ Échec de la phase de recherche")
            return {
                'success': False,
                'error': 'Échec de la phase de recherche',
                'json_file': None,
                'report_file': None,
                'report_content': None,
                'duration': time.time() - start_time
            }

        # Phase 2: Analyse et génération du rapport
        report = self.analyze_search_results(json_file, nom)

        if not report:
            if verbose:
                print("❌ Échec de la phase d'analyse")
            return {
                'success': False,
                'error': 'Échec de la phase d\'analyse',
                'json_file': json_file,
                'report_file': None,
                'report_content': None,
                'duration': time.time() - start_time
            }

        # Phase 3: Sauvegarde du rapport
        report_file = self.save_report(report, nom)

        end_time = time.time()
        duration = end_time - start_time

        if verbose:
            print("\n" + "=" * 60)
            print("✅ ANALYSE TERMINÉE AVEC SUCCÈS!")
            print(f"⏱️  Durée totale: {duration:.2f} secondes")
            print(f"📁 Fichiers générés:")
            print(f"   - Données brutes Google Search: {json_file}")
            print(f"   - Rapport de profil Google Search: {report_file}")
            print("=" * 60)

        return {
            'success': True,
            'json_file': json_file,
            'report_file': report_file,
            'report_content': report,
            'duration': duration,
            'person_name': nom,
            'context': contexte
        }


def main(nom_arg=None, contexte_arg=None): # Accepte les arguments
    """
    Fonction principale avec interface utilisateur
    """
    print("🔍 ANALYSEUR DE PROFIL AUTOMATISÉ")
    print("=" * 40)

    # Configuration des APIs (remplacez par vos vraies clés)
    # Il est préférable de les lire depuis des variables d'environnement
    # ou de les passer en arguments si elles ne sont pas hardcodées ici.
    # Pour cet exemple, je les garde ici, mais vous devriez les gérer de manière sécurisée.
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY_GOOGLE_AGENT", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID", "")


    # Récupération du nom et du contexte depuis les arguments de la fonction ou sys.argv
    if nom_arg is None:
        if len(sys.argv) > 1:
            nom = sys.argv[1].strip()
        else:
            print("❌ Le nom est obligatoire. Veuillez le passer en argument.")
            sys.exit(1)
    else:
        nom = nom_arg.strip()

    if contexte_arg is None:
        if len(sys.argv) > 2: # Check for the third argument (index 2)
            contexte = sys.argv[2].strip()
        else:
            contexte = "" # Default empty context if not provided
    else:
        contexte = contexte_arg.strip()


    num_results = 10  # Valeur par défaut fixe

    print(f"\n🚀 Démarrage de l'analyse pour: {nom}")
    if contexte:
        print(f"📋 Contexte: {contexte}")

    try:
        orchestrator = ProfileOrchestratorAgent(
            gemini_api_key=GEMINI_API_KEY,
            google_api_key=GOOGLE_API_KEY,
            google_cse_id=GOOGLE_CSE_ID
        )
    except Exception as e:
        print(f"❌ Erreur d'initialisation: {e}")
        sys.exit(1)

    try:
        results = orchestrator.analyze_complete_profile(nom, contexte, num_results)

        if results and results['success']:
            print(f"\n📖 Aperçu du rapport:")
            print("-" * 40)
            print(results['report_content'][:500] + "..." if len(results['report_content']) > 500 else results['report_content'])
            sys.exit(0)
        else:
            print(f"\n❌ L'analyse complète du profil a échoué: {results.get('error', 'Erreur inconnue')}")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⏹️  Analyse interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Quand appelé par subprocess.run, sys.argv contiendra les arguments
    # sys.argv[0] est le nom du script
    # sys.argv[1] est le nom de la personne
    # sys.argv[2] est le contexte (optionnel)
    main(sys.argv[1] if len(sys.argv) > 1 else None, sys.argv[2] if len(sys.argv) > 2 else None)

