import serial
import time

ser = serial.Serial('COM11', 115200, timeout=1.0)
time.sleep(2.0)
ser.reset_input_buffer()

print("[*] Conectado al ESP32. Iniciando pruebas comparativas...")

# 1. Reset
ser.write(b'Z\n')
time.sleep(0.1)

# PRUEBA A: MODO PH/EN Giro Horario (IN1=PWM, IN2=LOW)
print("\n[+] PRUEBA 1: IN1=PWM, IN2=LOW (1.5 segundos)")
ser.write(b'A\n')
t0 = time.time()
while time.time() - t0 < 1.5:
    ser.write(b'T\n')
    time.sleep(0.15)
    l = ser.readline().decode('utf-8', errors='ignore').strip()
    if 'DATA:' in l:
        print("   ", l)

ser.write(b'S\n')
print("[*] Freno aplicado (1 seg)")
time.sleep(1.0)

# PRUEBA B: MODO PH/EN Giro Antihorario (IN1=PWM, IN2=HIGH)
print("\n[+] PRUEBA 2: IN1=PWM, IN2=HIGH (1.5 segundos) -> Observa si invierte el giro!")
ser.write(b'B\n')
t0 = time.time()
while time.time() - t0 < 1.5:
    ser.write(b'T\n')
    time.sleep(0.15)
    l = ser.readline().decode('utf-8', errors='ignore').strip()
    if 'DATA:' in l:
        print("   ", l)

ser.write(b'S\n')
print("[*] Freno final.")
time.sleep(0.2)
ser.write(b'T\n')
print("[*] Estado final:", ser.readline().decode('utf-8', errors='ignore').strip())
ser.close()
