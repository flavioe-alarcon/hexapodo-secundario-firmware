import serial
import time
import sys

PORT = "COM11"
BAUD = 115200

def test_motor():
    print(f"[*] Abriendo puerto serie en {PORT} a {BAUD} baudios...")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1.0)
    except Exception as e:
        print(f"[!] Error al abrir el puerto: {e}")
        return

    # Esperar reinicio de la conexion DTR/RTS
    time.sleep(2.0)
    ser.reset_input_buffer()

    print("[*] Verificando comunicacion con el ESP32...")
    ser.write(b"P\n")
    time.sleep(0.1)
    resp = ser.read_all().decode('utf-8', errors='ignore')
    print(f"[ESP32]: {resp.strip()}")

    # 1. Resetear contador de ticks
    ser.write(b"Z\n")
    time.sleep(0.1)

    # 2. Prueba de Giro Adelante (F100)
    print("\n[+] PRUEBA 1: GIRO ADELANTE (PWM = 100 / 255) durante 1.5s")
    ser.write(b"F100\n")
    
    t_start = time.time()
    while time.time() - t_start < 1.5:
        ser.write(b"R\n")
        time.sleep(0.1)
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line.startswith("DATA:"):
            _, vals = line.split(":")
            ticks, cs = vals.split(",")
            print(f"    -> [ADELANTE] Ticks: {ticks:>6} | CS (Corriente ADC): {cs:>4}")

    # Parada
    ser.write(b"S\n")
    print("[*] Freno aplicado. Pausa de 1 segundo...")
    time.sleep(1.0)

    # 3. Prueba de Giro Atras (B100)
    print("\n[+] PRUEBA 2: GIRO ATRAS (PWM = 100 / 255) durante 1.5s")
    ser.write(b"B100\n")

    t_start = time.time()
    while time.time() - t_start < 1.5:
        ser.write(b"R\n")
        time.sleep(0.1)
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if line.startswith("DATA:"):
            _, vals = line.split(":")
            ticks, cs = vals.split(",")
            print(f"    -> [ATRAS]    Ticks: {ticks:>6} | CS (Corriente ADC): {cs:>4}")

    # Parada final
    ser.write(b"S\n")
    print("\n[*] Freno final ejecutado. Leyendo estado final...")
    time.sleep(0.2)
    ser.write(b"R\n")
    final_line = ser.readline().decode('utf-8', errors='ignore').strip()
    print(f"[*] Resultado final: {final_line}")

    ser.close()
    print("\n[V] Prueba automatica finalizada con exito.")

if __name__ == "__main__":
    test_motor()
