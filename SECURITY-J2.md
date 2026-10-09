# Corrections J2

L'application exige une session Django. Chaque utilisateur ne voit et ne modifie que ses tâches. Les anciennes tâches sans propriétaire restent en base et peuvent être réattribuées par un administrateur Django ; aucune migration ne les supprime.

Les entrées sont échappées dans les templates. La recherche utilise l'ORM ; l'import accepte une liste JSON validée (100 titres maximum), jamais pickle. Les écritures nécessitent CSRF. Le panneau réservé au personnel utilise la session et ne renvoie aucun secret. Les helpers inutilisés de hash MD5, jeton aléatoire, YAML non sûr et commande shell ont été retirés.

Le mot de passe applicatif en dur n'est plus accepté. L'ancienne clé Django de démonstration n'est plus chargée : `DJANGO_SECRET_KEY` est obligatoire. Un déploiement doit injecter son propre secret, jamais réutiliser celui de l'historique. La configuration J1 utilisait déjà une clé distincte par VM.

Les cookies Secure et HttpOnly sont activés par défaut. Le laboratoire app-dev sert encore HTTP : son module de déploiement autorise les cookies HTTP uniquement sur cette cible privée. Une exposition réelle nécessite TLS. La production reste verrouillée et n'est pas modifiée par ce TP.

## Tests

Installer Python 3.11 ou supérieur et les dépendances verrouillées :
`python -m pip install --require-hashes -r requirements.txt`

Installer coverage, injecter une clé de test aléatoire dans `DJANGO_SECRET_KEY`, puis exécuter :

```text
python -m coverage run manage.py test --noinput
python -m coverage report
python -m coverage xml -o reports/coverage.xml
```

La couverture porte sur `tasks` et `todo`, avec branches. Seul le fichier de tests est séparé du code applicatif, comme dans Sonar. Les migrations et les points d'entrée ASGI/WSGI restent inclus.

`requirements.txt` fige toutes les dépendances et leurs empreintes. `requirements.in` et Pipfile décrivent les dépendances directes. Django 5.2 LTS permet d'utiliser les mêmes versions corrigées sur Python 3.11 de Debian et dans la CI.
