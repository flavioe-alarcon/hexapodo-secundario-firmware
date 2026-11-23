#!/usr/bin/env python3
"""
========================================================================================
Monitor de Telemetria en Raspberry Pi para Sensor de Gas MQ-9 y Corriente ACS758
Plataforma: Raspberry Pi 5 (Ubuntu / ROS 2) conectada por USB al Arduino Nano
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Flavio Alarcon, Aleskyjubinsl Alcarraz, Alfredo Erazo
Asesor: Dante Inga Narvaez

Lee tramas JSON a 115200 baudios desde /dev/ttyUSB0 (o /dev/ttyACM0)
========================================================================================
"""

import sys
import time
import json
import serial
import serial.tools.list_ports

def encontrar_puerto():
    puertos = list(serial.tools.list_ports.comports())
    for p in puertos:
        if "USB" in p.device or "ACM" in p.device:
            return p.device
    return "/dev/ttyUSB0"

def main():
    puerto = sys.argv[1] if len(sys.argv) > 1 else encontrar_puerto()
    baud = 115200

    print("===========================================================================")
    print(f"  MONITOR DE SENSORES MQ-9 & ACS758 EN RASPBERRY PI 5")
    print(f"  Puerto: {puerto} | Velocidad: {baud} baudios")
    print("===========================================================================")

    try:
        ser = serial.Serial(puerto, baud, timeout=1.0)
        time.sleep(1.8) # Esperar estabilizacion de Arduino tras reset por DTR
        ser.reset_input_buffer()
        print(f"[+] Conexion exitosa con el Arduino Nano en {puerto}.\n")
    except Exception as e:
        print(f"[-] Error abriendo {puerto}: {e}")
        print("    Asegurate de que tu usuario tenga permisos: sudo usermod -aG dialout $USER")
        print("    O de forma temporal: sudo chmod 666 " + puerto)
        sys.exit(1)

    print("-" * 92)
    print(f"{'Tiempo (s)':<11} | {'Gas (V)':<8} | {'Rs/R0':<8} | {'PPM Etanol':<11} | {'PPM CO':<9} | {'Alerta D0':<12} | {'Corriente (A)':<13}")
    print("-" * 92)

    try:
        while True:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                continue

            if line.startswith("{") and line.endswith("}"):
                try:
                    data = json.loads(line)
                    if "status" in data and data["status"] == "calibrado":
                        print(f"[*] Calibracion recibida: V_off_i={data.get('v_off_i')}V, V0_gas={data.get('v0_gas')}V, R0={data.get('r0_gas')}k")
                        continue

                    if "gas_v" in data:
                        t_sec = data.get("t", 0) / 1000.0
                        gas_v = data.get("gas_v", 0.0)
                        rs_r0 = data.get("rs_r0", 1.0)
                        ppm_alc = data.get("ppm_alc", 0.0)
                        ppm_co = data.get("ppm_co", 0.0)
                        alerta_num = data.get("gas_alerta", 0)
                        alerta_str = "[!ETANOL!]" if alerta_num == 1 else "[NORMAL]"
                        i_amp = data.get("i_amp", 0.0)

                        print(f"{t_sec:<11.1f} | {gas_v:<8.3f} | {rs_r0:<8.2f} | {ppm_alc:<11.1f} | {ppm_co:<9.1f} | {alerta_str:<12} | {i_amp:<13.2f}")
                except json.JSONDecodeError:
                    pass
    except KeyboardInterrupt:
        print("\n[+] Monitor detenido por el usuario.")
    finally:
        ser.close()

if __name__ == '__main__':
    main()
