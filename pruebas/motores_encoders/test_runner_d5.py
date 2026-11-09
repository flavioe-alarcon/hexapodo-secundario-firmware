import serial
import time

ser = serial.Serial('COM11', 115200, timeout=1.0)
time.sleep(2.0)
ser.reset_input_buffer()

print("[*] Conectado al ESP32 con IN2 en D5.")

# Reset ticks
ser.write(b'Z\n')
time.sleep(0.1)

# FASE 1: IN1 con PWM, IN2 en LOW (1.5s)
print("\n[+] PASO 1: Mandando PWM a IN1 (D21) con IN2 en LOW (1.5 segundos)")
ser.write(b'1\n')
t0 = time.time()
while time.time() - t0 < 1.5:
    ser.write(b'T\n')
    time.sleep(0.15)
    l = ser.readline().decode('utf-8', errors='ignore').strip()
    if 'DATA:' in l:
        print("   ", l)

ser.write(b'S\n')
print("[*] Freno aplicado (1 segundo)")
time.sleep(1.0)

# FASE 2: IN2 con PWM (D5), IN1 en LOW (1.5s)
print("\n[+] PASO 2: Mandando PWM a IN2 (D5) con IN1 en LOW (1.5 segundos) -> Observa la cinta!")
ser.write(b'2\n')
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
