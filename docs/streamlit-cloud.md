# Préparation Streamlit Community Cloud

Branche de travail : `feat/streamlit-cloud`. Cette préparation ne fusionne rien et ne
publie ni le code ni les données. L’entrée cloud est `cloud/streamlit_app.py` ;
`streamlit_app.py` reste l’entrée locale avec ses chemins et sa sauvegarde atomique.
Le schéma des annotations reste inchangé. Aucune migration n’est nécessaire.

## Configuration du déploiement

Dans Community Cloud, choisir le dépôt, cette branche (après revue et publication
autorisée) et `cloud/streamlit_app.py`. Choisir explicitement **Python 3.14** dans
Advanced settings. Ne pas déployer l’entrée locale sur une instance partagée.

`requirements.txt` installe le paquet local avec son extra UI. Les cinq dépendances
directes sont figées dans `constraints-cloud.txt`. Leurs métadonnées sont compatibles
avec Python 3.14 ; les tests ont été exécutés avec CPython 3.14.0 sous Windows. La CI
ajoutée exécute la suite sur Ubuntu/Python 3.14. La résolution Linux de roues binaires
est vérifiée séparément ; elle ne remplace pas une exécution Linux ni un essai sur
Community Cloud. Les dépendances transitives ne constituent pas un lock complet.
Le support annoncé du noyau local reste Python >=3.10 ; les versions figées du cloud
exigent au minimum 3.12 (NumPy/SciPy). Aucun test runtime de cette préparation n’a été
exécuté sur Python 3.10–3.13.

La configuration au voisinage de l’entrée cloud surcharge celle de la racine :
`0.0.0.0` pour recevoir le trafic du proxy, uploads à 50 Mio, XSRF/CORS actifs et pas de
service statique de fichiers. L’entrée locale garde `127.0.0.1`. Ne pas fixer un port
ou désactiver XSRF pour contourner un problème de proxy. Les réglages de la plateforme
peuvent primer sur le dépôt, dont sa collecte de statistiques : `gatherUsageStats=false`
dans le dépôt n’est pas une garantie de désactivation sur Community Cloud.

Essai du mode cloud depuis la racine, en conservant un accès loopback local :

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run cloud/streamlit_app.py --server.address 127.0.0.1 --server.port 8502
```

Le mode local continue à se lancer avec `streamlit run streamlit_app.py`.
Le module Windows `winsound` n’est importé que par la CLI `annotate --play` ; cette
option reste spécifique à Windows et n’est jamais utilisée par l’entrée cloud.
Les roues Linux SoundFile embarquent libsndfile ; pas de `packages.txt` nécessaire
pour cette sélection de versions/plateforme. Revalider si les versions changent.

## Ce qui dépendait d’un disque durable

| Fonction locale | Hypothèse locale | Mode cloud préparé |
|---|---|---|
| Découverte `audio/prototypes/*.wav` | WAV disponibles sur disque | Uploads explicites, aucun parcours du dépôt |
| `annotations/the_signal.json` | JSON partagé conservé entre lancements | Objet JSON propre à la session, import/export explicites |
| Sauvegarde et verrou atomiques | Un dossier et des versions durables | Appliquer en mémoire ; télécharger pour conserver |
| `reports/interface/` | Rapports accessibles après redémarrage | Répertoire temporaire de calcul ; ZIP en mémoire de session |
| Cache de forme d’onde locale | Cache global acceptable pour une seule personne | Aucun `st.cache_data`/`st.cache_resource` pour les données cloud |
| `SUNO_LAB_ROOT` | Chemin d’un projet local connu | Non utilisé par l’entrée cloud |

La CLI et le mode local gardent leur comportement. La suppression de fichiers locaux
n’est pas utilisée comme moyen de migration. Les WAV originaux restent intacts.

## Architecture d’uploads mise en œuvre

```text
Navigateur → uploader Streamlit → validation format/tailles
            → octets WAV + JSON dans st.session_state
            → écoute / forme d’onde / validation humaine
            → export JSON vers l’utilisateur
            → calcul du rapport : TemporaryDirectory unique
              → fonctions DSP/rapport existantes → ZIP en mémoire → téléchargement
              → suppression du répertoire à la sortie du calcul (succès ou exception)
```

Limites applicatives par session : deux WAV ; 50 Mio par fichier, 100 Mio au total ;
mono ou stéréo ; 8–48 kHz ; 5 minutes ; 24 millions d’échantillons de canaux maximum
par fichier (~96 Mo de tableau float32, avant copies et FFT). Le JSON importé est
limité à 1 Mio. Les noms de WAV sont contrôlés et distincts, sans chemin fourni par
l’utilisateur. Le conteneur réel est contrôlé avec SoundFile, pas seulement l’extension.
Les JSON sont validés avec `phases_for` et les durées des uploads, sans changer le schéma.
L’import exige que les pistes du JSON correspondent aux WAV déjà chargés.

Aucun repère n’est inventé. Les modifications sont appliquées ensemble à la session ;
les champs de formulaire non appliqués peuvent être perdus au changement de piste.
Le bouton rapport utilise seulement le JSON appliqué : au moins une phase validée
par piste et tous les repères présents validés, phases manquantes autorisées.
Le ZIP contient Markdown, JSON et PNG, jamais les WAV.

Le seul état global ajouté est un verrou de calcul sans données utilisateur : un seul
rapport à la fois par processus, avec refus immédiat si un calcul est en cours. Il réduit
les pics mémoire, sans constituer une limite globale de sessions ou un ordonnanceur fiable.

Les WAV sont écrits uniquement comme copies éphémères dans le répertoire temporaire
pour appeler le pipeline existant. Chaque calcul a un nom aléatoire distinct. Aucun
chemin temporaire ne sert de lien de téléchargement ; les résultats sont envoyés en
mémoire. Effacer la session retire ses références applicatives. Ce n’est pas un effacement
sécurisé : uploader, serveur et navigateur peuvent garder leurs propres références.
Un arrêt brutal peut empêcher le nettoyage. Le disque temporaire n’est ni un stockage
persistant ni une frontière de confidentialité. Il ne doit contenir aucun jeu de données
préchargé, annotation privée ou secret provenant du développeur.

## Risques avant fusion et utilisation publique

- **Confidentialité** : Session State sépare les sessions au niveau applicatif, pas les
  processus ou l’administrateur. Le disque, la mémoire du processus et les caches internes
  du serveur ne sont pas des coffres privés entre utilisateurs. Ne pas utiliser Community
  Cloud pour des enregistrements sensibles avec cette architecture.
- **Durabilité** : fermeture/reconnexion, veille ou redéploiement peuvent perdre la session.
  Télécharger le JSON et le ZIP. Aucun enregistrement durable automatique n’est promis.
- **Ressources** : l’uploader reçoit les octets avant le contrôle du total et du nombre.
  Plusieurs sessions/uploads peuvent saturer la RAM ou le CPU malgré les limites et le
  verrou de rapports. Pas de protection complète contre les abus, pas d’authentification
  ou de quota par identité dans ce prototype. L’enveloppe audio reste recalculée sans cache.
- **Fichiers non fiables** : un en-tête WAV valide ne garantit pas un décodage complet.
  Le parseur natif et le DSP demandent des mises à jour et des budgets CPU/mémoire.
- **Dépendances/runtime** : Linux est couvert par une CI ajoutée mais non encore exécutée
  sur GitHub ; l’hébergement Community Cloud n’a pas été testé. Les pins nécessitent un
  suivi de sécurité. Une résolution à blanc ne valide pas les bibliothèques natives à runtime.
- **Publication** : `.gitignore`, `MANIFEST.in` et `tools/check_public_files.py` couvrent
  les chemins de données, pas tous les secrets potentiellement incorporés dans du code
  ou l’historique. Examiner le diff et l’historique avant tout push. Ne pas forcer l’ajout
  des répertoires privés.

Pour des uploads privés et durables : authentification obligatoire → stockage objet
chiffré avec préfixes par propriétaire et autorisation vérifiée côté serveur → liens
signés courts → job identifié par UUID dans un worker isolé (conteneur/processus avec
limites RAM/CPU/temps) → résultats sous ACL du propriétaire. Ajouter quotas par identité,
expiration et nettoyage côté stockage, suppression explicite, journalisation sans contenu,
consentement/rétention et tests d’accès entre comptes. Les annotations gardent le même
JSON, stocké comme objet versionné avec contrôle de concurrence. La clé objet n’est pas
une autorisation. Cette architecture renforcée est proposée, pas implémentée ici.

## Revue et validation

Les 55 tests existants ne sont pas modifiés. Les tests ajoutés couvrent les uploads,
limites, chemins, conservation du schéma, nettoyage des temporaires même en erreur,
absence de WAV dans les ZIP, sessions Streamlit distinctes et réseau local/cloud.

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe tools/check_public_files.py
git diff --cached --stat
git diff --cached
```

Aucune fusion, aucun push ni déploiement n’est effectué par cette préparation.

Sources officielles consultées :
[dépendances](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies),
[choix de Python](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy),
[configuration par entrée](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization),
[restrictions de la plateforme](https://docs.streamlit.io/deploy/streamlit-community-cloud/status),
[uploads en mémoire](https://docs.streamlit.io/knowledge-base/using-streamlit/where-file-uploader-store-when-deleted),
[Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state),
[portée du cache](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data).
