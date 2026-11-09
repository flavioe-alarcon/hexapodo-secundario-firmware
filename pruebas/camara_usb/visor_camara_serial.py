"""
Visor de Video en Tiempo Real para Camara UVC sobre ESP32-S3 (Puerto Serial / COM)
Tesis de Ingenieria Mecatronica - UTEC 2026

Protocolo de trama binaria:
  Header (4B): 0xFF 0xAA 0x55 0xFF
  Payload len (4B): uint32 little-endian
  Width (2B): uint16 little-endian
  Height (2B): uint16 little-endian
  Seq (4B): uint32 little-endian
  JPEG Data (N bytes)
  Footer (2B): 0x00 0xFF
"""

import sys
import time
import struct
import serial
import serial.tools.list_ports
import cv2
import numpy as np

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

DEFAULT_BAUD_RATE = 1500000
MAGIC_HEADER = b'\xff\xaa\x55\xff'
MAGIC_FOOTER = b'\x00\xff'

def find_default_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "CH343" in p.description or "1A86:55D3" in p.hwid or "COM12" == p.device:
            return p.device
    if ports:
        return ports[-1].device
    return "COM12"

def main():
    port_name = sys.argv[1] if len(sys.argv) > 1 else find_default_port()
    baud_rate = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD_RATE

    print("=" * 60)
    print(f"[*] Visor de Camara UVC - ESP32-S3 (Version 2 Desacoplada)")
    print(f"[*] Conectando a {port_name} a {baud_rate} baudios...")
    print("[*] Presiona 'q' o ESC en la ventana de video para salir.")
    print("[*] Presiona 's' para guardar una captura JPEG.")
    print("=" * 60)

    try:
        ser = serial.Serial(port_name, baud_rate, timeout=0.05)
    except Exception as e:
        safe_print(f"[ERROR] No se pudo abrir {port_name}: {e}")
        return

    buffer = bytearray()
    log_line_buf = bytearray()
    
    fps_counter = 0
    fps_timer = time.time()
    current_fps = 0.0
    total_frames = 0
    last_frame = None
    last_frame_time = 0.0

    cv2.namedWindow("ESP32-S3 Camara UVC (Puerto COM)", cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            # Leer bytes disponibles
            waiting = ser.in_waiting
            if waiting > 0:
                chunk = ser.read(waiting)
                buffer.extend(chunk)

            # Buscar encabezado magico
            while True:
                idx = buffer.find(MAGIC_HEADER)
                if idx == -1:
                    # No hay header en el buffer.
                    # Extraer texto ascii para logs del ESP32
                    if len(buffer) > 3:
                        text_part = buffer[:-3]
                        # Buscar saltos de linea
                        while b'\n' in text_part:
                            nl_idx = text_part.find(b'\n')
                            line = (log_line_buf + text_part[:nl_idx]).decode('utf-8', errors='replace').strip()
                            if line:
                                safe_print(f"[ESP32-LOG] {line}")
                            log_line_buf.clear()
                            text_part = text_part[nl_idx+1:]
                        log_line_buf.extend(text_part)
                        buffer = buffer[-3:]
                    break

                # Si hay texto antes del header, imprimirlo como log
                if idx > 0:
                    prefix = buffer[:idx]
                    log_line_buf.extend(prefix)
                    while b'\n' in log_line_buf:
                        nl_idx = log_line_buf.find(b'\n')
                        line = log_line_buf[:nl_idx].decode('utf-8', errors='replace').strip()
                        if line:
                            safe_print(f"[ESP32-LOG] {line}")
                        log_line_buf = log_line_buf[nl_idx+1:]
                    buffer = buffer[idx:]

                # Verificar si tenemos los 16 bytes de cabecera
                if len(buffer) < 16:
                    break  # Esperar mas datos

                # Desempaquetar cabecera: length (uint32), width (uint16), height (uint16), seq (uint32)
                try:
                    payload_len, w, h, seq = struct.unpack('<IHHI', buffer[4:16])
                except Exception as e:
                    buffer = buffer[1:]
                    continue
                # Limite de cordura: si payload_len es mayor a 300 KB, es basura
                if payload_len > 300000 or payload_len < 100:
                    # Descartar este header invalido y avanzar 1 byte
                    buffer = buffer[1:]
                    continue

                packet_total_len = 16 + payload_len + 2
                if len(buffer) < packet_total_len:
                    break  # Esperar a que llegue el resto del JPEG

                # Verificar footer
                footer = buffer[16 + payload_len : packet_total_len]
                if footer != MAGIC_FOOTER:
                    print(f"[WARN] Error de footer en paquete #{seq}. Resincronizando...")
                    buffer = buffer[4:]
                    continue

                # Extraer JPEG valido
                jpeg_data = bytes(buffer[16 : 16 + payload_len])
                buffer = buffer[packet_total_len:]

                # Decodificar JPEG
                nparr = np.frombuffer(jpeg_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if img is not None:
                    last_frame = img
                    last_frame_time = time.time()
                    total_frames += 1
                    fps_counter += 1

                    # Calculo de FPS
                    now = time.time()
                    if now - fps_timer >= 1.0:
                        current_fps = fps_counter / (now - fps_timer)
                        fps_counter = 0
                        fps_timer = now

                    # Dibujar overlay con telemetria
                    overlay = img.copy()
                    ih, iw = img.shape[:2]
                    cv2.rectangle(overlay, (0, 0), (iw, 32), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

                    text = f"ESP32-S3 V2 | {iw}x{ih} | {current_fps:.1f} FPS | #{seq} | {payload_len/1024:.1f} KB"
                    cv2.putText(img, text, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 128), 2, cv2.LINE_AA)
                    cv2.imshow("ESP32-S3 Camara UVC (Puerto COM)", img)

            now = time.time()
            if last_frame is not None and (now - last_frame_time > 2.0):
                # Aviso de desconexión o pausa si pasan más de 2 segundos sin cuadros
                status_img = (last_frame * 0.4).astype(np.uint8)
                cv2.putText(status_img, "Camara en Pausa / Desconectada", (40, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 120, 255), 2)
                cv2.putText(status_img, "Esperando reconexion USB...", (60, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (220, 220, 220), 1)
                cv2.imshow("ESP32-S3 Camara UVC (Puerto COM)", status_img)
            elif last_frame is None:
                blank = np.zeros((320, 480, 3), dtype=np.uint8)
                cv2.putText(blank, "ESP32-S3 Conectado (COM12)", (50, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                cv2.putText(blank, "Esperando camara UVC...", (80, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                cv2.putText(blank, "Asegurate de alimentar VBUS (5V)", (70, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 200, 100), 1)
                cv2.imshow("ESP32-S3 Camara UVC (Puerto COM)", blank)

            key = cv2.waitKey(1) & 0xFF
            if key == 27 or key == ord('q'):
                break
            try:
                if cv2.getWindowProperty("ESP32-S3 Camara UVC (Puerto COM)", cv2.WND_PROP_VISIBLE) < 1:
                    break
            except Exception:
                pass
            if key == ord('s') and last_frame is not None:
                filename = f"captura_{int(time.time())}.jpg"
                cv2.imwrite(filename, last_frame)
                print(f"[OK] Captura guardada como {filename}")

    except KeyboardInterrupt:
        print("\n[*] Interrumpido por usuario.")
    finally:
        ser.close()
        cv2.destroyAllWindows()
        print("[*] Puerto serial cerrado y visor finalizado.")

if __name__ == "__main__":
    main()
