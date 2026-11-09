/*
 * TEST AUTOMATIZADO V2 - MODO PH/EN Y PWM DEDICADO
 * Comandos:
 * 'A' -> Modo PH/EN Giro Horario (IN1=PWM, IN2=LOW)
 * 'B' -> Modo PH/EN Giro Antihorario (IN1=PWM, IN2=HIGH)
 * 'F' -> Modo PWM1 puro (IN1=PWM, IN2=LOW)
 * 'R' -> Modo PWM2 puro (IN1=LOW, IN2=PWM)
 * 'S' -> Freno total
 * 'T' -> Telemetria (ticks, CS)
 * 'Z' -> Reset ticks
 */

const int M1_IN1 = 21;
const int M1_IN2 = 19;
const int M1_CS  = 36;
const int M1_C1  = 32;
const int M1_C2  = 33;

volatile long ticksM1 = 0;

void IRAM_ATTR isrM1() {
  if (digitalRead(M1_C2) == HIGH) ticksM1++; else ticksM1--;
}

void setup() {
  Serial.begin(115200);
  pinMode(M1_IN1, OUTPUT);
  pinMode(M1_IN2, OUTPUT);
  freno();

  pinMode(M1_C1, INPUT_PULLUP);
  pinMode(M1_C2, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(M1_C1), isrM1, RISING);

  Serial.println("READY_V2");
}

void freno() {
  analogWrite(M1_IN1, 0);
  digitalWrite(M1_IN1, LOW);
  analogWrite(M1_IN2, 0);
  digitalWrite(M1_IN2, LOW);
}

void loop() {
  if (Serial.available() > 0) {
    char cmd = Serial.read();

    if (cmd == 'A') { // PH/EN Horario
      digitalWrite(M1_IN2, LOW);
      analogWrite(M1_IN1, 130);
      Serial.println("OK:PH_LOW");
    }
    else if (cmd == 'B') { // PH/EN Antihorario
      digitalWrite(M1_IN2, HIGH);
      analogWrite(M1_IN1, 130);
      Serial.println("OK:PH_HIGH");
    }
    else if (cmd == 'F') { // IN1 activo
      digitalWrite(M1_IN2, LOW);
      analogWrite(M1_IN1, 130);
      Serial.println("OK:IN1_PWM");
    }
    else if (cmd == 'R') { // IN2 activo
      digitalWrite(M1_IN1, LOW);
      analogWrite(M1_IN2, 130);
      Serial.println("OK:IN2_PWM");
    }
    else if (cmd == 'S') { // Stop
      freno();
      Serial.println("OK:STOP");
    }
    else if (cmd == 'Z') {
      ticksM1 = 0;
      Serial.println("OK:ZERO");
    }
    else if (cmd == 'T') {
      int csVal = analogRead(M1_CS);
      Serial.printf("DATA:%ld,%d\n", ticksM1, csVal);
    }
    else if (cmd == 'P') {
      Serial.println("PONG");
    }
  }
}
