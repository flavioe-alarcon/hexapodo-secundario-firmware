"""
========================================================================================
Visor RTP / UDP de Video UVC y Telemetría de Gases MiCS-5524 para ESP32-S3 (OpenCV)
Tesis de Ingeniería Mecatrónica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcón, Alfredo Erazo
Asesor: Dante Inga Narváez

Arquitectura V7:
  - Video UVC: Protocolo Estándar RFC 3550 RTP sobre UDP (Puerto 5004) con Packet Pacing
  - Telemetría de Gas: Broadcast UDP Datagramas JSON a 20 Hz (Puerto 5005)
  - Calibración R0: HTTP POST a http://192.168.4.1/calibrate
  - Control de Latencia: Unicast directo con handshake de autodetección
========================================================================================
"""

import sys
import os
import time
import json
import socket
import struct
import threading
import datetime
import urllib.request
import cv2
import numpy as np

DEFAULT_HOST = "192.168.4.1"
GAS_UDP_PORT = 5005
VIDEO_RTP_PORT = 5004
RTP_PAYLOAD_TYPE_JPEG = 26

# Compatibilidad UTF-8 en consolas Windows
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


class VideoReceiverRTP:
    """Hilo receptor y reensamblador de paquetes RTP/UDP de video JPEG (Puerto 5004)"""
    def __init__(self, host=DEFAULT_HOST, port=VIDEO_RTP_PORT):
        self.host = host
        self.port = port
        self.running = False
        self.latest_frame = None
        self.fps = 0.0
        self.kb_sec = 0.0
        self.total_frames = 0
        self.dropped_frames = 0
        self.packet_loss_rate = 0.0
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024) # 2 MB buffer
        except Exception:
            pass

        try:
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(0.2)
            safe_print(f"[*] [RTP-VIDEO] Socket a la escucha en puerto UDP {self.port}...")
        except Exception as e:
            safe_print(f"[!] [RTP-VIDEO] Error bindeando socket: {e}")
            return

        # Enviar handshake inicial al ESP32 para vincular IP Unicast
        try:
            sock.sendto(b"HELLO_RTP", (self.host, self.port))
            safe_print(f"[*] [RTP-VIDEO] Handshake enviado a {self.host}:{self.port}")
        except Exception as e:
            safe_print(f"[!] [RTP-VIDEO] Error enviando handshake inicial: {e}")

        frame_buffers = {}       # {frame_id: {chunk_idx: bytes}}
        frame_totals = {}        # {frame_id: total_chunks}
        frame_timestamps = {}    # {frame_id: time_created}

        fps_counter = 0
        fps_timer = time.time()
        handshake_timer = time.time()
        bytes_this_sec = 0
        total_packets_sec = 0
        lost_packets_sec = 0
        expected_seq = -1
        last_completed_frame_id = -1

        while self.running:
            # Enviar keepalive/handshake cada 2 segundos para mantener el puerto NAT / IP viva
            now = time.time()
            if now - handshake_timer > 2.0:
                try:
                    sock.sendto(b"PING_RTP", (self.host, self.port))
                except Exception:
                    pass
                handshake_timer = now

            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    safe_print(f"[!] [RTP-VIDEO] Error recv: {e}")
                break

            if len(data) < 20: # 12 bytes RTP + 8 bytes extension
                continue

            bytes_this_sec += len(data)
            total_packets_sec += 1

            # 1. Desempaquetar cabecera RTP RFC 3550 (12 bytes)
            # '>BBHII' -> b0, b1, seq_num (uint16), timestamp (uint32), ssrc (uint32)
            b0, b1, seq_num, rtp_ts, ssrc = struct.unpack('>BBHII', data[:12])
            version = (b0 >> 6) & 0x03
            marker = (b1 >> 7) & 0x01
            pt = b1 & 0x7F

            if version != 2 or pt != RTP_PAYLOAD_TYPE_JPEG:
                continue

            # Detección de pérdida de paquetes a nivel de secuencia RTP
            if expected_seq != -1:
                seq_diff = (seq_num - expected_seq) & 0xFFFF
                if seq_diff > 0:
                    lost_packets_sec += seq_diff
            expected_seq = (seq_num + 1) & 0xFFFF

            # 2. Desempaquetar extensión de fotograma (8 bytes)
            frame_id, chunk_idx, total_chunks = struct.unpack('>IHH', data[12:20])

            if frame_id <= last_completed_frame_id and (last_completed_frame_id - frame_id) < 500:
                # Cuadro viejo/anterior
                continue

            payload = data[20:]

            if frame_id not in frame_buffers:
                frame_buffers[frame_id] = {}
                frame_totals[frame_id] = total_chunks
                frame_timestamps[frame_id] = now

            frame_buffers[frame_id][chunk_idx] = payload

            # ¿Fotograma completo?
            if len(frame_buffers[frame_id]) == total_chunks or (marker == 1 and len(frame_buffers[frame_id]) == total_chunks):
                chunks = [frame_buffers[frame_id][i] for i in range(total_chunks) if i in frame_buffers[frame_id]]
                if len(chunks) == total_chunks:
                    jpeg_bytes = b"".join(chunks)
                    img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if img is not None:
                        with self.lock:
                            self.latest_frame = img
                            self.total_frames += 1
                        fps_counter += 1
                        last_completed_frame_id = frame_id

                # Limpieza de cuadros anteriores al completado
                keys_to_del = [f for f in list(frame_buffers.keys()) if f <= frame_id]
                for k in keys_to_del:
                    frame_buffers.pop(k, None)
                    frame_totals.pop(k, None)
                    frame_timestamps.pop(k, None)

            # Limpieza periódica de cuadros viejos o incompletos (>0.3s)
            if len(frame_buffers) > 8:
                expired = [f for f, t in frame_timestamps.items() if now - t > 0.3]
                for f in expired:
                    frame_buffers.pop(f, None)
                    frame_totals.pop(f, None)
                    frame_timestamps.pop(f, None)
                    self.dropped_frames += 1

            # Métricas calculadas por segundo
            if now - fps_timer >= 1.0:
                dt = now - fps_timer
                self.fps = fps_counter / dt
                self.kb_sec = (bytes_this_sec / 1024.0) / dt
                if (total_packets_sec + lost_packets_sec) > 0:
                    self.packet_loss_rate = (lost_packets_sec / (total_packets_sec + lost_packets_sec)) * 100.0
                else:
                    self.packet_loss_rate = 0.0

                fps_counter = 0
                bytes_this_sec = 0
                total_packets_sec = 0
                lost_packets_sec = 0
                fps_timer = now

        sock.close()


class GasReceiverUDP:
    """Hilo receptor de telemetría de gases por UDP en tiempo real (Puerto 5005)"""
    def __init__(self, port=GAS_UDP_PORT):
        self.port = port
        self.running = False
        self.latest_data = {
            "v_raw": 0.5, "v_med": 0.5, "v_ema": 0.5,
            "rs": 7500.0, "r0": 7500.0, "ratio": 1.0, "gas_pct": 0.0
        }
        self.last_packet_time = 0.0
        self.packet_count = 0
        self.hz = 0.0
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(0.5)
            safe_print(f"[*] [GAS-UDP] Socket a la escucha en puerto UDP {self.port}...")
        except Exception as e:
            safe_print(f"[!] [GAS-UDP] Error bindeando socket: {e}")
            return

        cnt = 0
        t0 = time.time()

        while self.running:
            try:
                data, _ = sock.recvfrom(512)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    safe_print(f"[!] [GAS-UDP] Error recv: {e}")
                break

            try:
                parsed = json.loads(data.decode('utf-8'))
                with self.lock:
                    self.latest_data = parsed
                    self.last_packet_time = time.time()
                    self.packet_count += 1
                cnt += 1
            except Exception:
                pass

            now = time.time()
            if now - t0 >= 1.0:
                self.hz = cnt / (now - t0)
                cnt = 0
                t0 = now

        sock.close()


def request_calibration(host=DEFAULT_HOST):
    """Envía solicitud HTTP para recalibrar R0 al aire limpio"""
    url = f"http://{host}/calibrate"
    def _req():
        try:
            req = urllib.request.Request(url, data=b"", headers={"User-Agent": "UTEC-Viewer-RTP/7.0"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                safe_print(f"[+] Calibracion enviada. Codigo: {resp.status}")
        except Exception as e:
            safe_print(f"[!] Error enviando calibracion: {e}")
    threading.Thread(target=_req, daemon=True).start()


def get_gas_status(ratio):
    if ratio < 1.05:
        return "AIRE LIMPIO", (0, 220, 0), "Normal / Seguro"
    elif ratio < 1.30:
        return "BAJA PRESENCIA", (0, 215, 255), "Traza de hidrocarburo"
    elif ratio < 1.80:
        return "GAS MODERADO", (0, 140, 255), "Precaucion"
    elif ratio < 3.00:
        return "ALTA CONCENTRACION", (0, 69, 255), "Alerta Toxicidad"
    else:
        return "PELIGRO CRITICO", (0, 0, 255), "EVACUACION INMEDIATA"


def main():
    host = DEFAULT_HOST
    safe_print("=" * 75)
    safe_print("   VISOR RTP / UDP (V7) - VIDEO UVC Y GAS MiCS-5524 (ESP32-S3)")
    safe_print("   Tesis Mecatronica UTEC 2026 | Arquitectura RTP RFC 3550 + Pacing")
    safe_print("=" * 75)
    safe_print(f"[*] Destino ESP32-S3: {host}")
    safe_print(f"[*] Puerto Video RTP: UDP {VIDEO_RTP_PORT}")
    safe_print(f"[*] Puerto Gas: UDP {GAS_UDP_PORT}")
    safe_print("[*] Teclas de control:")
    safe_print("     [C] : Calibrar R0 en Aire Limpio (POST http://.../calibrate)")
    safe_print("     [S] : Guardar captura instantanea (PNG)")
    safe_print("     [Q] o [ESC] : Salir del visualizador")
    safe_print("=" * 75)

    # Iniciar hilos receptores
    video_rx = VideoReceiverRTP(host=host, port=VIDEO_RTP_PORT)
    video_rx.start()

    gas_rx = GasReceiverUDP(port=GAS_UDP_PORT)
    gas_rx.start()

    window_name = "UTEC 2026 - ESP32-S3 Camara UVC (RTP) & Gas (UDP)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 960, 640)

    # Gráfico histórico de gases (últimos 150 puntos)
    history_ratio = [1.0] * 150
    calib_msg_until = 0.0

    try:
        while True:
            # Obtener último fotograma decodificado
            with video_rx.lock:
                frame = video_rx.latest_frame.copy() if video_rx.latest_frame is not None else None
                fps = video_rx.fps
                kb_sec = video_rx.kb_sec
                total_frames = video_rx.total_frames
                dropped_frames = video_rx.dropped_frames
                loss_rate = video_rx.packet_loss_rate

            # Obtener última telemetría de gases
            with gas_rx.lock:
                gas = dict(gas_rx.latest_data)
                gas_hz = gas_rx.hz
                gas_fresh = (time.time() - gas_rx.last_packet_time) < 1.0

            ratio = gas.get("ratio", 1.0)
            history_ratio.append(ratio)
            if len(history_ratio) > 150:
                history_ratio.pop(0)

            # Si aún no hay video, generar cuadro de espera elegante
            if frame is None:
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:] = (20, 20, 25)
                cv2.putText(frame, "ESPERANDO STREAM RTP / UDP...", (120, 220),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 255), 2)
                cv2.putText(frame, f"Escuchando paquetes RTP en puerto UDP {VIDEO_RTP_PORT}", (130, 260),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (160, 160, 160), 1)
                cv2.putText(frame, f"Verifica conexion Wi-Fi a SSID 'ESP32S3-CAM'", (140, 290),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (120, 180, 120), 1)

            h, w = frame.shape[:2]

            # -------------------------------------------------------------
            # Overlay Superior: Banner de Estado de Red y Video RTP
            # -------------------------------------------------------------
            cv2.rectangle(frame, (0, 0), (w, 55), (15, 15, 18), -1)
            cv2.line(frame, (0, 55), (w, 55), (50, 50, 60), 1)

            cv2.putText(frame, f"RTP UDP: {fps:.1f} FPS", (15, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 180), 2)
            cv2.putText(frame, f"Flujo: {kb_sec:.1f} KB/s", (15, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            loss_color = (0, 220, 0) if loss_rate < 1.0 else ((0, 165, 255) if loss_rate < 5.0 else (0, 0, 255))
            cv2.putText(frame, f"Perdida RTP: {loss_rate:.1f}%", (200, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, loss_color, 2)
            cv2.putText(frame, f"Frames OK: {total_frames} | Drops: {dropped_frames}", (200, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150, 150, 150), 1)

            status_text, status_color, status_desc = get_gas_status(ratio)
            cv2.putText(frame, f"GAS: {status_text}", (w - 280, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)
            cv2.putText(frame, f"{status_desc} | UDP {gas_hz:.0f} Hz", (w - 280, 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)

            # -------------------------------------------------------------
            # Overlay Inferior: Telemetría de Gases y Gráfico
            # -------------------------------------------------------------
            panel_h = 100
            cv2.rectangle(frame, (0, h - panel_h), (w, h), (15, 15, 18), -1)
            cv2.line(frame, (0, h - panel_h), (w, h - panel_h), (50, 50, 60), 1)

            v_ema = gas.get("v_ema", 0.5)
            r0 = gas.get("r0", 7500.0)
            rs = gas.get("rs", 7500.0)
            gas_pct = gas.get("gas_pct", 0.0)

            # Barra horizontal de intensidad de gas (%)
            bar_x = 20
            bar_y = h - 75
            bar_w = 260
            bar_h = 18
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (40, 40, 45), -1)
            fill_w = int(bar_w * (min(max(gas_pct, 0.0), 100.0) / 100.0))
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), status_color, -1)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (100, 100, 100), 1)
            cv2.putText(frame, f"Intensidad: {gas_pct:.1f}%", (bar_x, bar_y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)

            # Datos numéricos
            cv2.putText(frame, f"V_ema: {v_ema:.3f} V | R0: {r0:.0f} Ohm | Rs: {rs:.0f} Ohm",
                        (bar_x, h - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (190, 190, 190), 1)
            cv2.putText(frame, f"Ratio R0/Rs: {ratio:.3f}x",
                        (bar_x, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

            # Mini-gráfico de tendencia
            gw = 220
            gh = 65
            gx = w - gw - 20
            gy = h - panel_h + 15
            cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), (25, 25, 30), -1)
            cv2.rectangle(frame, (gx, gy), (gx + gw, gy + gh), (70, 70, 75), 1)

            max_val = max(max(history_ratio), 2.0)
            pts = []
            for i, val in enumerate(history_ratio[-gw:]):
                px = gx + i
                norm = min((val - 0.8) / (max_val - 0.8), 1.0)
                py = int((gy + gh) - (norm * (gh - 4)))
                pts.append((px, py))

            if len(pts) > 1:
                cv2.polylines(frame, [np.array(pts)], False, status_color, 2)

            cv2.putText(frame, f"Tendencia (Max {max_val:.2f}x)", (gx + 5, gy + 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (150, 150, 150), 1)

            # Notificación de calibración si fue solicitada
            if time.time() < calib_msg_until:
                cv2.putText(frame, "RECALIBRANDO R0 EN AIRE LIMPIO...", (w // 2 - 160, h // 2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q'), ord('Q')):
                break
            elif key in (ord('c'), ord('C')):
                safe_print("[*] Solicitando recalibracion de R0 al ESP32...")
                request_calibration(host)
                calib_msg_until = time.time() + 2.5
            elif key in (ord('s'), ord('S')):
                fn = f"captura_v7_rtp_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(fn, frame)
                safe_print(f"[+] Fotograma guardado: {fn}")

    finally:
        video_rx.stop()
        gas_rx.stop()
        cv2.destroyAllWindows()
        safe_print("[*] Visor finalizado.")


if __name__ == "__main__":
    main()
