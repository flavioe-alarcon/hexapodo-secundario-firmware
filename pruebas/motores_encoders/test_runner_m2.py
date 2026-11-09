import serial
import time
import sys

PORT = "COM11"
BAUD = 115200

def test_motor2():
    print(f"[*] Conectando a {PORT} a {BAUD} baudios...")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1.0)
    except Exception as e:
        print(f"[!] Error al abrir el puerto: {e}")
        return

    time.sleep(2.0)
    ser.reset_input_buffer()

    print("[*] Verificando comunicación...")
    ser.write(b"P\n")
    time.sleep(0.1)
    resp = ser.readline().decode('utf-8', errors='ignore').strip()
    print(f"[ESP32 Resp]: {resp}")

    # Reset ticks
    ser.write(b"Z\n")
    time.sleep(0.1)
    ser.reset_input_buffer()

    # FASE 1: Sentido A (IN1 = D18 PWM 130, IN2 = D17 LOW) por 1.5s
    print("\n[+] PASO 1: Giro Sentido A (IN1=D18 PWM 130, IN2=D17 LOW) - 1.5 segundos")
    ser.write(b"1\n")
    time.sleep(0.05)
    t0 = time.time()
    while time.time() - t0 < 1.5:
        ser.write(b"T\n")
        time.sleep(0.15)
        l = ser.readline().decode('utf-8', errors='ignore').strip()
        if 'DATA:' in l:
            print("   ", l)

    ser.write(b"S\n")
    print("[*] Freno aplicado (1 segundo de pausa)...")
    time.sleep(1.0)

    # FASE 2: Sentido B (IN1 = D18 LOW, IN2 = D17 PWM 130) por 1.5s
    print("\n[+] PASO 2: Giro Sentido B (IN1=D18 LOW, IN2=D17 PWM 130) - 1.5 segundos")
    ser.write(b"2\n")
    time.sleep(0.05)
    t0 = time.time()
    while time.time() - t0 < 1.5:
        ser.write(b"T\n")
        time.sleep(0.15)
        l = ser.readline().decode('utf-8', errors='ignore').strip()
        if 'DATA:' in l:
            print("   ", l)

    ser.write(b"S\n")
    print("[*] Freno final aplicado.")
    time.sleep(0.2)
    ser.write(b"T\n")
    print("[*] Estado final:", ser.readline().decode('utf-8', errors='ignore').strip())

    ser.close()
    print("\n[OK] Prueba de Motor 2 completada.")

if __name__ == "__main__":
    test_motor2()
