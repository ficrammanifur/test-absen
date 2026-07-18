#include <Wire.h>

#define SDA_PIN 1
#define SCL_PIN 2

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);

  Serial.println("Scanning...");

  for (byte address = 1; address < 127; address++) {
    Wire.beginTransmission(address);

    if (Wire.endTransmission() == 0) {
      Serial.print("Device ditemukan di 0x");
      Serial.println(address, HEX);
    }
  }

  Serial.println("Selesai Scan");
}

void loop() {
}
