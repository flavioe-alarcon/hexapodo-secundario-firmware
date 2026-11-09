/*
 * DECODIFICADOR BIDIRECCIONAL LIMPIO PARA ENCODER N20
 * Motor 2: D25 (C1) y D26 (C2)
 * Disparo en CHANGE de C1 y comparacion directa con C2
 */

const int PIN_C1 = 25; // D25
const int PIN_C2 = 26; // D26

volatile long ticks = 0;

void IRAM_ATTR isrEncoderC1() {
  int c1 = digitalRead(PIN_C1);
  int c2 = digitalRead(PIN_C2);
  
  // Si C1 y C2 son diferentes: Sentido A (++), si son iguales: Sentido B (--)
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

  Serial.println("ENCODER_BIDIRECTIONAL_READY");
}

void loop() {
  int c1 = digitalRead(PIN_C1);
  int c2 = digitalRead(PIN_C2);
  Serial.printf("RAW:%d,%d,%ld\n", c1, c2, ticks);
  delay(30); // ~33 Hz para máxima fluidez en la interfaz web
}
