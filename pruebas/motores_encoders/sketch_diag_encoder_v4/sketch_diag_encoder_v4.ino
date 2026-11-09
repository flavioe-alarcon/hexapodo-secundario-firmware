/*
 * DECODIFICADOR BIDIRECCIONAL - ENCODER MOTOR 2
 * Canal C1 = D25 (GPIO 25)
 * Canal C2 = D13 (GPIO 13) <-- NUEVO PIN AISLADO CON PULL-UP
 */

const int PIN_C1 = 25; // D25
const int PIN_C2 = 13; // D13

volatile long ticks = 0;

void IRAM_ATTR isrEncoderC1() {
  int c1 = digitalRead(PIN_C1);
  int c2 = digitalRead(PIN_C2);
  
  if (c1 != c2) {
    ticks++;
  } else {
    ticks--;
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_C1, INPUT_PULLUP);
  pinMode(PIN_C2, INPUT_PULLUP);

  attachInterrupt(digitalPinToInterrupt(PIN_C1), isrEncoderC1, CHANGE);

  Serial.println("ENCODER_D25_D13_READY");
}

void loop() {
  int c1 = digitalRead(PIN_C1);
  int c2 = digitalRead(PIN_C2);
  Serial.printf("RAW:%d,%d,%ld\n", c1, c2, ticks);
  delay(30);
}
