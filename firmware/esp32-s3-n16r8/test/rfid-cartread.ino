#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN      10
#define RST_PIN     14

#define SPI_SCK     12
#define SPI_MISO    13
#define SPI_MOSI    11

MFRC522 mfrc522(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(115200);

  SPI.begin(SPI_SCK, SPI_MISO, SPI_MOSI, SS_PIN);
  mfrc522.PCD_Init();

  Serial.println("RFID Ready. Silakan tempelkan kartu...");
}

void loop() {
  // 1. Cek apakah ada kartu baru yang ditempelkan
  if (!mfrc522.PICC_IsNewCardPresent()) {
    return;
  }

  // 2. Coba baca UID kartu
  if (!mfrc522.PICC_ReadCardSerial()) {
    return;
  }

  // 3. Tampilkan UID ke Serial Monitor
  Serial.print("UID Kartu: ");
  for (byte i = 0; i < mfrc522.uid.size; i++) {
    Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " ");
    Serial.print(mfrc522.uid.uidByte[i], HEX);
  }
  Serial.println();

  // 4. Berhenti membaca kartu agar tidak terbaca berulang-ulang
  mfrc522.PICC_HaltA();
  mfrc522.PCD_StopCrypto1();
}
