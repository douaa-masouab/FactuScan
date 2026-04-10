# FactuScan - Analyse Intelligente & Multi-Utilisateurs

<div align="center">

![FactuScan Logo](https://img.shields.io/badge/FactuScan-OCR%20Intelligent-blue?style=for-the-badge)
![Version](https://img.shields.io/badge/version-1.1.0-green?style=for-the-badge)
![Security](https://img.shields.io/badge/auth-Flask--Login-orange?style=for-the-badge)
![AI](https://img.shields.io/badge/IA-Gemini%201.5-red?style=for-the-badge)

*Extraction automatisée et sécurisée des informations de factures marocaines via OCR et IA Hybride*

[🚀 Déployer](#déploiement) • [📖 Documentation](#documentation) • [💬 Support](#support)

</div>

---

## 📋 Table des Matières

- [À Propos](#à-propos)
- [🌟 Nouvelles Fonctionnalités](#fonctionnalités)
- [🏗️ Architecture Système](#architecture)
- [🚀 Installation & Démarrage](#démarrage-rapide)
- [🎯 Utilisation](#utilisation)
- [📄 Licence](#licence)

---

## 🎯 À Propos

**FactuScan** est désormais une plateforme sécurisée multi-utilisateurs pour l'analyse des factures marocaines. Elle combine la puissance de **Google Gemini 1.5** et de **EasyOCR** pour garantir une extraction de données ultra-précise, même sur des documents complexes, tout en protégeant la confidentialité de chaque utilisateur.

---

## 🌟 Fonctionnalités

### 🔐 Authentification & Sécurité
- **Multi-Utilisateurs** : Système complet d'inscription et de connexion.
- **Isolation des Données** : Chaque compte possède ses propres archives (vos factures ne sont visibles que par vous).
- **Sessions Sécurisées** : Gestion des sessions via Flask-Login.

### 📊 Extraction IA Hybride (Morocco Optimized)
- **IA Gemini 1.5 Flash** : Analyse contextuelle pour une précision de 99% sur les montants, ICE et dates.
- **OCR Local (Fallback)** : Utilisation de EasyOCR pour les environnements hors-ligne ou documents manuscrits.
- **Validation Mathématique** : Vérification automatique de la cohérence HT + TVA = TTC.

### 🎙️ Assistant Vocal Bilingue
- **Auto-Détection de Langue** : L'assistant détecte et parle désormais en **Français** ou en **Arabe** selon le contenu de la facture.
- **Commandes Intuitives** : "Total", "Résumé", "Aide", "Lire".

### 🚀 Performance
- **Lazy Loading** : Démarrage du serveur quasi-instantané grâce au chargement différé des modèles lourds d'IA.

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌────────────────────┐
│   Frontend      │    │    Backend      │    │     Database       │
│   (HTML/JS)     │◄──►│    (Flask)      │◄──►│   (SQLite/MySQL)   │
│ Login/Dashboard │    │  Auth & Logic   │    │  Invoices x Users  │
└─────────────────┘    └─────────────────┘    └────────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   AI Services    │
                        │ ┌──────────────┐ │
                        │ │  Gemini 1.5  │ │
                        │ └──────────────┘ │
                        │ ┌──────────────┐ │
                        │ │ EasyOCR (AR) │ │
                        │ └──────────────┘ │
                        └──────────────────┘
```

---

## 🚀 Démarrage Rapide

### Installation

```bash
# 1. Cloner le projet
git clone https://github.com/douaa-masouab/FactuScan.git
cd FactuScan

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Lancer l'application
python backend/app.py
```

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