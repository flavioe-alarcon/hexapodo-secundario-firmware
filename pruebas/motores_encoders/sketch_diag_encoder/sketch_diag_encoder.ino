/*
 * DIAGNÓSTICO EN TIEMPO REAL - CANALES ENCODER (D25 y D26)
 * Muestra el estado digital crudo (0 o 1) y los ticks para giro manual
 */

const int PIN_C1 = 25; // D25
const int PIN_C2 = 26; // D26

volatile long ticks = 0;
volatile int lastC1 = 0;
volatile int lastC2 = 0;

void IRAM_ATTR isrC1() {
  int c2Val = digitalRead(PIN_C2);
  if (c2Val == HIGH) ticks++; else ticks--;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_C1, INPUT_PULLUP);
  pinMode(PIN_C2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_C1), isrC1, RISING);
  Serial.println("DIAGNOSTICO_ENCODER_READY");
}

void loop() {
  int val1 = digitalRead(PIN_C1);
  int val2 = digitalRead(PIN_C2);
  
  // Enviamos: ESTADO:valC1,valC2,ticks
  Serial.printf("RAW:%d,%d,%ld\n", val1, val2, ticks);
  delay(50); // 20 Hz para refresco suave
}
