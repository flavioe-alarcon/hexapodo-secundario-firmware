"""
========================================================================================
Visor UDP PURO de Video UVC y Telemetría de Gases MiCS-5524 para ESP32-S3 (OpenCV)
Tesis de Ingeniería Mecatrónica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcón, Alfredo Erazo
Asesor: Dante Inga Narváez

Arquitectura UDP PURO (Simulador de Recepción Raspberry Pi 5 / ROS 2):
  - Video UVC (UDP Datagramas Fragmentados en Puerto 5006)
  - Telemetría de Gas (UDP Datagramas JSON a 20 Hz en Puerto 5005)
  - Calibración R0 (HTTP GET a http://192.168.4.1/calibrate)
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
VIDEO_UDP_PORT = 5006
MAGIC_HEADER = 0xAA55

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


class VideoReceiverUDP:
    """Hilo receptor y reensamblador de fragmentos UDP de video JPEG (Puerto 5006)"""
    def __init__(self, port=VIDEO_UDP_PORT):
        self.port = port
        self.running = False
        self.latest_frame = None
        self.fps = 0.0
        self.kb_sec = 0.0
        self.total_frames = 0
        self.dropped_frames = 0
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
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024 * 1024) # 1 MB buffer
        except Exception:
            pass

        try:
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(0.5)
            safe_print(f"[*] [VIDEO-UDP] Socket a la escucha en puerto UDP {self.port}...")
        except Exception as e:
            safe_print(f"[!] [VIDEO-UDP] Error bindeando socket: {e}")
            return

        frame_buffers = {}       # {frame_id: {chunk_id: bytes}}
        frame_totals = {}        # {frame_id: total_chunks}
        frame_timestamps = {}    # {frame_id: time_created}

        fps_counter = 0
        fps_timer = time.time()
        bytes_this_sec = 0
        last_completed_frame_id = -1

        while self.running:
            try:
                data, _ = sock.recvfrom(2048)
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    safe_print(f"[!] [VIDEO-UDP] Error recv: {e}")
                break

            if len(data) < 10:
                continue

            bytes_this_sec += len(data)

            # Desempaquetar encabezado: [magic (2B), frame_id (2B), chunk_id (2B), total_chunks (2B), payload_len (2B)]
            magic, frame_id, chunk_id, total_chunks, payload_len = struct.unpack('<HHHHH', data[:10])

            if magic != MAGIC_HEADER:
                continue

            if frame_id <= last_completed_frame_id and (last_completed_frame_id - frame_id) < 500:
                # Cuadro viejo/descartado
                continue

            payload = data[10 : 10 + payload_len]

            now = time.time()
            if frame_id not in frame_buffers:
                frame_buffers[frame_id] = {}
                frame_totals[frame_id] = total_chunks
                frame_timestamps[frame_id] = now

            frame_buffers[frame_id][chunk_id] = payload

            # ¿Se recibieron todos los fragmentos de este frame?
            if len(frame_buffers[frame_id]) == total_chunks:
                # Reensamblar en orden
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

                # Limpiar buffers de cuadros anteriores
                keys_to_del = [f for f in list(frame_buffers.keys()) if f <= frame_id]
                for k in keys_to_del:
                    frame_buffers.pop(k, None)
                    frame_totals.pop(k, None)
                    frame_timestamps.pop(k, None)

            # Limpieza periódica de cuadros huérfanos (perdidos en Wi-Fi hace más de 0.4s)
            if len(frame_buffers) > 10:
                expired = [f for f, t in frame_timestamps.items() if now - t > 0.4]
                for f in expired:
                    frame_buffers.pop(f, None)
                    frame_totals.pop(f, None)
                    frame_timestamps.pop(f, None)
                    self.dropped_frames += 1

            # Cálculo de métricas por segundo
            if now - fps_timer >= 1.0:
                with self.lock:
                    self.fps = fps_counter / (now - fps_timer)
                    self.kb_sec = (bytes_this_sec / 1024.0) / (now - fps_timer)
                fps_counter = 0
                bytes_this_sec = 0
                fps_timer = now

        sock.close()


class GasTelemetryReceiverUDP:
    """Hilo receptor de telemetría de gases por UDP Broadcast (Puerto 5005)"""
    def __init__(self, port=GAS_UDP_PORT):
        self.port = port
        self.running = False
        self.last_packet_time = 0.0
        self.connected = False
        self.records_to_export = []
        self.history_v = []
        self.max_history = 120

        # Últimos valores recibidos
        self.v_raw = 0.0
        self.v_med = 0.0
        self.v_ema = 0.0
        self.rs = 0.0
        self.r0 = 7500.0
        self.ratio = 1.0
        self.gas_pct = 0.0
        self.calibrating = False
        self.seq = 0

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

        while self.running:
            try:
                data, _ = sock.recvfrom(1024)
            except socket.timeout:
                # Si pasa más de 2 s sin recibir paquetes, marcar desconectado
                if time.time() - self.last_packet_time > 2.0:
                    with self.lock:
                        self.connected = False
                continue
            except Exception as e:
                if self.running:
                    safe_print(f"[!] [GAS-UDP] Error en recv: {e}")
                break

            now = time.time()
            try:
                payload = json.loads(data.decode('utf-8'))
                with self.lock:
                    self.v_raw = float(payload.get("v_raw", 0.0))
                    self.v_med = float(payload.get("v_med", 0.0))
                    self.v_ema = float(payload.get("v_ema", 0.0))
                    self.rs = float(payload.get("rs", 0.0))
                    self.r0 = float(payload.get("r0", 7500.0))
                    self.ratio = float(payload.get("ratio", 1.0))
                    self.gas_pct = float(payload.get("gas_pct", 0.0))
                    self.calibrating = bool(payload.get("calibrating", False))
                    self.seq = int(payload.get("seq", 0))

                    self.last_packet_time = now
                    self.connected = True

                    self.history_v.append(self.v_ema)
                    if len(self.history_v) > self.max_history:
                        self.history_v.pop(0)

                    self.records_to_export.append({
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "v_raw": self.v_raw,
                        "v_med": self.v_med,
                        "v_ema": self.v_ema,
                        "rs": self.rs,
                        "r0": self.r0,
                        "ratio": self.ratio,
                        "gas_pct": self.gas_pct,
                        "calibrating": self.calibrating,
                    })
            except Exception:
                pass

        sock.close()


def send_calibration_request(host=DEFAULT_HOST):
    url = f"http://{host}/calibrate"
    safe_print(f"[*] Enviando solicitud de calibración a {url}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ESP32Visor-Python'})
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            if resp.status == 200:
                safe_print("[+] Solicitud de calibración ACEPTADA por el ESP32.")
            else:
                safe_print(f"[!] Respuesta inesperada: HTTP {resp.status}")
    except Exception as e:
        safe_print(f"[!] Error enviando calibración: {e}")


def export_csv(records, filename_prefix="telemetria_udp_gas"):
    if not records:
        safe_print("[!] No hay datos para exportar.")
        return
    fname = f"{filename_prefix}_{int(time.time())}.csv"
    try:
        with open(fname, "w", encoding="utf-8") as f:
            f.write("timestamp,v_raw,v_med,v_ema,rs_ohm,r0_ohm,ratio_r0_rs,gas_pct,calibrating\n")
            for r in records:
                f.write(f"{r['timestamp']},{r['v_raw']:.3f},{r['v_med']:.3f},{r['v_ema']:.3f},"
                        f"{r['rs']:.1f},{r['r0']:.1f},{r['ratio']:.3f},{r['gas_pct']:.1f},{r['calibrating']}\n")
        safe_print(f"[+] Archivo CSV exportado con éxito: {fname} ({len(records)} registros)")
    except Exception as e:
        safe_print(f"[!] Error al exportar CSV: {e}")


def draw_hud(canvas, video_rx, gas_rx, last_calib_time):
    h, w, _ = canvas.shape
    font = cv2.FONT_HERSHEY_SIMPLEX

    # Encabezado Superior
    cv2.rectangle(canvas, (0, 0), (w, 42), (20, 24, 33), -1)
    cv2.putText(canvas, "ESP32-S3 · SUBSISTEMA INTEGRADO: VISION UDP (5006) & GAS UDP (5005)",
                (14, 28), font, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.line(canvas, (0, 42), (w, 42), (40, 160, 220), 2)

    # Panel Derecho: Telemetría de Gases
    panel_x = int(w * 0.60)
    panel_w = w - panel_x
    cv2.rectangle(canvas, (panel_x, 43), (w, h - 35), (28, 20, 18), -1)
    cv2.line(canvas, (panel_x, 43), (panel_x, h - 35), (50, 40, 35), 2)

    # Obtener estado de gas
    with gas_rx.lock:
        conn = gas_rx.connected
        v_raw = gas_rx.v_raw
        v_med = gas_rx.v_med
        v_ema = gas_rx.v_ema
        rs = gas_rx.rs
        r0 = gas_rx.r0
        ratio = gas_rx.ratio
        gas_pct = gas_rx.gas_pct
        calibrating = gas_rx.calibrating
        hist_v = list(gas_rx.history_v)

    # 1. Título subsistema de gases
    cv2.putText(canvas, "SENSOR DE GASES (MiCS-5524)", (panel_x + 14, 72), font, 0.58, (80, 180, 255), 2)
    if not conn:
        cv2.putText(canvas, "ESPERANDO UDP (5005)...", (panel_x + 14, 94), font, 0.42, (100, 100, 255), 1)
    elif calibrating:
        cv2.putText(canvas, "CALIBRANDO R0 EN AIRE LIMPIO...", (panel_x + 14, 94), font, 0.42, (0, 220, 255), 1)
    else:
        cv2.putText(canvas, "ENLACE UDP ACTIVO (20 Hz)", (panel_x + 14, 94), font, 0.42, (100, 255, 100), 1)

    # 2. Barra de Intensidad de Gas
    box_y = 106
    cv2.rectangle(canvas, (panel_x + 10, box_y), (w - 10, box_y + 80), (38, 28, 24), -1)
    cv2.rectangle(canvas, (panel_x + 10, box_y), (w - 10, box_y + 80), (70, 50, 45), 1)

    status_str = "[AIRE LIMPIO / SEGURO]" if gas_pct < 15.0 else ("[PRECAUCION]" if gas_pct < 45.0 else "[PELIGRO / ALARMA]")
    status_col = (100, 220, 100) if gas_pct < 15.0 else ((50, 200, 255) if gas_pct < 45.0 else (80, 80, 255))
    if calibrating:
        status_str = "[CALIBRANDO R0]"
        status_col = (0, 220, 255)

    cv2.putText(canvas, f"NIVEL DE GAS:  {gas_pct:4.1f} %", (panel_x + 20, box_y + 30), font, 0.65, (255, 255, 255), 2)
    cv2.putText(canvas, status_str, (panel_x + 220, box_y + 30), font, 0.46, status_col, 1)

    # Barra gráfica
    bar_x1 = panel_x + 20
    bar_x2 = w - 20
    bar_y1 = box_y + 44
    bar_y2 = box_y + 66
    cv2.rectangle(canvas, (bar_x1, bar_y1), (bar_x2, bar_y2), (20, 15, 15), -1)
    bar_fill = int(bar_x1 + (bar_x2 - bar_x1) * min(max(gas_pct / 100.0, 0.0), 1.0))
    if bar_fill > bar_x1:
        cv2.rectangle(canvas, (bar_x1, bar_y1), (bar_fill, bar_y2), status_col, -1)

    # 3. Métricas Numéricas de Transducción
    met_y = box_y + 92
    cv2.rectangle(canvas, (panel_x + 10, met_y), (w - 10, met_y + 100), (38, 28, 24), -1)
    cv2.rectangle(canvas, (panel_x + 10, met_y), (w - 10, met_y + 100), (70, 50, 45), 1)

    cv2.putText(canvas, f"Voltaje EMA : {v_ema:.3f} V", (panel_x + 20, met_y + 26), font, 0.60, (255, 255, 255), 2)
    cv2.putText(canvas, f"Raw: {v_raw:.3f}V | Mediana: {v_med:.3f}V", (panel_x + 20, met_y + 48), font, 0.42, (180, 180, 180), 1)
    cv2.putText(canvas, f"Rs: {rs/1000.0:.2f} kOhm | R0: {r0/1000.0:.2f} kOhm", (panel_x + 20, met_y + 70), font, 0.46, (70, 200, 255), 1)
    cv2.putText(canvas, f"Ratio R0 / Rs: {ratio:.3f}", (panel_x + 20, met_y + 92), font, 0.52, (255, 200, 50), 2)

    # 4. Mini Osciloscopio de Voltaje
    osc_y = met_y + 112
    cv2.rectangle(canvas, (panel_x + 10, osc_y), (w - 10, osc_y + 110), (22, 16, 14), -1)
    cv2.rectangle(canvas, (panel_x + 10, osc_y), (w - 10, osc_y + 110), (70, 50, 45), 1)
    cv2.putText(canvas, "OSCILOSCOPIO VOLTAJE Vout (0.0 V - 3.14 V)", (panel_x + 18, osc_y + 18), font, 0.40, (180, 180, 180), 1)

    # Líneas de referencia
    for v_ref, lbl in [(0.5, "0.5V"), (1.0, "1.0V"), (2.0, "2.0V"), (3.0, "3.0V")]:
        ref_y = int(osc_y + 98 - (v_ref / 3.14) * 75)
        cv2.line(canvas, (panel_x + 18, ref_y), (w - 18, ref_y), (40, 32, 28), 1)
        cv2.putText(canvas, lbl, (panel_x + 20, ref_y - 2), font, 0.30, (120, 100, 90), 1)

    if len(hist_v) >= 2:
        pts = []
        plot_w = (w - 18) - (panel_x + 18)
        step = plot_w / float(gas_rx.max_history)
        for i, val in enumerate(hist_v):
            px = int((panel_x + 18) + i * step)
            py = int(osc_y + 98 - (min(max(val, 0.0), 3.14) / 3.14) * 75)
            pts.append((px, py))
        for i in range(len(pts) - 1):
            cv2.line(canvas, pts[i], pts[i + 1], (80, 220, 80), 2)

    # Barra Inferior: Guía de Teclado
    cv2.rectangle(canvas, (0, h - 35), (w, h), (16, 18, 24), -1)
    cv2.line(canvas, (0, h - 35), (w, h - 35), (40, 50, 60), 1)
    calib_msg = "[C] Calibrar R0 (Aire Limpio)" if time.time() - last_calib_time > 2.0 else "[!] SOLICITANDO CALIBRACION..."
    cv2.putText(canvas, f"{calib_msg}   |   [S] Captura Pantalla   |   [E] Exportar CSV   |   [Q] Salir",
                (18, h - 12), font, 0.44, (200, 210, 220), 1, cv2.LINE_AA)


def main():
    safe_print("=" * 75)
    safe_print(" VISOR UDP PURO: VIDEO UVC (5006) + GAS MiCS-5524 (5005)")
    safe_print(" Simulador de Estación Terrena / Raspberry Pi 5")
    safe_print("=" * 75)

    video_rx = VideoReceiverUDP(port=VIDEO_UDP_PORT)
    gas_rx = GasTelemetryReceiverUDP(port=GAS_UDP_PORT)

    video_rx.start()
    gas_rx.start()

    window_name = "ESP32-S3 · Hexapodo Secundario: Video UDP (5006) & Gas UDP (5005)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1180, 540)

    last_calib_time = 0.0

    try:
        while True:
            with video_rx.lock:
                frame = video_rx.latest_frame.copy() if video_rx.latest_frame is not None else None
                fps = video_rx.fps
                kb_sec = video_rx.kb_sec
                total_frames = video_rx.total_frames
                dropped = video_rx.dropped_frames

            canvas = np.zeros((540, 1180, 3), dtype=np.uint8)
            panel_x = int(1180 * 0.60)
            vid_w = panel_x - 20
            vid_h = 540 - 45 - 45

            if frame is not None:
                resized = cv2.resize(frame, (vid_w, vid_h))
                canvas[43 : 43 + vid_h, 10 : 10 + vid_w] = resized

                # Overlay de video UDP
                h_f, w_f = frame.shape[:2]
                status_txt = f"UDP {w_f}x{h_f} | {fps:.1f} FPS | {kb_sec:.1f} KB/s | Frame #{total_frames} | Perdidos: {dropped}"
                cv2.rectangle(canvas, (10, 43), (10 + vid_w, 68), (0, 0, 0), -1)
                cv2.putText(canvas, status_txt, (18, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 220, 255), 1, cv2.LINE_AA)
            else:
                # Cuadro de espera de video UDP
                cv2.rectangle(canvas, (10, 43), (10 + vid_w, 43 + vid_h), (20, 22, 28), -1)
                cv2.putText(canvas, "ESPERANDO STREAM UDP EN PUERTO 5006...",
                            (40, 43 + vid_h // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 180, 255), 2)
                cv2.putText(canvas, "Verifique conexion Wi-Fi a 'ESP32S3-CAM' (192.168.4.1)",
                            (50, 43 + vid_h // 2 + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (150, 150, 150), 1)

            draw_hud(canvas, video_rx, gas_rx, last_calib_time)
            cv2.imshow(window_name, canvas)

            key = cv2.waitKey(30) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                break
            elif key == ord('c') or key == ord('C'):
                threading.Thread(target=send_calibration_request, daemon=True).start()
                last_calib_time = time.time()
            elif key == ord('s') or key == ord('S'):
                snap_name = f"captura_udp_{int(time.time())}.png"
                cv2.imwrite(snap_name, canvas)
                safe_print(f"[+] Captura guardada como {snap_name}")
            elif key == ord('e') or key == ord('E'):
                with gas_rx.lock:
                    recs = list(gas_rx.records_to_export)
                export_csv(recs)

            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except Exception:
                pass

    finally:
        video_rx.stop()
        gas_rx.stop()
        cv2.destroyAllWindows()
        safe_print("[*] Visor UDP finalizado.")

if __name__ == "__main__":
    main()
