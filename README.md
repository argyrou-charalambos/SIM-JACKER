# 🔥 SIMJACKER ULTIMATE – Système de Localisation par SMS Binaire

![Version](https://img.shields.io/badge/version-3.0-blue)
![License](https://img.shields.io/badge/license-Éducatif%20uniquement-red)
![Status](https://img.shields.io/badge/status-Production%20Ready-brightgreen)

## 📋 TABLE DES MATIÈRES
1. [Présentation](#-présentation)
2. [Architecture du système](#-architecture-du-système)
3. [Prérequis matériels](#-prérequis-matériels)
4. [Installation](#-installation)
5. [Configuration](#-configuration)
6. [Utilisation](#-utilisation)
7. [Fonctionnement détaillé](#-fonctionnement-détaillé)
8. [Dépannage](#-dépannage)
9. [Limitations](#-limitations)
10. [Aspects légaux](#-aspects-légaux)

---

## 🎯 PRÉSENTATION

**SimJacker Ultimate** est un système professionnel de test de vulnérabilité des cartes SIM basé sur l'attaque SimJacker (CVE-2020-16139). Ce projet implémente une preuve de concept complète permettant de :

- ✅ Tester la vulnérabilité d'une carte SIM au navigateur S@T
- ✅ Envoyer des commandes SIM Toolkit (GetLocation, etc.)
- ✅ Recevoir et analyser les réponses de la carte SIM
- ✅ Extraire le Cell-ID pour localisation approximative
- ✅ Maximiser les chances de succès par tests exhaustifs

> ⚠️ **AVERTISSEMENT** : Ce projet est STRICTEMENT éducatif. L'utiliser sans autorisation sur des systèmes dont vous n'êtes pas propriétaire est ILLÉGAL.

---

## 🏗️ ARCHITECTURE DU SYSTÈME
[Modem GSM] ←→ [PC Ubuntu] ←→ [Serveur C2]
(Samsung ) ↑ ↑
| |
SMS Attaque Réponse SIM
| |
[Cible] ←→ [Carte SIM]

text

### Composants principaux

| Composant | Rôle |
|:---|:---|
| **Modem GSM** | Samsung configuré en mode modem USB |
| **PC Ubuntu** | Exécute le script principal |
| **Serveur C2** | Reçoit les réponses de la carte SIM |
| **Tunnel** | ngrok/serveo.net pour exposer le serveur |

---

## 📱 PRÉREQUIS MATÉRIELS

### Obligatoire
- **PC Ubuntu** 22.04/24.04
- **Téléphone Android** (Samsung  recommandé)
- **Câble USB** pour connexion

### Optionnel mais recommandé
- **Compte Twilio** (pour envoi SMS alternatif)
- **Token OpenCellID** (pour localisation précise)

---

## 🔧 INSTALLATION

### 1. Préparation du téléphone (Samsung )

```bash
# Activer le mode développeur
# Paramètres → À propos du téléphone → Appuyer 7x sur "Numéro de build"

# Activer le débogage USB
# Paramètres → Options développeur → Débogage USB

# Activer le mode modem
# Composer *#0808# et sélectionner "RNDIS + DM + MODEM"
# Ou dans Paramètres → Connexions → Modem USB
2. Installation sur PC
bash
# Cloner le dépôt
git clone https://github.com/votre-repo/simjacker-ultimate.git
cd simjacker-ultimate

# Installer les dépendances
sudo apt update
sudo apt install python3 python3-pip -y
pip3 install -r requirements.txt

# Donner les permissions au modem
sudo usermod -a -G dialout $USER
# Déconnecter/reconnecter pour appliquer
3. Fichier requirements.txt
txt
pyserial>=3.5
flask>=2.0
requests>=2.26
⚙️ CONFIGURATION
Fichier config.py
python
# =====================================================================
# CONFIGURATION SIMJACKER ULTIMATE
# =====================================================================

CONFIG = {
    # ----- NUMÉROS TÉLÉPHONIQUES -----
    "NUMERO_CIBLE": "+243839898872",      # La cible
    "NUMERO_COMPLICE": "+243XXXXXXXXX",   # Ton numéro pour réception
    
    # ----- MODEM -----
    "MODEM_PORT": "/dev/ttyACM0",          # Port du modem
    "MODEM_BAUD": 115200,                   # Vitesse
    
    # ----- MODE DE TEST -----
    "USE_ALL_TAGS": True,                    # Tester TOUS les tags (0x00-0xFF)
    "TAGS_PERSONNALISES": [0x24, 0x26, 0x2A], # Si USE_ALL_TAGS=False
    
    # ----- SERVEUR C2 -----
    "C2_PORT": 5000,                          # Port local
    "USE_TUNNEL": True,                        # Activer tunnel (ngrok/serveo)
    
    # ----- TIMINGS -----
    "TIMEOUT_ATTENTE": 300,                    # Attente max (secondes)
    "DELAI_ENVOI": 2,                          # Pause entre envois
}
🚀 UTILISATION
1. Lancer le script principal
bash
python3 simjacker_ultimate.py
2. Menu interactif
text
================================================================
🔥 SIMJACKER ULTIMATE - MAXIMUM SUCCESS RATE
================================================================

1) Détection automatique du modem
2) Lancer campagne complète (recommandé)
3) Tester un tag spécifique
4) Surveiller les réponses
5) Analyser une réponse hexadécimale
6) Configurer OpenCellID
7) Quitter

👉 Votre choix: 
3. Campagne complète (option 2)
Le script va automatiquement :

Détecter le modem

Démarrer le serveur C2

Générer et envoyer tous les payloads (256 tags)

Surveiller les réponses

Afficher les résultats

4. Résultat attendu
text
📩 SMS reçu de +243XXXXXXXXX: 9000
   Statut: SUCCESS
   🎯 Cell-ID: 53021
🔬 FONCTIONNEMENT DÉTAILLÉ
1. Format du payload SIM Toolkit
text
[CLA] 0x80  (SIM Application Toolkit)
[INS] 0x10  (ENVELOPE)
[P1]  0x00
[P2]  0x00
[LC]  Longueur des données
[TLV] Tag-Length-Value
  [Tag]  0x24 (GETLOCATION)
  [Len]  Longueur de l'URL
  [Val]  URL du C2
  [0xFF] Tag de fin
2. Tags S@T standards
Tag	Commande	Description
0x24	GETLOCATION	Demande la localisation
0x26	SEND SMS	Envoie un SMS
0x2A	LAUNCH BROWSER	Ouvre un navigateur
0x2C	SETUP CALL	Initie un appel
0xD0	PROVIDE LOCAL INFO	Fournit des infos locales
3. Réponses SIM (Status Words)
SW1	SW2	Signification
0x90	0x00	SUCCÈS
0x91	0x00	PLUS DE DONNÉES
0x6F	0x00	ERREUR TECHNIQUE
0x6D	0x00	INSTRUCTION NON SUPPORTÉE
0x6E	0x00	CLASSE NON SUPPORTÉE
🛠️ DÉPANNAGE
Problème : Modem non détecté
bash
# Vérifier les ports disponibles
ls /dev/tty*

# Vérifier les permissions
ls -la /dev/ttyACM0
sudo chmod 666 /dev/ttyACM0
# Ou ajouter l'utilisateur au groupe dialout
sudo usermod -a -G dialout $USER
# Déconnecter/reconnecter
Problème : "AT" ne répond pas
bash
# Tester manuellement
screen /dev/ttyACM0 115200
# Taper AT puis Ctrl+A, Ctrl+\ pour quitter
Problème : SMS non envoyé
bash
# Vérifier la qualité du signal
AT+CSQ
# Réponse attendue: +CSQ: <rssi>,<ber>
# rssi > 10 est bon
Problème : Tunnel ne démarre pas
bash
# Installer ngrok manuellement
wget https://bin.equinox.io/c/bNyj1mQVYc4/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/
⚠️ LIMITATIONS
1. Vulnérabilité de la carte SIM
Le succès dépend uniquement de la présence du navigateur S@T sur la carte SIM. Les cartes SIM modernes (post-2020) ne sont pas vulnérables.

2. Opérateur
Même si la carte a le navigateur, l'opérateur peut l'avoir désactivé.

3. Tags
Le tag de localisation varie selon les opérateurs. Le script teste tous les tags pour maximiser les chances.

4. Localisation
Le Cell-ID donne une zone approximative (500m-3km). Pour une localisation précise, il faut OpenCellID.


📚 RESSOURCES
Rapport technique original SimJacker

Spécifications 3GPP TS 31.115

Base de données OpenCellID

Documentation SIM Toolkit



Rejoindre le Discord (lien dans le dépôt)

