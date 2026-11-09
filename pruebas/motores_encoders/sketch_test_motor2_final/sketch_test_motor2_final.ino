/*
 * TEST AUTOMATIZADO DEFINITIVO - MOTOR 2 (FÉMUR)
 * Pines de control: IN1 = D18, IN2 = D17
 * Pin de corriente: CS = Pin 39 (VN)
 * Encoders separados: C1 = D25, C2 = D13
 */

const int M2_IN1 = 18;
const int M2_IN2 = 17;
const int M2_CS  = 39; // VN (ADC1)
const int M2_C1  = 25; // D25
const int M2_C2  = 13; // D13 (Aislado con pull-up)

volatile long ticksM2 = 0;

void IRAM_ATTR isrM2() {
  int c1 = digitalRead(M2_C1);
  int c2 = digitalRead(M2_C2);
  if (c1 != c2) ticksM2++; else ticksM2--;
}

void setup() {
  Serial.begin(115200);
  pinMode(M2_IN1, OUTPUT);
  pinMode(M2_IN2, OUTPUT);
  freno();

  pinMode(M2_C1, INPUT_PULLUP);
  pinMode(M2_C2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(M2_C1), isrM2, CHANGE);

  Serial.println("READY_M2_FINAL");
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

    if (cmd == '1') { // Sentido A (IN1 = PWM 130, IN2 = LOW)
      digitalWrite(M2_IN2, LOW);
      analogWrite(M2_IN1, 130);
      Serial.println("OK:M2_IN1_PWM");
    }
    else if (cmd == '2') { // Sentido B (IN1 = LOW, IN2 = PWM 130)
      digitalWrite(M2_IN1, LOW);
      analogWrite(M2_IN2, 130);
      Serial.println("OK:M2_IN2_PWM");
    }
    else if (cmd == 'F') { // Sentido A FULL 100% (IN1 = HIGH, IN2 = LOW)
      digitalWrite(M2_IN2, LOW);
      digitalWrite(M2_IN1, HIGH);
      Serial.println("OK:M2_IN1_FULL");
    }
    else if (cmd == 'R') { // Sentido B FULL 100% (IN1 = LOW, IN2 = HIGH)
      digitalWrite(M2_IN1, LOW);
      digitalWrite(M2_IN2, HIGH);
      Serial.println("OK:M2_IN2_FULL");
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
