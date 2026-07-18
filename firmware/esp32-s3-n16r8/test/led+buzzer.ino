#define LED_MERAH 16
#define LED_HIJAU 17
#define BUZZER    18

void setup() {
  pinMode(LED_MERAH, OUTPUT);
  pinMode(LED_HIJAU, OUTPUT);
  pinMode(BUZZER, OUTPUT);
}

void loop() {

  // Merah ON
  digitalWrite(LED_MERAH, HIGH);
  digitalWrite(LED_HIJAU, LOW);
  digitalWrite(BUZZER, HIGH);
  delay(500);

  digitalWrite(BUZZER, LOW);
  delay(500);

  // Hijau ON
  digitalWrite(LED_MERAH, LOW);
  digitalWrite(LED_HIJAU, HIGH);
  digitalWrite(BUZZER, HIGH);
  delay(500);

  digitalWrite(BUZZER, LOW);
  delay(500);
}
