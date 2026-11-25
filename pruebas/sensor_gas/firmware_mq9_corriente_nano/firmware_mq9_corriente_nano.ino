/*
 * ======================================================================================
 * Firmware Integrado: Sensor de Gas MQ-9 (Etanol/CO/Gases) + Sensor de Corriente ACS758
 * Plataforma: Arduino Nano (ATmega328P @ 16 MHz) en puerto COM15 / 115200 baud
 * Proyecto: Tesis de Ingenieria Mecatronica - UTEC 2026
 *
 * Mapeo de Pines en Arduino Nano:
 *   [MQ-9 Gas]:
 *     - VCC  -> 5V (Alimentacion del calefactor, ~150-180 mA)
 *     - GND  -> GND
 *     - A0   -> Pin A0 (Voltaje analogico proporcional a gas / etanol)
 *     - D0   -> Pin D2 (Umbral digital LM393 ajustado por potenciometro)
 *
 *   [ACS758 Corriente]:
 *     - VCC  -> 5V
 *     - GND  -> GND
 *     - OU1  -> Pin A1 (Voltaje analogico de corriente, 40 mV/A)
 * ======================================================================================
 */

const int PIN_GAS_A0 = A0;
const int PIN_GAS_D0 = 2;
const int PIN_CORRIENTE_A1 = A1;

// Parametros electricos y de calibracion
const float VCC_REF = 5.000;              // Tension de alimentacion nominal (5.00 V)
const float SENSIBILIDAD_ACS = 0.040;     // 40 mV/A para ACS758LCB-050B
const float V_BAT_NOMINAL = 11.1;         // LiPo 3S nominal (11.1 V)
const float RL_GAS = 10.0;                // Resistencia de carga en modulo (10 kOhms)
const float RATIO_AIRE_LIMPIO = 9.80;     // Rs/R0 en aire limpio segun datasheet MQ-9

// Constantes de regresion potencial ppm = a * (Rs/R0)^b (Datasheet MQ-9 Hanwei/Winsen)
const float A_ALCOHOL = 7630.0;
const float B_ALCOHOL = -2.322;
const float A_CO = 599.65;
const float B_CO = -2.244;

// Limite de Deteccion (LOD) y piso matematico en aire limpio (Rs/R0 >= 9.20 -> 0.0 ppm)
const float RATIO_LOD_LIMPIO = 9.20;
const float PPM_BASE_ALCOHOL = 38.28;     // 7630.0 * (9.80)^(-2.322)
const float PPM_BASE_CO = 3.58;           // 599.65 * (9.80)^(-2.244)

float v_offset_corriente = 2.500;         // Offset de reposo del sensor de corriente (0 A)
float r0_gas = 1.02;                      // Resistencia base R0 calibrada en aire limpio (kOhms)
float v0_gas = 0.800;                     // Voltaje base en aire limpio

unsigned long ultimo_envio = 0;
const unsigned long INTERVALO_MS = 50;    // 20 Hz de transmision hacia Python

// Rutina de calibracion conjunta en aire limpio y sin carga
void calibrarSensores() {
  // Descartar lectura inicial para estabilizar multiplexor ADC
  analogRead(PIN_CORRIENTE_A1);
  delay(10);

  // 1. Calibracion de corriente (Promedio de 250 muestras)
  long suma_i = 0;
  for (int i = 0; i < 250; i++) {
    suma_i += analogRead(PIN_CORRIENTE_A1);
    delayMicroseconds(400);
  }
  float adc_i_prom = suma_i / 250.0;
  v_offset_corriente = (adc_i_prom * VCC_REF) / 1023.0;

  // 2. Calibracion de gas R0 en aire limpio (Promedio de 250 muestras)
  analogRead(PIN_GAS_A0); // Dummy read tras conmutar canal ADC
  delay(10);
  long suma_gas = 0;
  for (int i = 0; i < 250; i++) {
    suma_gas += analogRead(PIN_GAS_A0);
    delayMicroseconds(400);
  }
  float adc_gas_prom = suma_gas / 250.0;
  v0_gas = (adc_gas_prom * VCC_REF) / 1023.0;
  if (v0_gas < 0.05) v0_gas = 0.05; // Evitar division por cero
  if (v0_gas > 4.95) v0_gas = 4.95;
  
  // Rs en aire limpio
  float rs_aire = RL_GAS * (VCC_REF - v0_gas) / v0_gas;
  // Segun datasheet de MQ-9: Rs(aire) / R0 = 9.80 => R0 = Rs(aire) / 9.80
  r0_gas = rs_aire / RATIO_AIRE_LIMPIO;
  if (r0_gas < 0.01) r0_gas = 0.01;

  Serial.print(F("{\"status\":\"calibrado\",\"v_off_i\":"));
  Serial.print(v_offset_corriente, 4);
  Serial.print(F(",\"v0_gas\":"));
  Serial.print(v0_gas, 4);
  Serial.print(F(",\"rs_aire\":"));
  Serial.print(rs_aire, 3);
  Serial.print(F(",\"r0_gas\":"));
  Serial.print(r0_gas, 3);
  Serial.println(F("}"));
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_GAS_D0, INPUT_PULLUP);
  pinMode(PIN_GAS_A0, INPUT);
  pinMode(PIN_CORRIENTE_A1, INPUT);

  // Retardo para estabilizacion de tensiones
  delay(400);

  // Calibracion inicial de linea base
  calibrarSensores();
}

void loop() {
  // Comandos por puerto serie ('c' o 'C' para recalibrar en caliente)
  if (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'c' || cmd == 'C') {
      calibrarSensores();
    }
  }

  unsigned long ahora = millis();
  if (ahora - ultimo_envio >= INTERVALO_MS) {
    ultimo_envio = ahora;

    // --- Lectura de Gas MQ-9 (Oversampling de 20 muestras) ---
    // Dummy read para que el multiplexor ADC del ATmega328P conmute limpiamente a A0
    analogRead(PIN_GAS_A0);
    delayMicroseconds(100);
    long suma_gas = 0;
    for (int i = 0; i < 20; i++) {
      suma_gas += analogRead(PIN_GAS_A0);
      delayMicroseconds(80);
    }
    float adc_gas = suma_gas / 20.0;
    float v_gas = (adc_gas * VCC_REF) / 1023.0;
    if (v_gas < 0.05) v_gas = 0.05;
    if (v_gas > 4.95) v_gas = 4.95;

    // Calculo de resistencia Rs y Ratio estandar Rs/R0 (Datasheet MQ-9)
    float rs_gas = RL_GAS * (VCC_REF - v_gas) / v_gas;
    float ratio_rs_r0 = (r0_gas > 0.001) ? (rs_gas / r0_gas) : 1.0;
    if (ratio_rs_r0 < 0.05) ratio_rs_r0 = 0.05;
    if (ratio_rs_r0 > 25.0) ratio_rs_r0 = 25.0;

    // Calculo de concentracion en PPM usando la ley potencial del datasheet
    // con compensacion por Limite de Deteccion (LOD) y tara de piso en aire limpio
    float ppm_alcohol = 0.0;
    float ppm_co = 0.0;
    if (ratio_rs_r0 < RATIO_LOD_LIMPIO) {
      ppm_alcohol = A_ALCOHOL * pow(ratio_rs_r0, B_ALCOHOL) - PPM_BASE_ALCOHOL;
      if (ppm_alcohol < 0.0) ppm_alcohol = 0.0;
      if (ppm_alcohol > 10000.0) ppm_alcohol = 10000.0;

      ppm_co = A_CO * pow(ratio_rs_r0, B_CO) - PPM_BASE_CO;
      if (ppm_co < 0.0) ppm_co = 0.0;
      if (ppm_co > 2000.0) ppm_co = 2000.0;
    }

    // Ratio ascendente visual (R0_aire / Rs) para monitoreo
    float ratio_visual = (rs_gas > 0.001) ? ((r0_gas * RATIO_AIRE_LIMPIO) / rs_gas) : 1.0;

    // Estado digital (D0 es active LOW cuando el gas supera el umbral del potenciometro)
    int alerta_gas = (digitalRead(PIN_GAS_D0) == LOW) ? 1 : 0;

    // --- Lectura de Corriente ACS758 (Oversampling de 25 muestras) ---
    analogRead(PIN_CORRIENTE_A1); // Dummy read para conmutar canal ADC a A1
    delayMicroseconds(100);
    long suma_i = 0;
    for (int i = 0; i < 25; i++) {
      suma_i += analogRead(PIN_CORRIENTE_A1);
      delayMicroseconds(80);
    }
    float adc_i = suma_i / 25.0;
    float v_i = (adc_i * VCC_REF) / 1023.0;
    float corriente = (v_i - v_offset_corriente) / SENSIBILIDAD_ACS;

    // Filtro de banda muerta (< 35 mA)
    if (abs(corriente) < 0.035) {
      corriente = 0.0;
    }
    float potencia = corriente * V_BAT_NOMINAL;

    // --- Transmision JSON estandar (Opcion B: gas_ratio emite PPM de Etanol para ROS 2) ---
    Serial.print(F("{\"t\":"));
    Serial.print(ahora);
    Serial.print(F(",\"gas_v\":"));
    Serial.print(v_gas, 3);
    Serial.print(F(",\"gas_raw\":"));
    Serial.print(adc_gas, 1);
    Serial.print(F(",\"gas_ratio\":"));
    Serial.print(ppm_alcohol, 2);
    Serial.print(F(",\"rs_r0\":"));
    Serial.print(ratio_rs_r0, 3);
    Serial.print(F(",\"ppm_alc\":"));
    Serial.print(ppm_alcohol, 2);
    Serial.print(F(",\"ppm_co\":"));
    Serial.print(ppm_co, 2);
    Serial.print(F(",\"gas_alerta\":"));
    Serial.print(alerta_gas);
    Serial.print(F(",\"i_amp\":"));
    Serial.print(corriente, 2);
    Serial.print(F(",\"i_v\":"));
    Serial.print(v_i, 3);
    Serial.print(F(",\"pot_w\":"));
    Serial.print(potencia, 2);
    Serial.println(F("}"));
  }
}
