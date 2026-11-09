/*
 * DECODIFICADOR ROBUSTO DE CUADRATURA COMPLETA (MÁQUINA DE ESTADOS x4)
 * Motor 2: D25 (C1) y D26 (C2)
 * Inmune a rebotes, lee ambos canales en CHANGE con tabla de transiciones Gray
 */

const int PIN_C1 = 25; // D25
const int PIN_C2 = 26; // D26

volatile long ticks = 0;
volatile uint8_t estadoAnterior = 0;

// Tabla de transiciones de cuadratura:
// Índice = (estado_previo << 2) | estado_actual
// Valores: +1 (adelante), -1 (atras), 0 (sin cambio o transicion invalida/ruido)
const int8_t TABLA_CUADRATURA[16] = {
   0, -1,  1,  0,
   1,  0,  0, -1,
  -1,  0,  0,  1,
   0,  1, -1,  0
};

void IRAM_ATTR isrCuadratura() {
  uint8_t c1 = digitalRead(PIN_C1);
  uint8_t c2 = digitalRead(PIN_C2);
  uint8_t estadoActual = (c1 << 1) | c2;
  
  uint8_t indice = (estadoAnterior << 2) | estadoActual;
  ticks += TABLA_CUADRATURA[indice];
  estadoAnterior = estadoActual;
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_C1, INPUT_PULLUP);
  pinMode(PIN_C2, INPUT_PULLUP);

  // Leer estado inicial
  estadoAnterior = (digitalRead(PIN_C1) << 1) | digitalRead(PIN_C2);

  // Interrupciones en ambos pines en CUALQUIER cambio (CHANGE)
  attachInterrupt(digitalPinToInterrupt(PIN_C1), isrCuadratura, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_C2), isrCuadratura, CHANGE);

  Serial.println("CUADRATURA_X4_READY");
}

void loop() {
  uint8_t c1 = digitalRead(PIN_C1);
  uint8_t c2 = digitalRead(PIN_C2);
  Serial.printf("RAW:%d,%d,%ld\n", c1, c2, ticks);
  delay(40); // 25 Hz para lectura fluida en el navegador
}
