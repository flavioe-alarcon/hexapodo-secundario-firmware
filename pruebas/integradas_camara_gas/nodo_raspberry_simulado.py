"""
========================================================================================
NODO SIMULADOR DE RASPBERRY PI 5 - HEXAPODO PRIMARIO (TESIS UTEC 2026)
Arquitectura Hibrida: Video UVC por TCP (Puerto 81) + Gases por UDP (Puerto 5005)
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Caracteristicas Principales:
  1. Hilo Receptor de Video TCP: Parser por Content-Length con tolerancia total a
     conexion/desconexion fisica (Hot-Plug) mediante cuadro de espera (Standby Frame).
  2. Hilo Receptor de Gases UDP: Recepcion continua a 20 Hz en puerto 5005.
  3. Supervisor de Seguridad Minera: Evaluacion de riesgo segun D.S. N° 024-2016-EM.
  4. Caja Negra de Mision: Registro continuo en 'registro_mision_hexapodo.csv'.
  5. Panel de Control Tactico de la Estacion Terrena / Raspberry Pi 5.
========================================================================================
"""

import sys
import os
import time
import json
import csv
import socket
import threading
import datetime
import urllib.request
import cv2
import numpy as np

# Parametros de Comunicacion
ESP32_HOST = "192.168.4.1"
VIDEO_URL = f"http://{ESP32_HOST}:81/stream"
CALIB_URL = f"http://{ESP32_HOST}:80/calibrate"
GAS_UDP_PORT = 5005
LOG_FILENAME = "registro_mision_hexapodo.csv"

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


class VideoStreamReceiver:
    """Hilo receptor de video MJPEG sobre TCP con parser robusto y tolerancia Hot-Plug"""
    def __init__(self, stream_url=VIDEO_URL):
        self.stream_url = stream_url
        self.running = False
        self.connected = False
        self.latest_frame = None
        self.fps = 0.0
        self.kb_sec = 0.0
        self.total_frames = 0
        self.is_standby = True
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        bytes_buffer = bytearray()
        fps_counter = 0
        fps_timer = time.time()
        bytes_this_sec = 0

        while self.running:
            try:
                safe_print(f"[*] [RPi-VIDEO-TCP] Conectando a stream UVC en {self.stream_url}...")
                req = urllib.request.Request(self.stream_url, headers={'User-Agent': 'RPi5-ROS2-Node/1.0'})
                stream = urllib.request.urlopen(req, timeout=4.0)
                self.connected = True
                safe_print("[OK] [RPi-VIDEO-TCP] Stream MJPEG conectado exitosamente (TCP Puerto 81).")

                while self.running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break

                    bytes_this_sec += len(chunk)
                    bytes_buffer.extend(chunk)

                    # Parser robusto por Content-Length anunciado en cabecera HTTP
                    while True:
                        cl_pos = bytes_buffer.find(b'Content-Length: ')
                        if cl_pos != -1:
                            hdr_end = bytes_buffer.find(b'\r\n\r\n', cl_pos)
                            if hdr_end != -1:
                                cl_str = bytes_buffer[cl_pos + 16 : hdr_end].decode('ascii', errors='ignore').strip()
                                try:
                                    frame_len = int(cl_str)
                                    start_jpeg = hdr_end + 4
                                    if len(bytes_buffer) >= start_jpeg + frame_len:
                                        jpg = bytes_buffer[start_jpeg : start_jpeg + frame_len]
                                        bytes_buffer = bytes_buffer[start_jpeg + frame_len :]

                                        img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                                        if img is not None:
                                            # Cuadro Standby del ESP32 mide 16x16 px
                                            is_std = bool(img.shape[0] < 30)
                                            with self.lock:
                                                self.latest_frame = img
                                                self.is_standby = is_std
                                                if not is_std:
                                                    self.total_frames += 1

                                            if not is_std:
                                                fps_counter += 1
                                                now = time.time()
                                                if now - fps_timer >= 1.0:
                                                    elapsed = now - fps_timer
                                                    self.fps = fps_counter / elapsed
                                                    self.kb_sec = (bytes_this_sec / 1024.0) / elapsed
                                                    fps_counter = 0
                                                    bytes_this_sec = 0
                                                    fps_timer = now
                                            else:
                                                self.fps = 0.0
                                                self.kb_sec = 0.0
                                        continue
                                except ValueError:
                                    bytes_buffer = bytes_buffer[hdr_end + 4 :]
                                    continue

                        # Fallback de seguridad por delimitadores SOI (0xFFD8) y EOI (0xFFD9)
                        a = bytes_buffer.find(b'\xff\xd8')
                        b = bytes_buffer.find(b'\xff\xd9', a + 2) if a != -1 else -1
                        if a != -1 and b != -1 and b > a:
                            if b + 4 <= len(bytes_buffer) and (bytes_buffer[b+2:b+4] == b'\r\n' or b'--' in bytes_buffer[b+2:b+6]):
                                jpg = bytes_buffer[a : b + 2]
                                bytes_buffer = bytes_buffer[b + 2 :]
                                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                                if img is not None:
                                    is_std = bool(img.shape[0] < 30)
                                    with self.lock:
                                        self.latest_frame = img
                                        self.is_standby = is_std
                                continue
                        break

            except Exception as e:
                self.connected = False
                safe_print(f"[!] [RPi-VIDEO-TCP] Esperando stream del ESP32-S3... ({e})")
                time.sleep(1.5)


class GasClientUDP:
    """Hilo receptor de telemetria de gases por UDP en tiempo real a 20 Hz"""
    def __init__(self, port=GAS_UDP_PORT):
        self.port = port
        self.running = False
        self.connected = False
        self.latest_data = {
            "v_raw": 0.5, "v_med": 0.5, "v_ema": 0.5,
            "rs": 7500.0, "r0": 7500.0, "ratio": 1.0, "gas_pct": 0.0
        }
        self.history_ratio = [1.0] * 120
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
            sock.settimeout(1.0)
            safe_print(f"[OK] [RPi-GAS-UDP] Socket UDP escuchando activamente en 0.0.0.0:{self.port}")
        except Exception as e:
            safe_print(f"[!] [RPi-GAS-UDP] Error bindeando puerto UDP {self.port}: {e}")
            return

        cnt = 0
        t0 = time.time()

        while self.running:
            try:
                raw_bytes, _ = sock.recvfrom(1024)
                if raw_bytes:
                    payload = raw_bytes.decode('utf-8', errors='replace')
                    d = json.loads(payload)
                    now = time.time()

                    with self.lock:
                        self.latest_data = d
                        self.connected = True
                        self.last_packet_time = now
                        self.packet_count += 1
                        ratio = d.get("ratio", 1.0)
                        self.history_ratio.append(ratio)
                        if len(self.history_ratio) > 120:
                            self.history_ratio.pop(0)

                    cnt += 1
            except socket.timeout:
                with self.lock:
                    self.connected = False
            except Exception:
                pass

            now = time.time()
            if now - t0 >= 1.0:
                self.hz = cnt / (now - t0)
                cnt = 0
                t0 = now

        sock.close()


class MissionDataLogger:
    """Hilo de Caja Negra: Registra telemetria continua en archivo CSV"""
    def __init__(self, filename=LOG_FILENAME):
        self.filename = filename
        self.running = False
        self.records_written = 0
        self.thread = None
        self._init_csv()

    def _init_csv(self):
        if not os.path.exists(self.filename):
            with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_iso", "unix_time",
                    "v_raw", "v_med", "v_ema",
                    "rs_ohms", "r0_ohms",
                    "ratio_r0_rs", "gas_intensity_pct",
                    "estado_seguridad_minera"
                ])
            safe_print(f"[+] [RPi-LOGGER] Archivo de mision inicializado: {self.filename}")

    def start(self, gas_client):
        self.gas_client = gas_client
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        while self.running:
            time.sleep(0.2) # Muestreo a 5 Hz
            with self.gas_client.lock:
                gas = dict(self.gas_client.latest_data)
                last_t = self.gas_client.last_packet_time
                g_conn = self.gas_client.connected

            if not g_conn or (time.time() - last_t > 2.0):
                continue

            ratio = gas.get("ratio", 1.0)
            status_text, _, _ = evaluate_mining_safety(ratio)

            now_iso = datetime.datetime.now().isoformat()
            now_unix = time.time()

            try:
                with open(self.filename, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        now_iso, f"{now_unix:.3f}",
                        f"{gas.get('v_raw', 0):.3f}",
                        f"{gas.get('v_med', 0):.3f}",
                        f"{gas.get('v_ema', 0):.3f}",
                        f"{gas.get('rs', 0):.1f}",
                        f"{gas.get('r0', 0):.1f}",
                        f"{ratio:.3f}",
                        f"{gas.get('gas_pct', 0):.1f}",
                        status_text
                    ])
                self.records_written += 1
            except Exception:
                pass


def evaluate_mining_safety(ratio):
    """
    Evaluacion de seguridad atmosferica segun normativa minera D.S. N° 024-2016-EM.
    """
    if ratio < 1.05:
        return "AIRE LIMPIO", (34, 197, 94), "Atmosfera Segura (Operacion Normal)"
    elif ratio < 1.30:
        return "BAJA PRESENCIA", (245, 158, 11), "Traza detectada (Monitoreo Preventivo)"
    elif ratio < 1.80:
        return "GAS MODERADO", (14, 200, 240), "Precaucion (Ventilacion Requerida)"
    elif ratio < 3.00:
        return "ALTA CONCENTRACION", (11, 158, 245), "Peligro Toxicidad (Alerta Nivel 1)"
    else:
        return "EVACUACION CRITICA", (68, 68, 239), "PELIGRO LETAL (Repliegue Inmediato)"


def send_calibration_request(calib_url=CALIB_URL):
    def _call():
        try:
            req = urllib.request.Request(calib_url, data=b"", headers={'User-Agent': 'RPi5-Commander/1.0'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                safe_print(f"[+] [RPi-CONTROL] Calibracion R0 aceptada por ESP32-S3 (HTTP {resp.status}).")
        except Exception as e:
            safe_print(f"[!] [RPi-CONTROL] Error al calibrar: {e}")
    threading.Thread(target=_call, daemon=True).start()


def main():
    safe_print("=" * 80)
    safe_print("   SISTEMA DE INSPECCION ROBOTICA COOPERATIVA EN MINERIA SUBTERRANEA")
    safe_print("   Nodo Simulador Raspberry Pi 5 / Hexapodo Primario - Tesis UTEC 2026")
    safe_print("=" * 80)
    safe_print(f"[*] Destino Hexapodo Secundario (ESP32-S3): {ESP32_HOST}")
    safe_print(f"[*] Stream Video (TCP): {VIDEO_URL}")
    safe_print(f"[*] Telemetria Gases (UDP): Puerto {GAS_UDP_PORT}")
    safe_print(f"[*] Registro de Caja Negra: {LOG_FILENAME}")
    safe_print("[*] Controles:")
    safe_print("     [C] : Calibrar R0 en Aire Limpio (HTTP POST /calibrate)")
    safe_print("     [S] : Guardar captura instantanea (PNG)")
    safe_print("     [Q] o [ESC] : Detener mision y guardar registro")
    safe_print("=" * 80)

    # Iniciar hilos receptores
    video_rx = VideoStreamReceiver(stream_url=VIDEO_URL)
    video_rx.start()

    gas_rx = GasClientUDP(port=GAS_UDP_PORT)
    gas_rx.start()

    logger = MissionDataLogger(filename=LOG_FILENAME)
    logger.start(gas_rx)

    window_title = "ESTACION TERRENA RASPBERRY PI 5 - HEXAPODO PRIMARIO (UTEC 2026)"
    cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_title, 1100, 680)

    canvas = np.zeros((680, 1100, 3), dtype=np.uint8)
    mission_start_time = time.time()
    calib_notice_until = 0.0

    try:
        while True:
            canvas.fill(20)
            h_total, w_total = canvas.shape[:2]

            # -------------------------------------------------------------
            # 1. ZONA IZQUIERDA: Video UVC de la Camara (640 x 480)
            # -------------------------------------------------------------
            vid_x, vid_y = 15, 65
            vid_w, vid_h = 640, 480

            with video_rx.lock:
                frame = video_rx.latest_frame
                fps = video_rx.fps
                kb_sec = video_rx.kb_sec
                v_conn = video_rx.connected
                frames_cnt = video_rx.total_frames
                is_standby = video_rx.is_standby

            if frame is not None and v_conn and not is_standby and frame.shape[0] >= 30:
                frame_resized = cv2.resize(frame, (vid_w, vid_h))
                canvas[vid_y:vid_y+vid_h, vid_x:vid_x+vid_w] = frame_resized

                cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + 32), (10, 10, 10), -1)
                info_txt = f"UVC TCP {frame.shape[1]}x{frame.shape[0]} | {fps:.1f} FPS | {kb_sec:.1f} KB/s | #{frames_cnt}"
                cv2.putText(canvas, info_txt, (vid_x + 10, vid_y + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (56, 189, 248), 2, cv2.LINE_AA)
            else:
                cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (20, 27, 38), -1)
                cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (51, 65, 85), 2)
                cv2.putText(canvas, "[ CAMARA UVC EN ESPERA / RECONEXION ]", (vid_x + 70, vid_y + 200),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.72, (245, 158, 11), 2, cv2.LINE_AA)
                cv2.putText(canvas, "El ESP32-S3 y la telemetria de gas siguen 100% activos", (vid_x + 75, vid_y + 245),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (34, 197, 94), 1, cv2.LINE_AA)
                cv2.putText(canvas, "Conecta o reconecta la camara al puerto USB nativo del ESP32", (vid_x + 55, vid_y + 285),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (148, 163, 184), 1, cv2.LINE_AA)
                cv2.putText(canvas, "La imagen se reanudara instantaneamente sin reiniciar nada", (vid_x + 65, vid_y + 315),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.46, (56, 189, 248), 1, cv2.LINE_AA)

            # -------------------------------------------------------------
            # 2. ZONA DERECHA: Telemetria de Gases MiCS-5524 (UDP)
            # -------------------------------------------------------------
            px = 675
            with gas_rx.lock:
                g = dict(gas_rx.latest_data)
                g_conn = gas_rx.connected
                g_hz = gas_rx.hz
                hist_ratio = list(gas_rx.history_ratio)

            gas_pct = g.get("gas_pct", 0.0)
            v_ema = g.get("v_ema", 0.0)
            v_raw = g.get("v_raw", 0.0)
            v_med = g.get("v_med", 0.0)
            rs = g.get("rs", 0.0)
            r0 = g.get("r0", 7500.0)
            ratio = g.get("ratio", 1.0)
            status_text, status_col, status_desc = evaluate_mining_safety(ratio)

            # Encabezado Panel Gas
            cv2.rectangle(canvas, (px, 65), (w_total - 15, 120), (30, 41, 59), -1)
            cv2.rectangle(canvas, (px, 65), (w_total - 15, 120), (51, 65, 85), 1)
            cv2.putText(canvas, "SENSOR DE GASES (MiCS-5524)", (px + 12, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (56, 189, 248), 2, cv2.LINE_AA)

            status_str = f"EN LINEA (UDP {g_hz:.0f} Hz) | RPi Rcv OK" if g_conn else "DESCONECTADO (Sin UDP)"
            cv2.putText(canvas, status_str, (px + 12, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (34, 197, 94) if g_conn else (68, 68, 239), 2, cv2.LINE_AA)

            # Tarjeta 1: Intensidad de Gas y Estado Minero
            cy = 130
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 90), (15, 23, 42), -1)
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 90), (51, 65, 85), 1)

            cv2.putText(canvas, "NIVEL DE GAS:", (px + 15, cy + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (148, 163, 184), 1, cv2.LINE_AA)
            cv2.putText(canvas, f"{gas_pct:.1f} %", (px + 140, cy + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.85, status_col, 2, cv2.LINE_AA)
            cv2.putText(canvas, f"[{status_text}]", (px + 265, cy + 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, status_col, 1, cv2.LINE_AA)

            # Barra de intensidad
            bar_x = px + 15
            bar_y = cy + 48
            bar_w = (w_total - 15) - bar_x - 15
            bar_h = 24
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (30, 41, 59), -1)
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (71, 85, 105), 1)
            fill_w = int((min(max(gas_pct, 0.0), 100.0) / 100.0) * bar_w)
            if fill_w > 0:
                cv2.rectangle(canvas, (bar_x + 1, bar_y + 1), (bar_x + fill_w - 1, bar_y + bar_h - 1), status_col, -1)

            # Tarjeta 2: Metricas Fisicas y Ratio
            cy = 230
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 105), (15, 23, 42), -1)
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 105), (51, 65, 85), 1)

            cv2.putText(canvas, f"Voltaje EMA : {v_ema:.3f} V", (px + 15, cy + 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.58, (240, 240, 240), 2, cv2.LINE_AA)
            cv2.putText(canvas, f"Raw: {v_raw:.3f}V | Mediana: {v_med:.3f}V", (px + 15, cy + 48),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.46, (148, 163, 184), 1, cv2.LINE_AA)
            cv2.putText(canvas, f"Rs: {rs/1000.0:.2f} kOhm | R0: {r0/1000.0:.2f} kOhm", (px + 15, cy + 74),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (56, 189, 248), 1, cv2.LINE_AA)
            cv2.putText(canvas, f"Ratio R0/Rs: {ratio:.3f}x (Umbral: 1.80x)", (px + 15, cy + 96),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 215, 0), 2, cv2.LINE_AA)

            # Tarjeta 3: Osciloscopio Historico Ratio
            cy = 345
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 200), (10, 15, 25), -1)
            cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 200), (51, 65, 85), 1)
            cv2.putText(canvas, "HISTORICO RATIO R0 / Rs (Deteccion Gases)", (px + 15, cy + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.48, (148, 163, 184), 1, cv2.LINE_AA)

            plot_x = px + 40
            plot_y = cy + 32
            plot_w = (w_total - 15) - plot_x - 15
            plot_h = 150

            max_plot = max(max(hist_ratio), 2.5)
            for r_ref in [1.0, 1.5, 2.0, 2.5]:
                if r_ref <= max_plot:
                    y_line = int(plot_y + plot_h - ((r_ref - 0.8) / (max_plot - 0.8)) * plot_h)
                    cv2.line(canvas, (plot_x, y_line), (plot_x + plot_w, y_line), (35, 45, 60), 1)
                    cv2.putText(canvas, f"{r_ref:.1f}x", (px + 5, y_line + 4),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 116, 139), 1)

            if len(hist_ratio) > 1:
                pts = []
                step_x = plot_w / 120.0
                for i, val in enumerate(hist_ratio):
                    norm = min(max((val - 0.8) / (max_plot - 0.8), 0.0), 1.0)
                    px_pt = int(plot_x + i * step_x)
                    py_pt = int(plot_y + plot_h - norm * plot_h)
                    pts.append((px_pt, py_pt))
                for i in range(len(pts) - 1):
                    cv2.line(canvas, pts[i], pts[i+1], status_col, 2)

            # -------------------------------------------------------------
            # 3. BARRA SUPERIOR (HEADER) E INFERIOR (FOOTER)
            # -------------------------------------------------------------
            cv2.rectangle(canvas, (0, 0), (w_total, 50), (15, 23, 42), -1)
            cv2.line(canvas, (0, 50), (w_total, 50), (56, 189, 248), 1)

            mission_elapsed = int(time.time() - mission_start_time)
            mins, secs = divmod(mission_elapsed, 60)
            cv2.putText(canvas, "HEXAPODO PRIMARIO (RPi 5) · ESTACION DE MONITOREO TACTICO", (20, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(canvas, f"MISION: {mins:02d}:{secs:02d} | CAJA NEGRA: {logger.records_written} reg",
                        (w_total - 380, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (34, 197, 94), 2, cv2.LINE_AA)

            cv2.rectangle(canvas, (0, h_total - 42), (w_total, h_total), (15, 23, 42), -1)
            cv2.line(canvas, (0, h_total - 42), (w_total, h_total - 42), (51, 65, 85), 1)

            footer_txt = "[C] Calibrar R0 (Aire Limpio)   |   [S] Captura Pantalla   |   [Q] Salir de Mision"
            cv2.putText(canvas, footer_txt, (25, h_total - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (203, 213, 225), 1, cv2.LINE_AA)

            if time.time() < calib_notice_until:
                cv2.putText(canvas, ">> SOLICITUD ENVIADA: CALIBRANDO R0 EN AIRE LIMPIO... <<",
                            (px - 100, h_total - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (34, 197, 94), 2, cv2.LINE_AA)

            cv2.imshow(window_title, canvas)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord('q'), ord('Q')):
                break
            elif key in (ord('c'), ord('C')):
                safe_print("[*] [RPi-CONTROL] Enviando orden de calibracion R0 al hexapodo secundario...")
                send_calibration_request(CALIB_URL)
                calib_notice_until = time.time() + 2.5
            elif key in (ord('s'), ord('S')):
                snap_name = f"captura_mision_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(snap_name, canvas)
                safe_print(f"[+] [RPi-CONTROL] Captura de mision guardada: {snap_name}")

    finally:
        video_rx.stop()
        gas_rx.stop()
        logger.stop()
        cv2.destroyAllWindows()
        safe_print("=" * 80)
        safe_print(f"[*] Mision finalizada. Registros guardados en '{LOG_FILENAME}' ({logger.records_written} filas).")
        safe_print("=" * 80)


if __name__ == "__main__":
    main()
