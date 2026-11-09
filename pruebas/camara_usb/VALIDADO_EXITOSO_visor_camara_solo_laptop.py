#!/usr/bin/env python3
"""
========================================================================================
VISOR OPENCV EN LAPTOP · PRUEBA DE CAMARA UVC STANDALONE (ESP32-S3)
========================================================================================
Conecta al stream TCP en http://192.168.4.1:81/stream
Muestra ventana grafica OpenCV con indicador de STANDBY vs CAMARA ACTIVA en tiempo real.
========================================================================================
"""

import sys
import time
import urllib.request
import numpy as np
import cv2

STREAM_URL = "http://192.168.4.1:81/stream"

def main():
    print("=" * 65)
    print("  VISOR DE CAMARA UVC - TEST DE ROBUSTEZ Y STANDBY")
    print("=" * 65)
    print(f"[*] Conectando a {STREAM_URL}...")
    print("[*] Presiona 'q' o ESC en la ventana para salir.\n")

    while True:
        try:
            req = urllib.request.Request(STREAM_URL, headers={"User-Agent": "OpenCV-Client"})
            with urllib.request.urlopen(req, timeout=5.0) as stream:
                print("[+] Conectado al stream MJPEG del ESP32-S3.")
                bufer = bytearray()
                fps_count = 0
                t_prev = time.time()
                fps = 0.0

                while True:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    bufer.extend(chunk)

                    a = bufer.find(b'\xff\xd8')
                    b = bufer.find(b'\xff\xd9', a + 2) if a != -1 else -1

                    if a != -1 and b != -1:
                        jpg_bytes = bytes(bufer[a:b + 2])
                        del bufer[:b + 2]

                        frame_len = len(jpg_bytes)
                        es_standby = (frame_len <= 700)

                        img = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

                        fps_count += 1
                        t_now = time.time()
                        if t_now - t_prev >= 1.0:
                            fps = fps_count / (t_now - t_prev)
                            fps_count = 0
                            t_prev = t_now

                        if img is not None:
                            # Si es frame standby (16x16), reescalar para visualizacion clara
                            if es_standby:
                                display = np.zeros((320, 480, 3), dtype=np.uint8)
                                cv2.putText(display, "[ MODO STANDBY ]", (110, 130),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
                                cv2.putText(display, "Camara Apagada o Desconectada", (70, 170),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1)
                                cv2.putText(display, "Conexion TCP mantenida activa", (85, 210),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                            else:
                                display = img.copy()
                                h, w = display.shape[:2]
                                cv2.putText(display, f"EN VIVO - UVC {w}x{h}", (15, 30),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                cv2.putText(display, f"{fps:4.1f} FPS | {frame_len/1024.0:.1f} KB", (15, 60),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

                            cv2.imshow("Robot Hexapodo - Camara UVC", display)
                            key = cv2.waitKey(1) & 0xFF
                            if key == ord('q') or key == 27:
                                return

        except Exception as e:
            print(f"[!] Error de conexion: {e}. Reintentando en 1.5s...")
            time.sleep(1.5)

if __name__ == "__main__":
    main()
