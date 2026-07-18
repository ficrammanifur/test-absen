#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#define SDA_PIN 1
#define SCL_PIN 2

LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  Wire.begin(SDA_PIN, SCL_PIN);

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("ESP32-S3 CAM");

  lcd.setCursor(0, 1);
  lcd.print("LCD OK");
}

void loop() {
}
