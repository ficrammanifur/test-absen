#include <SPI.h>
#include <MFRC522.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// --- Pin Definitions ---
#define SDA_PIN 8
#define SCL_PIN 9

// RFID RC522
#define SS_PIN 10
#define MOSI_PIN 11
#define SCK_PIN 12
#define MISO_PIN 13
#define RST_PIN 14

// Indicators - HANYA LED dan Buzzer
#define LED_RED 16
#define LED_GREEN 17
#define BUZZER_PIN 18

// Object Initialization
MFRC522 mfrc522(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);

// Authorized Card UID
byte kartuDiizinkan[] = {0x4B, 0xAA, 0x22, 0x06};

// State variables
enum SystemState {
  IDLE,
  ACCESS_GRANTED,
  ACCESS_DENIED
};

SystemState currentState = IDLE;
unsigned long stateStartTime = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n========================================");
  Serial.println("Memulai Sistem RFID Access Control");
  Serial.println("========================================");
  
  // --- SETUP I2C & LCD ---
  Serial.println("1. Menginisialisasi I2C...");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setTimeOut(1000);
  
  Serial.println("2. Scan I2C...");
  scanI2C();
  
  Serial.println("3. Menginisialisasi LCD...");
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Sistem Siap");
  Serial.println("   LCD OK");
  
  // --- SETUP SPI & RFID ---
  Serial.println("4. Menginisialisasi SPI & RFID...");
  SPI.begin(SCK_PIN, MISO_PIN, MOSI_PIN, SS_PIN);
  mfrc522.PCD_Init();
  Serial.println("   RFID OK");
  
  // --- SETUP PINS (HANYA LED dan Buzzer) ---
  Serial.println("5. Menginisialisasi Pin I/O...");
  
  Serial.println("   - Setting LED_RED (GPIO16)...");
  pinMode(LED_RED, OUTPUT);
  digitalWrite(LED_RED, LOW);
  Serial.println("     LED_RED OK");
  
  Serial.println("   - Setting LED_GREEN (GPIO17)...");
  pinMode(LED_GREEN, OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  Serial.println("     LED_GREEN OK");
  
  Serial.println("   - Setting BUZZER_PIN (GPIO18)...");
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("     BUZZER OK");
  
  Serial.println("========================================");
  Serial.println("Sistem Inisialisasi Selesai!");
  Serial.println("Silakan tempelkan kartu RFID");
  Serial.println("========================================");
  
  lcd.setCursor(0, 1);
  lcd.print("Silakan Tempel");
  
  currentState = IDLE;
}

void loop() {
  // Handle state machine
  handleStateMachine();
  
  // Only check for new cards if in IDLE state
  if (currentState == IDLE) {
    if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {
      processCard();
    }
  }
  
  delay(50);
}

void handleStateMachine() {
  unsigned long currentMillis = millis();
  
  switch(currentState) {
    case ACCESS_GRANTED:
      if (currentMillis - stateStartTime < 2000) {
        digitalWrite(LED_GREEN, HIGH);
        
        // Buzzer beep pattern (sederhana)
        if ((currentMillis / 200) % 2 == 0) {
          digitalWrite(BUZZER_PIN, HIGH);
        } else {
          digitalWrite(BUZZER_PIN, LOW);
        }
      } else {
        resetToIdle();
      }
      break;
      
    case ACCESS_DENIED:
      if (currentMillis - stateStartTime < 1500) {
        digitalWrite(LED_RED, HIGH);
        
        // Buzzer beep pattern (lebih lambat)
        if ((currentMillis / 300) % 2 == 0) {
          digitalWrite(BUZZER_PIN, HIGH);
        } else {
          digitalWrite(BUZZER_PIN, LOW);
        }
      } else {
        resetToIdle();
      }
      break;
      
    case IDLE:
    default:
      digitalWrite(LED_RED, LOW);
      digitalWrite(LED_GREEN, LOW);
      digitalWrite(BUZZER_PIN, LOW);
      break;
  }
}

void processCard() {
  // Display UID
  Serial.print("UID Terbaca: ");
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
  }
  Serial.println();
  
  // Check authorization
  bool cocok = true;
  for (byte i = 0; i < 4; i++) {
    if (mfrc522.uid.uidByte[i] != kartuDiizinkan[i]) {
      cocok = false;
      break;
    }
  }
  
  if (cocok) {
    aksesDiterima();
  } else {
    aksesDitolak();
  }
  
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}

void aksesDiterima() {
  Serial.println(">>> AKSES DITERIMA! <<<");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Akses Diterima");
  lcd.setCursor(0, 1);
  lcd.print("Selamat Datang!");
  
  currentState = ACCESS_GRANTED;
  stateStartTime = millis();
}

void aksesDitolak() {
  Serial.println(">>> AKSES DITOLAK! <<<");
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Akses Ditolak!");
  lcd.setCursor(0, 1);
  lcd.print("Kartu Tidak Sah");
  
  currentState = ACCESS_DENIED;
  stateStartTime = millis();
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
  
  currentState = IDLE;
}

void scanI2C() {
  byte error, address;
  int nDevices = 0;
  Serial.println("Scanning I2C bus...");
  for(address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    error = Wire.endTransmission();
    if(error == 0) {
      Serial.print("I2C device found at 0x");
      if(address < 16) Serial.print("0");
      Serial.println(address, HEX);
      nDevices++;
    }
  }
  if(nDevices == 0) {
    Serial.println("No I2C devices found - check wiring!");
  } else {
    Serial.print("Total devices: ");
    Serial.println(nDevices);
  }
}
