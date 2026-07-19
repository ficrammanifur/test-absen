/*
 * ESP32-S3-N16R8 RFID + LCD + LED + Buzzer + MQTT
 * Board: ESP32-S3-N16R8 (ESP32-S3 with 16MB Flash, 8MB PSRAM)
 * 
 * Koneksi:
 * - RFID RC522: SS=10, MOSI=11, SCK=12, MISO=13, RST=14
 * - LCD I2C: SDA=8, SCL=9 (0x27)
 * - LED Merah: 16
 * - LED Hijau: 17
 * - Buzzer: 18
 */

#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include <PubSubClient.h>

// ================================================================
// 1. KONFIGURASI
// ================================================================

// --- WiFi ---
const char* WIFI_SSID = "FRISS";
const char* WIFI_PASSWORD = "mamahfris";

// --- MQTT ---
const char* MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char* MQTT_CLIENT_ID = "ESP32_S3_RFID_001";

// MQTT Topics
const char* MQTT_TOPIC_RFID = "esp32/rfid/uid";        // Kirim UID ke Python
const char* MQTT_TOPIC_RESULT = "esp32/rfid/result";   // Terima hasil dari Python
const char* MQTT_TOPIC_STATUS = "esp32/rfid/status";   // Status perangkat

// --- Debug ---
#define DEBUG_MODE true

// ================================================================
// 2. PIN DEFINITIONS
// ================================================================

// I2C untuk LCD
#define SDA_PIN 8
#define SCL_PIN 9

// RFID RC522
#define SS_PIN 10
#define MOSI_PIN 11
#define SCK_PIN 12
#define MISO_PIN 13
#define RST_PIN 14

// LED & Buzzer
#define LED_RED 16
#define LED_GREEN 17
#define BUZZER_PIN 18

// ================================================================
// 3. OBJECT INITIALIZATION
// ================================================================

MFRC522 mfrc522(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);  // Coba 0x3F jika 0x27 tidak bekerja
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// ================================================================
// 4. VARIABLES
// ================================================================

bool waitingForResult = false;
unsigned long waitStartTime = 0;
String currentUID = "";
String lastUID = "";
unsigned long lastRFIDRead = 0;
const unsigned long RFID_READ_INTERVAL = 2000;
unsigned long lastMQTTReconnect = 0;
const unsigned long MQTT_RECONNECT_INTERVAL = 5000;

// ================================================================
// 5. WIFI FUNCTIONS
// ================================================================

void connectWiFi() {
  Serial.println();
  Serial.print("📶 Menghubungkan ke WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.println("✅ WiFi Terhubung!");
    Serial.print("📡 IP Address: ");
    Serial.println(WiFi.localIP());
    Serial.print("📶 RSSI: ");
    Serial.println(WiFi.RSSI());
  } else {
    Serial.println();
    Serial.println("❌ Gagal konek WiFi! Restart...");
    delay(3000);
    ESP.restart();
  }
}

// ================================================================
// 6. MQTT FUNCTIONS
// ================================================================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  
  Serial.println("\n📨 Pesan MQTT Diterima:");
  Serial.print("   Topic: ");
  Serial.println(topic);
  Serial.print("   Payload: ");
  Serial.println(message);

  if (String(topic) == MQTT_TOPIC_RESULT) {
    // Parse hasil dari backend
    if (message.indexOf("SUCCESS") > 0) {
      // Extract nama
      int nameStart = message.indexOf("name") + 7;
      int nameEnd = message.indexOf("\"", nameStart);
      String name = message.substring(nameStart, nameEnd);
      
      aksesDiterima(name);
    } else if (message.indexOf("FAILED") > 0) {
      aksesDitolak();
    }
    waitingForResult = false;
  }
}

void connectMQTT() {
  if (mqttClient.connected()) {
    return;
  }
  
  Serial.print("🔄 Menghubungkan ke MQTT Broker: ");
  Serial.print(MQTT_BROKER);
  Serial.print("...");
  
  if (mqttClient.connect(MQTT_CLIENT_ID)) {
    Serial.println(" ✅ Terhubung!");
    
    // Subscribe ke topic result
    mqttClient.subscribe(MQTT_TOPIC_RESULT);
    Serial.print("📡 Subscribe ke: ");
    Serial.println(MQTT_TOPIC_RESULT);
    
    // Kirim status online
    String statusMsg = "{\"status\":\"ONLINE\",\"device\":\"ESP32-S3\",\"ip\":\"" + WiFi.localIP().toString() + "\"}";
    mqttClient.publish(MQTT_TOPIC_STATUS, statusMsg.c_str());
    
  } else {
    Serial.print(" ❌ Gagal, rc=");
    Serial.print(mqttClient.state());
    Serial.println(" coba lagi nanti");
  }
}

void publishRFID(String uid) {
  String payload = "{\"uid\":\"" + uid + "\",\"timestamp\":" + String(millis()) + "}";
  
  if (mqttClient.publish(MQTT_TOPIC_RFID, payload.c_str())) {
    Serial.println("📤 UID terkirim ke MQTT");
    if (DEBUG_MODE) {
      Serial.println("   Payload: " + payload);
    }
  } else {
    Serial.println("❌ Gagal kirim ke MQTT!");
  }
}

// ================================================================
// 7. RFID FUNCTIONS
// ================================================================

String getUID() {
  String uid = "";
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    if (mfrc522.uid.uidByte[i] < 0x10) {
      uid += "0";
    }
    uid += String(mfrc522.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  return uid;
}

bool readRFID() {
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return false;
  }
  if (!mfrc522.PICC_ReadCardSerial()) {
    return false;
  }
  return true;
}

// ================================================================
// 8. SYSTEM FUNCTIONS
// ================================================================

void aksesDiterima(String name) {
  Serial.println("✅ AKSES DITERIMA!");
  Serial.println("   Selamat datang: " + name);
  
  // LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Akses Diterima");
  lcd.setCursor(0, 1);
  lcd.print("Halo, " + name);
  
  // LED Hijau ON
  digitalWrite(LED_GREEN, HIGH);
  digitalWrite(LED_RED, LOW);
  
  // Buzzer 2 beep pendek
  for (int i = 0; i < 2; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(150);
    digitalWrite(BUZZER_PIN, LOW);
    delay(150);
  }
  
  delay(3000);
  resetToIdle();
}

void aksesDitolak() {
  Serial.println("❌ AKSES DITOLAK!");
  
  // LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Akses Ditolak!");
  lcd.setCursor(0, 1);
  lcd.print("Wajah Tidak Cocok");
  
  // LED Merah ON
  digitalWrite(LED_RED, HIGH);
  digitalWrite(LED_GREEN, LOW);
  
  // Buzzer 1 beep panjang
  digitalWrite(BUZZER_PIN, HIGH);
  delay(1000);
  digitalWrite(BUZZER_PIN, LOW);
  
  delay(2000);
  resetToIdle();
}

void resetToIdle() {
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Silakan Tempel");
  lcd.setCursor(0, 1);
  lcd.print("Kartu RFID Anda");
  
  waitingForResult = false;
  currentUID = "";
}

void beepOnce() {
  digitalWrite(BUZZER_PIN, HIGH);
  delay(100);
  digitalWrite(BUZZER_PIN, LOW);
}

// ================================================================
// 9. SETUP
// ================================================================

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n========================================");
  Serial.println("🏢 ESP32-S3 RFID Access Control");
  Serial.println("   Board: ESP32-S3-N16R8");
  Serial.println("========================================\n");
  
  // --- I2C & LCD ---
  Serial.println("📟 Inisialisasi LCD...");
  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Booting...");
  lcd.setCursor(0, 1);
  lcd.print("Mohon Tunggu");
  
  // --- SPI & RFID ---
  Serial.println("📡 Inisialisasi RFID...");
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
  mfrc522.PCD_Init();
  
  // Tampilkan versi RFID
  if (DEBUG_MODE) {
    mfrc522.PCD_DumpVersionToSerial();
  }
  
  // --- GPIO ---
  Serial.println("💡 Inisialisasi GPIO...");
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  
  // --- WiFi ---
  connectWiFi();
  
  // --- MQTT ---
  Serial.println("📡 Inisialisasi MQTT...");
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  connectMQTT();
  
  // --- Selesai ---
  Serial.println("\n========================================");
  Serial.println("✅ SYSTEM READY!");
  Serial.print("📡 MQTT Broker: ");
  Serial.println(MQTT_BROKER);
  Serial.print("📤 Publish ke: ");
  Serial.println(MQTT_TOPIC_RFID);
  Serial.print("📥 Subscribe ke: ");
  Serial.println(MQTT_TOPIC_RESULT);
  Serial.println("💡 Tempelkan kartu RFID untuk memulai\n");
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Sistem Siap");
  lcd.setCursor(0, 1);
  lcd.print("Silakan Tempel");
  
  // Beep indikasi siap
  beepOnce();
  delay(200);
  beepOnce();
}

// ================================================================
// 10. LOOP
// ================================================================

void loop() {
  // Reconnect MQTT jika putus (dengan interval)
  if (!mqttClient.connected()) {
    if (millis() - lastMQTTReconnect > MQTT_RECONNECT_INTERVAL) {
      connectMQTT();
      lastMQTTReconnect = millis();
    }
  } else {
    mqttClient.loop();
  }
  
  // Jika menunggu hasil, cek timeout
  if (waitingForResult) {
    if (millis() - waitStartTime > 30000) {  // 30 detik timeout
      Serial.println("⏰ Timeout menunggu hasil!");
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Timeout!");
      lcd.setCursor(0, 1);
      lcd.print("Coba Lagi");
      delay(2000);
      resetToIdle();
    }
    delay(50);
    return;
  }
  
  // Baca RFID (dengan interval)
  if (millis() - lastRFIDRead < RFID_READ_INTERVAL) {
    delay(50);
    return;
  }
  lastRFIDRead = millis();
  
  // Cek kartu RFID
  if (readRFID()) {
    String uid = getUID();
    
    // Cegah pembacaan berulang UID yang sama
    if (uid != lastUID) {
      lastUID = uid;
      currentUID = uid;
      
      Serial.println("\n🔑 Kartu RFID Terdeteksi!");
      Serial.print("   UID: ");
      Serial.println(uid);
      
      // Kirim ke MQTT
      publishRFID(uid);
      
      // Update LCD
      lcd.clear();
      lcd.setCursor(0, 0);
      lcd.print("Cek Wajah...");
      lcd.setCursor(0, 1);
      lcd.print("Mohon Tunggu");
      
      // LED kedip (indikasi proses)
      digitalWrite(LED_GREEN, HIGH);
      delay(100);
      digitalWrite(LED_GREEN, LOW);
      
      // Beep 1x
      beepOnce();
      
      waitingForResult = true;
      waitStartTime = millis();
      
    } else {
      // UID sama, abaikan
      if (DEBUG_MODE) {
        Serial.println("⏳ UID sama, abaikan...");
      }
    }
    
    // Hentikan komunikasi RFID
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
  }
  
  delay(50);
}
