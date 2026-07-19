# ==========================================
# FILE KONFIGURASI TERPUSAT
# Edit semua setting di sini!
# ==========================================

import os
import json

# ==========================================
# 1. KONFIGURASI NETWORK
# ==========================================

# --- WiFi untuk ESP32-S3 ---
WIFI_SSID = "FRISS"
WIFI_PASSWORD = "mamahfris"

# --- IP Address Perangkat ---
# IP LAPTOP/PC (tempat backend Python berjalan)
LAPTOP_IP = "192.168.1.50"

# IP ESP32-S3 (RFID & indikator)
ESP32_S3_IP = "192.168.1.10"

# ==========================================
# 2. KONFIGURASI MQTT
# ==========================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883

# Topik MQTT
MQTT_TOPIC_RFID = "esp32/rfid/uid"
MQTT_TOPIC_RESULT = "esp32/rfid/result"
MQTT_TOPIC_STATUS = "esp32/rfid/status"

# Client ID
MQTT_CLIENT_ID = f"Python_Backend_{os.getpid()}"

# ==========================================
# 3. KONFIGURASI KAMERA (WEBCAM EKSTERNAL SAJA)
# ==========================================

# HANYA webcam eksternal Logitech C270
# Index yang biasanya digunakan Logitech C270: 1 atau 2
WEBCAM_INDEX = 1  # Logitech C270

# ==========================================
# 4. KONFIGURASI FACE RECOGNITION
# ==========================================

FACE_RECOGNITION_TIMEOUT = 10
FACE_RECOGNITION_INTERVAL = 0.3
FACE_MATCH_TOLERANCE = 0.6

# ==========================================
# 5. DATABASE USER
# ==========================================

USER_DATABASE = {
    "4BAA2206": "Rudi",
}

# ==========================================
# 6. KONFIGURASI FACE DATABASE
# ==========================================

KNOWN_FACES_DIR = "known_faces"
ENCODINGS_FILE = "face_encodings.pkl"

# ==========================================
# 7. KONFIGURASI LOGGING & DEBUG
# ==========================================

DEBUG_MODE = True
LOG_FILE = "system.log"

# ==========================================
# 8. FUNGSI UTILITY
# ==========================================

def get_config_summary():
    summary = {
        "MQTT Broker": f"{MQTT_BROKER}:{MQTT_PORT}",
        "Laptop IP": LAPTOP_IP,
        "ESP32-S3 IP": ESP32_S3_IP,
        "Webcam Index": WEBCAM_INDEX,
        "Known Users": list(USER_DATABASE.values()),
        "Face Timeout": f"{FACE_RECOGNITION_TIMEOUT}s",
    }
    return summary

def save_config_to_file(filename="config_backup.json"):
    config_data = {
        "LAPTOP_IP": LAPTOP_IP,
        "ESP32_S3_IP": ESP32_S3_IP,
        "MQTT_BROKER": MQTT_BROKER,
        "MQTT_TOPIC_RFID": MQTT_TOPIC_RFID,
        "MQTT_TOPIC_RESULT": MQTT_TOPIC_RESULT,
        "WEBCAM_INDEX": WEBCAM_INDEX,
        "USER_DATABASE": USER_DATABASE,
        "FACE_RECOGNITION_TIMEOUT": FACE_RECOGNITION_TIMEOUT,
    }
    with open(filename, 'w') as f:
        json.dump(config_data, f, indent=2)
    print(f"✅ Konfigurasi disimpan ke {filename}")

if __name__ == "__main__":
    print("=" * 60)
    print("📋 RINGKASAN KONFIGURASI")
    print("=" * 60)
    for key, value in get_config_summary().items():
        print(f"  {key}: {value}")
    print("=" * 60)
    save_config_to_file()
