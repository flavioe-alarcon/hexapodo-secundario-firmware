"""
========================================================================================
Visor y Monitor de Telemetria en Tiempo Real para Sensor de Corriente ACS758LCB-050B
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Robot: Hexapodo Primario (Chipo) - Monitoreo de Consumo Total de Bateria (3S LiPo)
Plataforma de Adquisicion: Arduino Nano (ATmega328P @ 16 MHz) en puerto COM15 / 115200 baud
Entrada Analogica: Pin A1 conectado a OU1 (Señal directa del ACS758)
========================================================================================
"""

import sys
import os
import time
import json
import threading
import datetime
import serial
import serial.tools.list_ports
import cv2
import numpy as np

# Soporte UTF-8 en Windows
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
        if "COM15" in p.device or "FT232" in p.description or "0403:6001" in p.hwid:
            return p.device
    for p in ports:
        if "USB" in p.description or "Serial" in p.description:
            return p.device
    return "COM15"

class CurrentTelemetryReceiver:
    def __init__(self, port="COM15", baud=115200):
        self.port = port
        self.baud = baud
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        
        self.invert_sign = False
        self.software_zero_offset = 0.0
        
        # Modos de escala vertical: +/- 50A (completo), +/- 20A, +/- 5A
        self.scale_modes = [50.0, 20.0, 5.0]
        self.scale_idx = 0  # Iniciar por defecto en rango completo +/- 50A
        
        self.latest_data = {
            "t_ms": 0,
            "v_out": 2.500,
            "v_zero": 2.500,
            "current_a": 0.0,
            "power_w": 0.0,
            "pin": "A1",
            "timestamp": time.time()
        }
        
        # Metricas acumuladas
        self.i_max = 0.0
        self.i_min = 0.0
        self.mah_accum = 0.0
        self.wh_accum = 0.0
        self.last_integrate_time = None
        
        # Historial para osciloscopio
        self.history_time = []
        self.history_current = []
        self.max_history = 350
        
        # Grabacion CSV
        self.recording = False
        self.csv_file = None
        self.csv_path = ""
        self.csv_records_count = 0
        
        self.serial_inst = None
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._serial_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.stop_recording()
        if self.serial_inst:
            try:
                self.serial_inst.close()
            except Exception:
                pass

    def send_tare_command(self):
        with self.lock:
            self.software_zero_offset = self.latest_data["current_a"]
            self.i_max = 0.0
            self.i_min = 0.0
            self.mah_accum = 0.0
            self.wh_accum = 0.0
        if self.serial_inst and self.serial_inst.is_open:
            try:
                self.serial_inst.write(b'c')
                safe_print("[*] Comando de Calibracion 'C' enviado al Arduino Nano (Pin A1).")
            except Exception as e:
                safe_print(f"[-] Error enviando calibracion: {e}")

    def toggle_sign(self):
        with self.lock:
            self.invert_sign = not self.invert_sign
            safe_print(f"[*] Signo de corriente invertido: {self.invert_sign}")

    def cycle_scale(self):
        with self.lock:
            self.scale_idx = (self.scale_idx + 1) % len(self.scale_modes)
            current_range = self.scale_modes[self.scale_idx]
            safe_print(f"[*] Escala vertical cambiada a: +/- {current_range:.0f} A")

    def get_current_scale_limit(self):
        with self.lock:
            return self.scale_modes[self.scale_idx]

    def start_recording(self):
        with self.lock:
            if self.recording:
                return
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datos_mision")
            if not os.path.exists(folder):
                os.makedirs(folder, exist_ok=True)
            self.csv_path = os.path.join(folder, f"registro_corriente_{timestamp_str}.csv")
            try:
                self.csv_file = open(self.csv_path, "w", encoding="utf-8")
                self.csv_file.write("ISO_Timestamp,Tiempo_Relativo_s,Tiempo_Arduino_ms,Pin,Voltaje_Sensor_V,Voltaje_Offset_V,Corriente_A,Potencia_W,Consumo_mAh\n")
                self.csv_file.flush()
                self.recording = True
                self.csv_records_count = 0
                self.record_start_time = time.time()
                safe_print(f"[+] Grabacion iniciada en: {self.csv_path}")
            except Exception as e:
                safe_print(f"[-] Error creando archivo CSV: {e}")
                self.recording = False

    def stop_recording(self):
        with self.lock:
            if not self.recording:
                return
            self.recording = False
            if self.csv_file:
                try:
                    self.csv_file.close()
                except Exception:
                    pass
                self.csv_file = None
            safe_print(f"[*] Grabacion finalizada. {self.csv_records_count} registros guardados en {self.csv_path}")

    def _serial_loop(self):
        while self.running:
            try:
                safe_print(f"[*] Conectando a {self.port} a {self.baud} baudios...")
                self.serial_inst = serial.Serial(self.port, self.baud, timeout=1.5)
                time.sleep(1.0)
                self.connected = True
                safe_print(f"[+] Conectado exitosamente a {self.port}.")
                
                self.serial_inst.reset_input_buffer()
                self.last_integrate_time = time.time()

                while self.running:
                    line = self.serial_inst.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            payload = json.loads(line)
                            if "v" in payload and "i" in payload:
                                now = time.time()
                                raw_i = float(payload.get("i", 0.0))
                                v_out = float(payload.get("v", 2.5))
                                v_zero = float(payload.get("v0", 2.5))
                                t_ms = int(payload.get("t", 0))
                                pin_name = payload.get("pin", "A1")

                                with self.lock:
                                    curr = raw_i if not self.invert_sign else -raw_i
                                    curr = curr - self.software_zero_offset
                                    p_watts = curr * 11.1

                                    if self.last_integrate_time is not None:
                                        dt_hours = (now - self.last_integrate_time) / 3600.0
                                        if curr > 0:
                                            self.mah_accum += (curr * 1000.0) * dt_hours
                                            self.wh_accum += p_watts * dt_hours
                                    self.last_integrate_time = now

                                    if curr > self.i_max:
                                        self.i_max = curr
                                    if curr < self.i_min:
                                        self.i_min = curr

                                    self.latest_data = {
                                        "t_ms": t_ms,
                                        "v_out": v_out,
                                        "v_zero": v_zero,
                                        "current_a": curr,
                                        "power_w": p_watts,
                                        "pin": pin_name,
                                        "timestamp": now
                                    }

                                    self.history_time.append(now)
                                    self.history_current.append(curr)
                                    if len(self.history_current) > self.max_history:
                                        self.history_time.pop(0)
                                        self.history_current.pop(0)

                                    if self.recording and self.csv_file:
                                        rel_t = now - self.record_start_time
                                        iso_t = datetime.datetime.now().isoformat()
                                        row = f"{iso_t},{rel_t:.3f},{t_ms},{pin_name},{v_out:.4f},{v_zero:.4f},{curr:.3f},{p_watts:.2f},{self.mah_accum:.2f}\n"
                                        self.csv_file.write(row)
                                        self.csv_records_count += 1
                                        if self.csv_records_count % 20 == 0:
                                            self.csv_file.flush()
                        except Exception:
                            pass
            except Exception as e:
                self.connected = False
                safe_print(f"[-] Error en enlace serial: {e}. Reintentando en 2 segundos...")
                time.sleep(2.0)
            finally:
                if self.serial_inst:
                    try:
                        self.serial_inst.close()
                    except Exception:
                        pass


def draw_hud(receiver, width=1040, height=660):
    hud = np.zeros((height, width, 3), dtype=np.uint8)
    hud[:] = (20, 22, 26)

    with receiver.lock:
        data = dict(receiver.latest_data)
        hist_i = list(receiver.history_current)
        i_max = receiver.i_max
        i_min = receiver.i_min
        mah_acc = receiver.mah_accum
        wh_acc = receiver.wh_accum
        is_rec = receiver.recording
        rec_count = receiver.csv_records_count
        is_conn = receiver.connected
        inv = receiver.invert_sign
        scale_limit = receiver.scale_modes[receiver.scale_idx]

    curr = data["current_a"]
    v_out = data["v_out"]
    v_zero = data["v_zero"]
    power = data["power_w"]
    pin_name = data.get("pin", "A1")

    # 1. Barra superior
    cv2.rectangle(hud, (0, 0), (width, 55), (32, 36, 44), -1)
    cv2.putText(hud, "MONITOR DE CONSUMO DE CORRIENTE - ACS758LCB-050B (50A)", (20, 36),
                cv2.FONT_HERSHEY_DUPLEX, 0.72, (0, 230, 255), 2, cv2.LINE_AA)

    # Estado de conexion
    conn_color = (0, 220, 100) if is_conn else (50, 50, 230)
    conn_text = f"CONECTADO [{receiver.port}]" if is_conn else f"DESCONECTADO [{receiver.port}]"
    cv2.circle(hud, (width - 230, 28), 8, conn_color, -1)
    cv2.putText(hud, conn_text, (width - 215, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (230, 230, 230), 1, cv2.LINE_AA)

    # 2. Tarjetas de Metricas Superiores
    # Tarjeta 1: Corriente Instantanea
    card1_rect = (20, 70, 235, 160)
    cv2.rectangle(hud, (card1_rect[0], card1_rect[1]), (card1_rect[0] + card1_rect[2], card1_rect[1] + card1_rect[3]), (28, 32, 40), -1)
    
    # Color dinamico segun magnitud
    c_color = (0, 235, 120)
    if abs(curr) > 3.0:
        c_color = (0, 215, 255)
    if abs(curr) > 8.0:
        c_color = (60, 70, 255)
        
    cv2.rectangle(hud, (card1_rect[0], card1_rect[1]), (card1_rect[0] + card1_rect[2], card1_rect[1] + card1_rect[3]), c_color, 2)
    cv2.putText(hud, "CORRIENTE TOTAL", (card1_rect[0] + 15, card1_rect[1] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(hud, f"{curr:+.2f} A", (card1_rect[0] + 12, card1_rect[1] + 85),
                cv2.FONT_HERSHEY_DUPLEX, 1.35, c_color, 3, cv2.LINE_AA)
    cv2.putText(hud, f"Max: {i_max:+.2f}A  Min: {i_min:+.2f}A", (card1_rect[0] + 15, card1_rect[1] + 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (200, 200, 200), 1, cv2.LINE_AA)

    # Tarjeta 2: Potencia Instantanea (3S 11.1V)
    card2_rect = (270, 70, 235, 160)
    cv2.rectangle(hud, (card2_rect[0], card2_rect[1]), (card2_rect[0] + card2_rect[2], card2_rect[1] + card2_rect[3]), (28, 32, 40), -1)
    cv2.rectangle(hud, (card2_rect[0], card2_rect[1]), (card2_rect[0] + card2_rect[2], card2_rect[1] + card2_rect[3]), (220, 150, 40), 1)
    cv2.putText(hud, "POTENCIA (LiPo 3S 11.1V)", (card2_rect[0] + 15, card2_rect[1] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(hud, f"{power:+.1f} W", (card2_rect[0] + 15, card2_rect[1] + 85),
                cv2.FONT_HERSHEY_DUPLEX, 1.3, (255, 185, 60), 2, cv2.LINE_AA)
    cv2.putText(hud, f"Energia: {wh_acc:.2f} Wh", (card2_rect[0] + 15, card2_rect[1] + 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    # Tarjeta 3: Carga Consumida (mAh)
    card3_rect = (520, 70, 235, 160)
    cv2.rectangle(hud, (card3_rect[0], card3_rect[1]), (card3_rect[0] + card3_rect[2], card3_rect[1] + card3_rect[3]), (28, 32, 40), -1)
    cv2.rectangle(hud, (card3_rect[0], card3_rect[1]), (card3_rect[0] + card3_rect[2], card3_rect[1] + card3_rect[3]), (180, 90, 220), 1)
    cv2.putText(hud, "CARGA ACUMULADA", (card3_rect[0] + 15, card3_rect[1] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1, cv2.LINE_AA)
    cv2.putText(hud, f"{mah_acc:.1f} mAh", (card3_rect[0] + 15, card3_rect[1] + 85),
                cv2.FONT_HERSHEY_DUPLEX, 1.2, (220, 130, 255), 2, cv2.LINE_AA)
    cv2.putText(hud, f"Bat: 4500 mAh ({(mah_acc/4500.0)*100:.1f}%)", (card3_rect[0] + 15, card3_rect[1] + 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    # Tarjeta 4: Tension Analogica y Estado
    card4_rect = (770, 70, 250, 160)
    cv2.rectangle(hud, (card4_rect[0], card4_rect[1]), (card4_rect[0] + card4_rect[2], card4_rect[1] + card4_rect[3]), (28, 32, 40), -1)
    cv2.rectangle(hud, (card4_rect[0], card4_rect[1]), (card4_rect[0] + card4_rect[2], card4_rect[1] + card4_rect[3]), (80, 130, 180), 1)
    cv2.putText(hud, f"SENSOR ADC (Pin {pin_name})", (card4_rect[0] + 15, card4_rect[1] + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(hud, f"Vout: {v_out:.3f} V", (card4_rect[0] + 15, card4_rect[1] + 62),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.putText(hud, f"Offset V0: {v_zero:.3f} V", (card4_rect[0] + 15, card4_rect[1] + 92),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (160, 160, 160), 1, cv2.LINE_AA)
    cv2.putText(hud, f"Escala: +/-{scale_limit:.0f}A", (card4_rect[0] + 15, card4_rect[1] + 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 200, 60), 1, cv2.LINE_AA)

    # 3. Osciloscopio / Grafica de Corriente Bidireccional
    plot_x = 20
    plot_y = 250
    plot_w = 1000
    plot_h = 340
    
    cv2.rectangle(hud, (plot_x, plot_y), (plot_x + plot_w, plot_y + plot_h), (16, 18, 22), -1)
    cv2.rectangle(hud, (plot_x, plot_y), (plot_x + plot_w, plot_y + plot_h), (50, 55, 65), 1)

    # Rango simetrico: desde -scale_limit hasta +scale_limit
    y_min = -scale_limit
    y_max = scale_limit
    y_range = y_max - y_min

    # Lineas de rejilla
    if scale_limit == 50.0:
        grid_values = [-50.0, -40.0, -30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0, 40.0, 50.0]
    elif scale_limit == 20.0:
        grid_values = [-20.0, -15.0, -10.0, -5.0, 0.0, 5.0, 10.0, 15.0, 20.0]
    else: # 5.0A
        grid_values = [-5.0, -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0]

    for g_val in grid_values:
        norm_y = 1.0 - ((g_val - y_min) / y_range)
        gy = int(plot_y + norm_y * plot_h)
        
        # Linea de cero destacada
        if abs(g_val) < 0.001:
            cv2.line(hud, (plot_x, gy), (plot_x + plot_w, gy), (0, 180, 255), 2)
            cv2.putText(hud, "  0.0 A (CERO)", (plot_x + 8, gy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 255), 1, cv2.LINE_AA)
        else:
            cv2.line(hud, (plot_x, gy), (plot_x + plot_w, gy), (35, 40, 50), 1)
            cv2.putText(hud, f"{g_val:+5.1f} A", (plot_x + 8, gy - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (120, 130, 150), 1, cv2.LINE_AA)

    # Trazar curva continua
    if len(hist_i) >= 2:
        pts = []
        for idx, val in enumerate(hist_i):
            px = int(plot_x + (idx / float(receiver.max_history)) * plot_w)
            norm_val = 1.0 - ((val - y_min) / y_range)
            norm_val = max(0.0, min(1.0, norm_val))
            py = int(plot_y + norm_val * plot_h)
            pts.append((px, py))
        
        for k in range(len(pts) - 1):
            val_k = hist_i[k]
            # Color segun polaridad
            seg_color = (0, 235, 120) if val_k >= 0 else (255, 120, 60)
            if abs(val_k) > 12.0:
                seg_color = (60, 80, 255)
            cv2.line(hud, pts[k], pts[k+1], seg_color, 2, cv2.LINE_AA)

    # 4. Barra Inferior de Estado y Controles
    cv2.rectangle(hud, (0, height - 50), (width, height), (30, 34, 40), -1)

    if is_rec:
        rec_color = (0, 0, 255) if int(time.time() * 2) % 2 == 0 else (100, 100, 255)
        cv2.circle(hud, (30, height - 25), 8, rec_color, -1)
        cv2.putText(hud, f"REC CSV: {rec_count} pts", (48, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 220, 255), 1, cv2.LINE_AA)
    else:
        cv2.circle(hud, (30, height - 25), 8, (70, 70, 80), -1)
        cv2.putText(hud, "GRABACION EN PAUSA", (48, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140, 140, 150), 1, cv2.LINE_AA)

    help_text = "[C] Tara/Cero  |  [E] Escala (+/-50A/20A/5A)  |  [I] Invertir  |  [R] Grabar CSV  |  [S] Captura  |  [Q] Salir"
    cv2.putText(hud, help_text, (200, height - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

    return hud

def main():
    target_port = sys.argv[1] if len(sys.argv) > 1 else find_default_port()
    safe_print(f"================================================================")
    safe_print(f"  VISOR DE CORRIENTE ACS758LCB-050B - ROBOT PRIMARIO CHIPO      ")
    safe_print(f"  Puerto seleccionado: {target_port}                            ")
    safe_print(f"  Canal ADC configurado: Pin A1 (conectado a OU1)               ")
    safe_print(f"================================================================")

    receiver = CurrentTelemetryReceiver(port=target_port, baud=115200)
    receiver.start()

    window_name = "Telemetria Sensor de Corriente ACS758LCB (UTEC 2026)"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            frame = draw_hud(receiver)
            cv2.imshow(window_name, frame)

            key = cv2.waitKey(30) & 0xFF
            if key in [ord('q'), ord('Q'), 27]: # Salir
                break
            elif key in [ord('c'), ord('C')]:   # Calibrar / Tara Cero
                receiver.send_tare_command()
            elif key in [ord('e'), ord('E')]:   # Alternar escala
                receiver.cycle_scale()
            elif key in [ord('i'), ord('I')]:   # Invertir signo
                receiver.toggle_sign()
            elif key in [ord('r'), ord('R')]:   # Iniciar / Pausar grabacion
                if receiver.recording:
                    receiver.stop_recording()
                else:
                    receiver.start_recording()
            elif key in [ord('s'), ord('S')]:   # Captura de pantalla
                folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "imagenes_experimentos")
                os.makedirs(folder, exist_ok=True)
                fn = os.path.join(folder, f"captura_corriente_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(fn, frame)
                safe_print(f"[+] Captura guardada en: {fn}")

    finally:
        receiver.stop()
        cv2.destroyAllWindows()
        safe_print("[*] Visor cerrado correctamente.")

if __name__ == "__main__":
    main()
