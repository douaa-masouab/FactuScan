# FactuScan - Analyse Intelligente des Factures Marocaines

<div align="center">

![FactuScan Logo](https://img.shields.io/badge/FactuScan-OCR%20Intelligent-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.0.0-green?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-purple?style=for-the-badge)
![Docker](https://img.shields.io/badge/docker-ready-blue?style=for-the-badge)

*Automatisation de l'extraction des informations des factures marocaines via l'OCR et l'IA*

[🚀 Déployer](#déploiement) • [📖 Documentation](#documentation) • [💬 Support](#support)

</div>

## 📋 Table des Matières

- [À Propos](#à-propos)
- [🌟 Fonctionnalités](#fonctionnalités)
- [🏗️ Architecture](#architecture)
- [🚀 Démarrage Rapide](#démarrage-rapide)
- [📦 Installation](#installation)
- [🎯 Utilisation](#utilisation)
- [🚀 Documentation](#documentation)
- [🤝 Contribuer](#contribuer)
- [📄 Licence](#licence)
- [📞 Support](#support)

---

## 🎯 À Propos

**FactuScan** est une application web d'analyse intelligente des factures marocaines qui automatise l'extraction des informations via l'OCR et l'intelligence artificielle. Conçue pour le contexte marocain, elle reconnaît les formats de factures locaux et fournit une interface moderne et épurée.

### 🎯 Objectif Principal

Simplifier et automatiser le traitement des factures pour les entreprises marocaines, réduisant le temps de saisie manuelle et minimisant les erreurs.

---

## 🌟 Fonctionnalités

### 📊 Extraction Intelligente
- **OCR Optimisé** : Reconnaissance de texte précise en Français (modèle EasyOCR)
- **Extraction Automatique** :
  - Numéro de facture (avec gestion du fallback `_`)
  - Date d'émission
  - Montant TVA
  - Montant total TTC
  - Nom du fournisseur
  - ICE (Identifiant Commun de l'Entreprise)

### 🎙️ Assistant Vocal
- **Reconnaissance Vocale** : Commandes vocales en Français
- **Synthèse Vocale** : Réponses vocales claires pour la lecture des résultats
- **Commandes Intuitives** : Résumé, totaux, aide, lire.

### 📱 Interface Utilisateur
- **Design Moderne** : Interface épurée, sombre et responsive
- **Glisser-Déposer** : Importation facile des factures (Images ou PDF)
- **Visualisation en Temps Réel** : Résultats instantanés avec badge de statut
- **Mode Sombre** : Design premium style "Glassmorphism"

### 💾 Gestion des Données
- **Historique Complet** : Toutes les factures archivées localement
- **Exportation** : Export CSV structuré (Compatible Excel/UTF-8)
- **Tableau de Bord** : Statistiques, totaux et gestion de l'historique

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │    Database     │
│   (HTML/JS)     │◄──►│   (Flask)       │◄──►│   (Local/DB)    │
│   Simple UI     │    │   Python 3.10   │    │   SQLite/MySQL  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   AI Services   │
                       │  ┌───────────┐  │
                       │  │   OCR     │  │
                       │  │ (EasyOCR) │  │
                       │  └───────────┘  │
                       │  ┌───────────┐  │
                       │  │   Voice   │  │
                       │  │ (gTTS)    │  │
                       │  └───────────┘  │
                       └─────────────────┘
```

---

## 🚀 Démarrage Rapide

### Prérequis

- [Python 3.10+](https://www.python.org/)
- [Git](https://git-scm.com/)

### Installation Locale

```bash
# 1. Cloner le projet
git clone https://github.com/douaa-masouab/FactuScan.git
cd FactuScan

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python backend/app.py
```

### Accès à l'Application

Ouvrez votre navigateur et accédez à :
- **Application** : http://localhost:5000
- **Tableau de Bord** : http://localhost:5000/dashboard.html

---

## 🎯 Utilisation

### Importation de Factures

1. **Glisser-Déposer** : Déposez vos fichiers PDF/JPG/PNG/JFIF
2. **Parcourir** : Cliquez sur la zone de dépôt pour sélectionner
3. **Analyse** : Cliquez sur "Analyser la facture" pour lancer le traitement OCR

### Assistant Vocal

```bash
# Commandes disponibles (Français)
- "Donne-moi un résumé" → Affiche le résumé des dernières factures
- "Quel est le total ?" → Affiche le montant cumulé de toutes les factures
- "Lire" → Lit vocalement les résultats de la dernière facture extraite
- "Aide-moi" → Liste les commandes supportées
```

---

## 🤝 Contribuer

Nous apprécions vos contributions ! Voici comment vous pouvez aider :

1. **Fork** le projet
2. **Créez** une branche (`git checkout -b feature/amazing-feature`)
3. **Commitez** vos changements (`git commit -m 'Add amazing feature'`)
4. **Pushez** (`git push origin feature/amazing-feature`)
5. **Ouvrez** une Pull Request

---

## 📄 Licence

Ce projet est sous licence **MIT**. 

---

## 📞 Support

| Canal | Description |
|-------|-------------|
| **GitHub Issues** | [Créer une issue](https://github.com/douaa-masouab/FactuScan/issues) |
| **Email** | support@factuscan.ma |

<div align="center">

**⭐ Si ce projet vous a aidé, n'oubliez pas de laisser une étoile !**

Made with ❤️ for Morocco

[🔝 Retour en haut](#factuscan---analyse-intelligente-des-factures-marocaines)

</div>