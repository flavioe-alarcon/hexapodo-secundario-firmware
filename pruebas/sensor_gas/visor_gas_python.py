"""
========================================================================================
Visor y Monitor de Telemetria en Tiempo Real para Sensor de Gas MiCS-5524 & ESP32-S3
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Soporta dos modos de conexion:
  1. Serial USB (UART / COM12 a 115200 baudios)
  2. Wi-Fi SoftAP HTTP (http://192.168.4.1/data)

Visualizacion de alto rendimiento con OpenCV (HUD interactivo, osciloscopio multitarea,
tarjetas de metricas, barra de nivel de gas y exportacion CSV/PNG).
========================================================================================
"""

import sys
import os
import time
import json
import threading
import datetime
import urllib.request
import serial
import serial.tools.list_ports
import cv2
import numpy as np

# Compatibilidad UTF-8 en Windows
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

def find_default_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "CH343" in p.description or "1A86:55D3" in p.hwid or "COM12" == p.device:
            return p.device
    if ports:
        return ports[-1].device
    return "COM12"

class GasTelemetryReceiver:
    """Hilo receptor de telemetria desacoplado para Serial o Wi-Fi"""
    def __init__(self, mode="serial", port_or_url="COM12", baud_rate=115200):
        self.mode = mode
        self.port_or_url = port_or_url
        self.baud_rate = baud_rate
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        
        # Ultimos datos
        self.latest_data = {
            "v_raw": 0.0,
            "v_med": 0.0,
            "v_ema": 0.0,
            "rs": 0.0,
            "r0": 10000.0,
            "ratio": 1.0,
            "timestamp": time.time()
        }
        self.history = []  # Lista de registros para exportar
        self.thread = None
        self.serial_inst = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.serial_inst:
            try:
                self.serial_inst.close()
            except Exception:
                pass

    def _worker(self):
        if self.mode == "serial":
            self._serial_loop()
        else:
            self._wifi_loop()

    def _serial_loop(self):
        while self.running:
            try:
                safe_print(f"[*] Intentando conectar a puerto {self.port_or_url} ({self.baud_rate} baud)...")
                self.serial_inst = serial.Serial(self.port_or_url, self.baud_rate, timeout=1.0)
                time.sleep(0.5)
                self.connected = True
                safe_print(f"[+] Conectado exitosamente a {self.port_or_url}.")
                
                while self.running:
                    line = self.serial_inst.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            payload = json.loads(line)
                            if "v_raw" in payload:
                                now = time.time()
                                record = {
                                    "v_raw": float(payload.get("v_raw", 0.0)),
                                    "v_med": float(payload.get("v_med", 0.0)),
                                    "v_ema": float(payload.get("v_ema", 0.0)),
                                    "rs": float(payload.get("rs", 0.0)),
                                    "r0": float(payload.get("r0", 10000.0)),
                                    "ratio": float(payload.get("ratio", 1.0)),
                                    "timestamp": now
                                }
                                with self.lock:
                                    self.latest_data = record
                                    self.history.append(record)
                                    if len(self.history) > 20000:
                                        self.history.pop(0)
                        except Exception:
                            pass
            except Exception as e:
                self.connected = False
                safe_print(f"[-] Error en conexion serial: {e}. Reintentando en 2 segundos...")
                time.sleep(2.0)
            finally:
                if self.serial_inst and self.serial_inst.is_open:
                    try:
                        self.serial_inst.close()
                    except Exception:
                        pass
                self.connected = False

    def _wifi_loop(self):
        url = self.port_or_url
        if not url.startswith("http"):
            url = f"http://{url}/data"
        safe_print(f"[*] Modo Wi-Fi activo. Consultando endpoint: {url}")
        
        while self.running:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'MiCS5524-Monitor/1.0'})
                with urllib.request.urlopen(req, timeout=1.5) as resp:
                    if resp.status == 200:
                        raw = resp.read().decode('utf-8')
                        payload = json.loads(raw)
                        self.connected = True
                        now = time.time()
                        record = {
                            "v_raw": float(payload.get("v_raw", 0.0)),
                            "v_med": float(payload.get("v_med", 0.0)),
                            "v_ema": float(payload.get("v_ema", 0.0)),
                            "rs": float(payload.get("rs", 0.0)),
                            "r0": float(payload.get("r0", 10000.0)),
                            "ratio": float(payload.get("ratio", 1.0)),
                            "timestamp": now
                        }
                        with self.lock:
                            self.latest_data = record
                            self.history.append(record)
                            if len(self.history) > 20000:
                                self.history.pop(0)
            except Exception:
                self.connected = False
            time.sleep(0.08) # Muestreo ~12 Hz

    def calibrate(self):
        """Envia comando de calibracion"""
        if self.mode == "serial" and self.serial_inst and self.serial_inst.is_open:
            try:
                self.serial_inst.write(b"CALIBRATE\n")
                safe_print("[*] Comando de calibracion enviado por Serial.")
            except Exception as e:
                safe_print(f"[-] Error enviando comando: {e}")
        elif self.mode == "wifi":
            try:
                base_url = self.port_or_url.replace("/data", "")
                if not base_url.startswith("http"):
                    base_url = f"http://{base_url}"
                cal_url = f"{base_url}/calibrate"
                urllib.request.urlopen(cal_url, timeout=2.0)
                safe_print(f"[*] Calibracion solicitada por HTTP: {cal_url}")
            except Exception as e:
                safe_print(f"[-] Error calibrando por Wi-Fi: {e}")

class GasDashboardOpenCV:
    """Dashboard HUD moderno con OpenCV"""
    def __init__(self, receiver, width=1200, height=720):
        self.rx = receiver
        self.w = width
        self.h = height
        self.buffer_size = 450 # Muestras visibles en osciloscopio
        
        # Buffers de graficacion
        self.buf_raw = []
        self.buf_med = []
        self.buf_ema = []
        self.paused = False
        
        # Paleta de colores (BGR para OpenCV)
        self.C_BG = (24, 17, 15)          # #0F1728 Slate oscuro
        self.C_CARD = (43, 30, 30)        # #1E293B Card slate
        self.C_BORDER = (75, 51, 51)      # Border suave
        self.C_TEXT = (241, 245, 248)     # Blanco suave
        self.C_TEXT_MUTED = (160, 148, 148)
        self.C_GRID = (38, 28, 28)        # Lineas de grilla
        
        # Colores de sensores
        self.C_RAW = (107, 107, 255)      # Coral / Rojo claro (BGR)
        self.C_MED = (11, 158, 245)       # Ambar / Amarillo (BGR)
        self.C_EMA = (248, 189, 56)       # Cian / Azul (BGR)
        
        self.C_SUCCESS = (100, 215, 70)   # Verde
        self.C_DANGER = (70, 70, 235)     # Rojo
        self.C_WARNING = (30, 190, 255)   # Naranja

    def run(self):
        window_title = f"Telemetria MiCS-5524 & ESP32-S3 | Tesis UTEC 2026 ({self.rx.mode.upper()})"
        cv2.namedWindow(window_title, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_title, self.w, self.h)
        
        prev_time = time.time()
        fps_counter = 0
        fps = 0.0

        while self.rx.running:
            now = time.time()
            fps_counter += 1
            if now - prev_time >= 1.0:
                fps = fps_counter / (now - prev_time)
                fps_counter = 0
                prev_time = now

            with self.rx.lock:
                cur = dict(self.rx.latest_data)

            if not self.paused and self.rx.connected:
                self.buf_raw.append(cur["v_raw"])
                self.buf_med.append(cur["v_med"])
                self.buf_ema.append(cur["v_ema"])
                if len(self.buf_raw) > self.buffer_size:
                    self.buf_raw.pop(0)
                    self.buf_med.pop(0)
                    self.buf_ema.pop(0)

            # Renderizar interfaz
            frame = self.render(cur, fps)
            cv2.imshow(window_title, frame)
            
            key = cv2.waitKey(20) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                safe_print("[*] Saliendo del visor...")
                break
            elif key == ord('c') or key == ord('C'):
                safe_print("[*] Tecla 'C' presionada: Calibrando linea base...")
                self.rx.calibrate()
            elif key == ord('r') or key == ord('R'):
                self.buf_raw.clear()
                self.buf_med.clear()
                self.buf_ema.clear()
                safe_print("[*] Grafica reseteada.")
            elif key == ord('p') or key == ord('P'):
                self.paused = not self.paused
                safe_print(f"[*] Pausa: {self.paused}")
            elif key == ord('s') or key == ord('S'):
                self.save_snapshot_and_csv(frame)

        cv2.destroyAllWindows()

    def render(self, cur, fps):
        canvas = np.full((self.h, self.w, 3), self.C_BG, dtype=np.uint8)
        
        # 1. Encabezado superior (Header)
        self.draw_header(canvas, fps)
        
        # 2. Tarjetas de metricas superiores (4 Cards)
        self.draw_metric_cards(canvas, cur)
        
        # 3. Osciloscopio / Grafica de ondas central
        self.draw_oscilloscope(canvas, cur)
        
        # 4. Barra inferior de atajos y estado
        self.draw_footer(canvas)
        
        return canvas

    def draw_header(self, img, fps):
        # Fondo sutil del header
        cv2.rectangle(img, (0, 0), (self.w, 54), (32, 22, 20), -1)
        cv2.line(img, (0, 54), (self.w, 54), self.C_BORDER, 1)
        
        # Titulo
        cv2.putText(img, "MONITOR DE GAS MiCS-5524 & ESP32-S3", (20, 34),
                    cv2.FONT_HERSHEY_DUPLEX, 0.75, self.C_TEXT, 1, cv2.LINE_AA)
        cv2.putText(img, "| Tesis UTEC 2026", (480, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, self.C_TEXT_MUTED, 1, cv2.LINE_AA)

        # Estado de conexion
        status_text = "CONECTADO" if self.rx.connected else "DESCONECTADO"
        status_color = self.C_SUCCESS if self.rx.connected else self.C_DANGER
        
        # Badge
        badge_x = self.w - 320
        cv2.rectangle(img, (badge_x, 14), (self.w - 20, 42), self.C_CARD, -1)
        cv2.rectangle(img, (badge_x, 14), (self.w - 20, 42), status_color, 1)
        cv2.circle(img, (badge_x + 16, 28), 5, status_color, -1)
        
        info_str = f"{status_text} | {self.rx.mode.upper()} | {fps:.1f} FPS"
        cv2.putText(img, info_str, (badge_x + 28, 33),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.C_TEXT, 1, cv2.LINE_AA)

    def draw_metric_cards(self, img, cur):
        y0 = 66
        card_h = 100
        margin = 16
        gap = 12
        card_w = (self.w - (margin * 2) - (gap * 3)) // 4
        
        # Calcular Ratio Inverso R0 / Rs (proporcional ascendente)
        r0_val = cur.get('r0', 10000.0)
        rs_val = max(1.0, cur.get('rs', 10000.0))
        inv_ratio = r0_val / rs_val

        # Datos para cada card
        cards = [
            {
                "title": "VOLTAJE FILTRADO (EMA)",
                "val": f"{cur['v_ema']:.3f} V",
                "sub": f"Raw: {cur['v_raw']:.3f} V | Med: {cur['v_med']:.3f} V",
                "val_color": self.C_EMA
            },
            {
                "title": "RESISTENCIA SENSOR Rs",
                "val": f"{(cur['rs'] / 1000.0):.2f} kOhm",
                "sub": f"RL integrada: 820 Ohm",
                "val_color": (255, 180, 100)
            },
            {
                "title": "LINEA BASE R0 (AIRE LIMPIO)",
                "val": f"{(cur['r0'] / 1000.0):.2f} kOhm",
                "sub": "Presiona [C] para calibrar",
                "val_color": self.C_SUCCESS
            },
            {
                "title": "PROPORCION R0 / Rs (ASCENDENTE)",
                "val": f"{inv_ratio:.3f}",
                "sub": "Limpio: 1.00 | Sube con gas",
                "val_color": self.C_WARNING,
                "is_gauge": True,
                "ratio": cur['ratio'],
                "inv_ratio": inv_ratio
            }
        ]

        for i, c in enumerate(cards):
            x = margin + i * (card_w + gap)
            # Fondo card
            cv2.rectangle(img, (x, y0), (x + card_w, y0 + card_h), self.C_CARD, -1)
            cv2.rectangle(img, (x, y0), (x + card_w, y0 + card_h), self.C_BORDER, 1)
            
            # Titulo
            cv2.putText(img, c["title"], (x + 14, y0 + 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.C_TEXT_MUTED, 1, cv2.LINE_AA)
            
            # Valor principal
            cv2.putText(img, c["val"], (x + 14, y0 + 60),
                        cv2.FONT_HERSHEY_DUPLEX, 0.85, c["val_color"], 1, cv2.LINE_AA)
            
            # Subtexto o Barra de gas
            if c.get("is_gauge", False):
                # Barra de deteccion: Si ratio < 1, hay gas (invertir escala)
                ratio_val = max(0.01, min(1.0, c["ratio"]))
                # detection 0% when ratio=1.0, 100% when ratio<=0.1
                detection_pct = max(0.0, min(1.0, (1.0 - ratio_val) / 0.9))
                
                bar_x = x + 14
                bar_y = y0 + 74
                bar_w = card_w - 28
                bar_h = 10
                
                cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (20, 15, 15), -1)
                cv2.rectangle(img, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), self.C_BORDER, 1)
                
                fill_w = int(bar_w * detection_pct)
                if fill_w > 0:
                    # Color dinamico segun intensidad: verde -> amarillo -> rojo
                    if detection_pct < 0.35:
                        fill_color = self.C_SUCCESS
                    elif detection_pct < 0.70:
                        fill_color = self.C_WARNING
                    else:
                        fill_color = self.C_DANGER
                    cv2.rectangle(img, (bar_x, bar_y), (bar_x + fill_w, bar_y + bar_h), fill_color, -1)
                
                pct_str = f"Gas: {int(detection_pct * 100)}%"
                cv2.putText(img, pct_str, (x + card_w - 75, y0 + 94),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.C_TEXT_MUTED, 1, cv2.LINE_AA)
            else:
                cv2.putText(img, c["sub"], (x + 14, y0 + 84),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, self.C_TEXT_MUTED, 1, cv2.LINE_AA)

    def draw_oscilloscope(self, img, cur):
        gx = 16
        gy = 180
        gw = self.w - 32
        gh = self.h - gy - 62
        
        # Fondo del osciloscopio
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), (18, 12, 10), -1)
        cv2.rectangle(img, (gx, gy), (gx + gw, gy + gh), self.C_BORDER, 1)
        
        # Ejes y lineas de tension (0.0 V a 3.3 V)
        voltajes = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.3]
        for v in voltajes:
            norm_y = (v / 3.3)
            y_pixel = int((gy + gh) - (norm_y * (gh - 30)) - 15)
            # Linea punteada o delgada
            cv2.line(img, (gx + 40, y_pixel), (gx + gw - 15, y_pixel), self.C_GRID, 1)
            cv2.putText(img, f"{v:.1f}V", (gx + 6, y_pixel + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, self.C_TEXT_MUTED, 1, cv2.LINE_AA)

        # Linea de tiempo vertical cada 50 pixeles
        for x_tick in range(gx + 40, gx + gw - 15, 80):
            cv2.line(img, (x_tick, gy + 15), (x_tick, gy + gh - 15), (28, 20, 20), 1)

        # Dibujar curvas
        n_pts = len(self.buf_raw)
        plot_w = gw - 55
        x_start = gx + 45
        
        if n_pts > 1:
            pts_raw = []
            pts_med = []
            pts_ema = []
            
            for idx in range(n_pts):
                x_pos = int(x_start + (idx / float(self.buffer_size - 1)) * plot_w)
                
                y_r = int((gy + gh) - (min(3.3, max(0.0, self.buf_raw[idx])) / 3.3) * (gh - 30) - 15)
                y_m = int((gy + gh) - (min(3.3, max(0.0, self.buf_med[idx])) / 3.3) * (gh - 30) - 15)
                y_e = int((gy + gh) - (min(3.3, max(0.0, self.buf_ema[idx])) / 3.3) * (gh - 30) - 15)
                
                pts_raw.append((x_pos, y_r))
                pts_med.append((x_pos, y_m))
                pts_ema.append((x_pos, y_e))
                
            pts_raw = np.array(pts_raw, np.int32).reshape((-1, 1, 2))
            pts_med = np.array(pts_med, np.int32).reshape((-1, 1, 2))
            pts_ema = np.array(pts_ema, np.int32).reshape((-1, 1, 2))
            
            # Polilineas con anti-aliasing
            cv2.polylines(img, [pts_raw], False, self.C_RAW, 1, cv2.LINE_AA)
            cv2.polylines(img, [pts_med], False, self.C_MED, 2, cv2.LINE_AA)
            cv2.polylines(img, [pts_ema], False, self.C_EMA, 2, cv2.LINE_AA)

        # Leyenda en la esquina superior derecha del osciloscopio
        leg_x = gx + gw - 380
        leg_y = gy + 16
        cv2.rectangle(img, (leg_x, leg_y), (gx + gw - 15, leg_y + 30), (30, 20, 20), -1)
        cv2.rectangle(img, (leg_x, leg_y), (gx + gw - 15, leg_y + 30), self.C_BORDER, 1)
        
        # Raw
        cv2.circle(img, (leg_x + 14, leg_y + 15), 5, self.C_RAW, -1)
        cv2.putText(img, "Raw", (leg_x + 24, leg_y + 19), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.C_TEXT, 1, cv2.LINE_AA)
        
        # Mediana
        cv2.circle(img, (leg_x + 90, leg_y + 15), 5, self.C_MED, -1)
        cv2.putText(img, "Mediana (N=5)", (leg_x + 100, leg_y + 19), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.C_TEXT, 1, cv2.LINE_AA)
        
        # EMA
        cv2.circle(img, (leg_x + 240, leg_y + 15), 5, self.C_EMA, -1)
        cv2.putText(img, "EMA (a=0.20)", (leg_x + 250, leg_y + 19), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.C_TEXT, 1, cv2.LINE_AA)

    def draw_footer(self, img):
        fy = self.h - 44
        cv2.rectangle(img, (0, fy), (self.w, self.h), (32, 22, 20), -1)
        cv2.line(img, (0, fy), (self.w, fy), self.C_BORDER, 1)
        
        shortcuts = [
            ("[C]", "Calibrar R0"),
            ("[S]", "Guardar Captura + CSV"),
            ("[R]", "Resetear Grafica"),
            ("[P]", "Pausar" if not self.paused else "Reanudar"),
            ("[Q / ESC]", "Salir")
        ]
        
        sx = 20
        for key_tag, desc in shortcuts:
            cv2.putText(img, key_tag, (sx, fy + 26), cv2.FONT_HERSHEY_DUPLEX, 0.45, self.C_EMA, 1, cv2.LINE_AA)
            sx += len(key_tag) * 9 + 4
            cv2.putText(img, desc, (sx, fy + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.40, self.C_TEXT_MUTED, 1, cv2.LINE_AA)
            sx += len(desc) * 8 + 24

    def save_snapshot_and_csv(self, frame):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Guardar captura PNG
        png_path = os.path.join(output_dir, f"captura_gas_{ts}.png")
        cv2.imwrite(png_path, frame)
        safe_print(f"[+] Captura de pantalla guardada en: {png_path}")
        
        # 2. Guardar CSV de historico
        csv_path = os.path.join(output_dir, f"datos_gas_{ts}.csv")
        with self.rx.lock:
            data_to_save = list(self.rx.history)
            
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("timestamp_iso,timestamp_epoch,v_raw,v_med,v_ema,rs_ohm,r0_ohm,ratio\n")
                for r in data_to_save:
                    dt_str = datetime.datetime.fromtimestamp(r["timestamp"]).isoformat()
                    f.write(f"{dt_str},{r['timestamp']:.3f},{r['v_raw']:.4f},{r['v_med']:.4f},{r['v_ema']:.4f},"
                            f"{r['rs']:.1f},{r['r0']:.1f},{r['ratio']:.4f}\n")
            safe_print(f"[+] Datos exportados exitosamente ({len(data_to_save)} filas) a: {csv_path}")
        except Exception as e:
            safe_print(f"[-] Error guardando CSV: {e}")

def main():
    mode = "serial"
    target = find_default_port()
    baud = 115200

    if len(sys.argv) > 1:
        arg1 = sys.argv[1].lower()
        if arg1 in ["--wifi", "-w", "wifi"]:
            mode = "wifi"
            target = sys.argv[2] if len(sys.argv) > 2 else "192.168.4.1"
        elif arg1.startswith("http") or "." in arg1:
            mode = "wifi"
            target = sys.argv[1]
        elif arg1.upper().startswith("COM"):
            mode = "serial"
            target = sys.argv[1].upper()
            if len(sys.argv) > 2:
                baud = int(sys.argv[2])

    safe_print("=" * 70)
    safe_print(" VISOR Y MONITOR DE GAS MiCS-5524 & ESP32-S3 (OpenCV Python)")
    safe_print(" Tesis Ingenieria Mecatronica - UTEC 2026")
    safe_print(f" Modo: {mode.upper()} | Destino: {target}")
    safe_print("=" * 70)

    receiver = GasTelemetryReceiver(mode=mode, port_or_url=target, baud_rate=baud)
    receiver.start()

    dashboard = GasDashboardOpenCV(receiver, width=1280, height=720)
    try:
        dashboard.run()
    finally:
        receiver.stop()

if __name__ == "__main__":
    main()
