# Explorateur musical underground

Outil de découverte musicale développé pour Le Larsen.

Triangule trois sources publiques :
- **MusicBrainz** — relations entre artistes (membres de groupes, side-projects, collaborations), labels, tags
- **ListenBrainz** — filtrage collaboratif open-source basé sur les scrobbles
- **Last.fm** — cooccurrence d'écoute massive

## Usage en local

```
python3 app.py
```

Puis ouvrir `http://localhost:8765` dans le navigateur.

## Déploiement

Compatible Render.com (lecture de la variable d'environnement `PORT`, écoute sur `0.0.0.0`).
