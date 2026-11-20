/*
 * ======================================================================================
 * Firmware de Lectura y Filtrado Digital para Sensor de Corriente ACS758LCB-050B
 * Plataforma: Arduino Nano (ATmega328P) @ 16 MHz
 * Proyecto: Tesis de Ingenieria Mecatronica - UTEC 2026
 * Robot: Hexapodo Primario (Chipo) - Monitoreo de Consumo Total de Bateria (3S LiPo)
 * Entrada Analogica: Pin A1 (conectado a OU1 del sensor)
 * ======================================================================================
 */

const int PIN_SENSOR = A1;             // Pin analogico A1 conectado a OU1 (Señal directa)
const float SENSIBILIDAD = 0.040;      // 40 mV/A (0.040 V/A) para ACS758LCB-050B
const float VCC_REF = 5.000;           // Tension nominal de referencia de alimentacion (5.00 V)
const float V_BAT_NOMINAL = 11.1;      // LiPo 3S nominal (11.1 V)

float v_offset_cero = 2.500;           // Offset de reposo (0 A)
unsigned long ultimo_envio = 0;
const unsigned long INTERVALO_ENVIO_MS = 50; // 20 Hz de transmision hacia Python

void calibrarCero() {
  long suma_adc = 0;
  const int N = 300;
  for (int i = 0; i < N; i++) {
    suma_adc += analogRead(PIN_SENSOR);
    delayMicroseconds(500);
  }
  float adc_prom = suma_adc / (float)N;
  v_offset_cero = (adc_prom * VCC_REF) / 1023.0;

  Serial.print(F("{\"status\":\"calibrated\",\"pin\":\"A1\",\"v_offset\":"));
  Serial.print(v_offset_cero, 4);
  Serial.println(F("}"));
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_SENSOR, INPUT);
  
  // Breve retardo para estabilizacion de la fuente
  delay(300);
  
  // Calibracion inicial de cero
  calibrarCero();
}

void loop() {
  // Comandos por puerto serie ('c' o 'C' para recalibrar cero en caliente)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'c' || cmd == 'C') {
      calibrarCero();
    }
  }

  unsigned long ahora = millis();
  if (ahora - ultimo_envio >= INTERVALO_ENVIO_MS) {
    ultimo_envio = ahora;

    // Sobremuestreo (Oversampling de 50 lecturas) para anular ruido de servos y PWM
    long suma_adc = 0;
    for (int i = 0; i < 50; i++) {
      suma_adc += analogRead(PIN_SENSOR);
      delayMicroseconds(100);
    }
    float adc_prom = suma_adc / 50.0;
    float voltaje = (adc_prom * VCC_REF) / 1023.0;

    // Corriente (A) = (Vout - Voffset) / Sensibilidad
    float corriente = (voltaje - v_offset_cero) / SENSIBILIDAD;

    // Zona muerta para ruido residual minimo (< 30 mA)
    if (abs(corriente) < 0.030) {
      corriente = 0.0;
    }

    // Potencia instantanea (W)
    float potencia = corriente * V_BAT_NOMINAL;

    // Envio en formato JSON estandar
    Serial.print(F("{\"t\":"));
    Serial.print(ahora);
    Serial.print(F(",\"v\":"));
    Serial.print(voltaje, 3);
    Serial.print(F(",\"i\":"));
    Serial.print(corriente, 2);
    Serial.print(F(",\"p\":"));
    Serial.print(potencia, 2);
    Serial.print(F(",\"v0\":"));
    Serial.print(v_offset_cero, 3);
    Serial.print(F(",\"pin\":\"A1\"}"));
    Serial.println();
  }
}
