"""
Visor de Video Inalámbrico Wi-Fi para Cámara UVC sobre ESP32-S3 (OpenCV)
Tesis de Ingeniería Mecatrónica - UTEC 2026

Modo SoftAP:
  Red Wi-Fi: ESP32S3-CAM
  Clave: camara123
  URL del Stream: http://192.168.4.1/stream
"""

import sys
import time
import urllib.request
import cv2
import numpy as np

DEFAULT_STREAM_URL = "http://192.168.4.1/stream"

# Asegurar compatibilidad de salida UTF-8 en consola de Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_print(text):
    try:
        print(text, flush=True)
    except Exception:
        try:
            print(text.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass

def main():
    stream_url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_STREAM_URL

    print("=" * 65)
    print(" [*] Visor Wi-Fi de Cámara UVC - ESP32-S3 (OpenCV)")
    print(f" [*] Conectando a URL: {stream_url}")
    print(" [*] Asegúrate de que tu laptop esté conectada al Wi-Fi:")
    print("       SSID: ESP32S3-CAM  |  Clave: camara123")
    print(" [*] Controles:")
    print("       'q' o ESC : Salir del visor")
    print("       's'       : Guardar captura instantánea (.jpg)")
    print("=" * 65)

    window_title = "ESP32-S3 Camara UVC (Wi-Fi 802.11 b/g/n)"
    cv2.namedWindow(window_title, cv2.WINDOW_AUTOSIZE)

    stream = None
    bytes_buffer = bytearray()
    
    fps_counter = 0
    fps_timer = time.time()
    current_fps = 0.0
    total_frames = 0
    last_frame = None
    last_frame_time = 0.0
    bytes_this_sec = 0
    current_kb_sec = 0.0

    while True:
        # 1. Intentar conectar al stream HTTP si no está conectado
        if stream is None:
            # Mostrar pantalla de espera interactiva
            blank = np.zeros((360, 540, 3), dtype=np.uint8)
            cv2.putText(blank, "Conectando al Wi-Fi del ESP32-S3...", (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 200, 255), 2)
            cv2.putText(blank, "1. Conecta tu laptop a: ESP32S3-CAM", (40, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
            cv2.putText(blank, "2. Clave Wi-Fi: camara123", (40, 195),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
            cv2.putText(blank, f"Buscando stream: {stream_url}", (40, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 100), 1)
            cv2.imshow(window_title, blank)

            key = cv2.waitKey(200) & 0xFF
            if key == 27 or key == ord('q'):
                break

            try:
                safe_print(f"[*] Intentando abrir stream en {stream_url}...")
                req = urllib.request.Request(
                    stream_url,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                stream = urllib.request.urlopen(req, timeout=3.0)
                safe_print("[+] Conexión HTTP establecida exitosamente! Recibiendo video...")
                bytes_buffer.clear()
            except Exception as e:
                time.sleep(0.5)
                continue

        # 2. Leer chunks del stream MJPEG
        try:
            chunk = stream.read(4096)
            if not chunk:
                safe_print("[-] Stream finalizado o cerrado por el servidor.")
                stream.close()
                stream = None
                continue

            bytes_this_sec += len(chunk)
            bytes_buffer.extend(chunk)

            # Buscar delimitadores JPEG: 0xFF 0xD8 (SOI) y 0xFF 0xD9 (EOI)
            a = bytes_buffer.find(b'\xff\xd8')
            b = bytes_buffer.find(b'\xff\xd9')

            if a != -1 and b != -1 and b > a:
                jpg = bytes_buffer[a:b+2]
                bytes_buffer = bytes_buffer[b+2:]

                # Decodificar JPEG
                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                if img is not None:
                    last_frame = img
                    last_frame_time = time.time()
                    total_frames += 1
                    fps_counter += 1

                    # Cálculo de FPS y tasa de transferencia
                    now = time.time()
                    if now - fps_timer >= 1.0:
                        elapsed = now - fps_timer
                        current_fps = fps_counter / elapsed
                        current_kb_sec = (bytes_this_sec / 1024.0) / elapsed
                        fps_counter = 0
                        bytes_this_sec = 0
                        fps_timer = now

                    # Dibujar barra de telemetría superior
                    overlay = img.copy()
                    ih, iw = img.shape[:2]
                    cv2.rectangle(overlay, (0, 0), (iw, 32), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

                    text = f"Wi-Fi AP | {iw}x{ih} | {current_fps:.1f} FPS | {current_kb_sec:.1f} KB/s | #{total_frames}"
                    cv2.putText(img, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 128), 2, cv2.LINE_AA)
                    cv2.imshow(window_title, img)

        except Exception as e:
            safe_print(f"[-] Error en el flujo del stream: {e}")
            if stream:
                try: stream.close()
                except Exception: pass
            stream = None
            time.sleep(0.5)

        # 3. Supervisar si la cámara se pausó o desconectó
        now = time.time()
        if last_frame is not None and (now - last_frame_time > 2.0):
            status_img = (last_frame * 0.4).astype(np.uint8)
            cv2.putText(status_img, "Camara en Pausa / Desconectada", (40, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 120, 255), 2)
            cv2.putText(status_img, "Esperando fotogramas Wi-Fi...", (60, 170),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
            cv2.imshow(window_title, status_img)

        # 4. Manejo de teclado y ventana
        key = cv2.waitKey(1) & 0xFF
        if key == 27 or key == ord('q'):
            break
        try:
            if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                break
        except Exception:
            pass
        if key == ord('s') and last_frame is not None:
            filename = f"captura_wifi_{int(time.time())}.jpg"
            cv2.imwrite(filename, last_frame)
            safe_print(f"[+] Captura guardada como {filename}")

    if stream:
        try: stream.close()
        except Exception: pass
    cv2.destroyAllWindows()
    safe_print("[*] Visor Wi-Fi finalizado.")

if __name__ == "__main__":
    main()
