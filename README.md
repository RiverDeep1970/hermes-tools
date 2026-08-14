# Hermes Tools

Ensemble d'outils web pour le suivi personnel — mood, médicaments, rappels, rapports et dashboard Hermes.

## 🧰 Outils

### 😊 Mood Tracker (`mood-server.py`)
Formulaire web pour suivre l'humeur, les lectures et les séries.
- 🔗 **https://mood.riverdeep1970.xyz**

### 💊 Médicaments Tracker (`med-server.py`)
Gestion des médicaments avec prises, rappels, historique, streak et alertes d'oubli.
- 🔗 **https://medocs.riverdeep1970.xyz**
- 🔐 Auth: alexis / medoc2026

### ⚡ Dashboard Hermes (`dashboard-server.py`)
Tableau de bord en temps réel : stats serveur, état Hermes, jobs cron, tokens/coûts LLM.
- 🔗 **https://dashboard.riverdeep1970.xyz**
- 🔐 Auth: alexis / medoc2026

### 📬 AgentMail Auto (`agentmail-auto.py`)
Répondeur automatique : détecte les newsletters BDM, TAO Daily, Reporterre, Journal du Coin, les résume et les envoie par email.

### 💾 Medoc Backup (`medoc-backup.py`)
Backup journalier des bases de données (médicaments + mood), rétention 14 jours, exécution à 4h.

### 📊 Med Report (`med-report.py`)
Rapports hebdomadaires et mensuels d'observance médicamenteuse par email.

### 🔔 Rappels (`med-reminder.py`)
Rappels Telegram aux heures de repas (8h, 12h, 19h) avec lien vers le site.

## 🔧 Services systemd

| Service | Port | Description |
|---------|------|-------------|
| `mood-tracker` | 8080 | Mood Tracker |
| `med-tracker` | 8081 | Médicaments Tracker |
| `dashboard-tracker` | 8082 | Dashboard Hermes |
| `mood-tracker-tunnel` | — | Tunnel Cloudflare permanent |

## 🔗 URLs

| Site | URL |
|------|-----|
| 😊 Mood | https://mood.riverdeep1970.xyz |
| 💊 Médicaments | https://medocs.riverdeep1970.xyz |
| ⚡ Dashboard | https://dashboard.riverdeep1970.xyz |

## 📁 Structure des données

```
~/.hermes/
├── med-tracker.db          # Base médicaments (SQLite)
├── state.db                # Base Hermes (sessions, jobs)
├── life-tracker/entries/   # Entrées mood (JSON)
├── newsletters/            # Newsletters sauvegardées
├── backups/medoc/          # Backups (14 jours)
├── scripts/                # Scripts (ce dépôt)
└── .cloudflared/           # Configuration tunnel
```

## 🚀 Installation

```bash
git clone https://github.com/RiverDeep1970/hermes-tools.git
cd hermes-tools
```

Chaque serveur s'installe via systemd :
```bash
sudo cp *.service /etc/systemd/system/
sudo systemctl enable --now med-tracker
```