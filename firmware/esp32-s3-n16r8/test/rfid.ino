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

  Serial.println("RFID Ready");
}

void loop() {

}
