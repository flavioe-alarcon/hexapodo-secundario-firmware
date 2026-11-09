/*
 * TEST AUTOMATIZADO - MOTOR 2 (FÉMUR - N20 + DRV8876)
 * Pines según arquitectura:
 * Pin IN1 = D18 (GPIO 18)
 * Pin IN2 = D17 (GPIO 17)
 * Pin CS  = 39  (VN / ADC1_CH3)
 * Encoders: C1 = D25 (GPIO 25), C2 = D26 (GPIO 26)
 */

const int M2_IN1 = 18;
const int M2_IN2 = 17;
const int M2_CS  = 39; // VN (ADC1)
const int M2_C1  = 25;
const int M2_C2  = 26;

volatile long ticksM2 = 0;

void IRAM_ATTR isrM2() {
  if (digitalRead(M2_C2) == HIGH) ticksM2++; else ticksM2--;
}

void setup() {
  Serial.begin(115200);
  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);
  freno();

  pinMode(M2_C1, INPUT_PULLUP);
  pinMode(M2_C2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(M2_C1), isrM2, RISING);

  Serial.println("READY_M2");
}

void freno() {
  analogWrite(M2_IN1, 0);
  digitalWrite(M2_IN1, LOW);
  analogWrite(M2_IN2, 0);
  digitalWrite(M2_IN2, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    // 1. Sentido A (IN1 = PWM, IN2 = LOW)
    if (cmd == '1') {
      digitalWrite(M2_IN2, LOW);
      analogWrite(M2_IN1, 130);
      Serial.println("OK:M2_IN1_PWM");
    }
    // 2. Sentido B (IN1 = LOW, IN2 = PWM)
    else if (cmd == '2') {
      digitalWrite(M2_IN1, LOW);
      analogWrite(M2_IN2, 130);
      Serial.println("OK:M2_IN2_PWM");
    }
    else if (cmd == 'S') { // Freno
      freno();
      Serial.println("OK:STOP");
    }
    else if (cmd == 'Z') { // Reset ticks
      ticksM2 = 0;
      Serial.println("OK:ZERO");
    }
    else if (cmd == 'T') { // Telemetria
      int csVal = analogRead(M2_CS);
      Serial.printf("DATA:%ld,%d\n", ticksM2, csVal);
    }
    else if (cmd == 'P') {
      Serial.println("PONG");
    }
  }
}
