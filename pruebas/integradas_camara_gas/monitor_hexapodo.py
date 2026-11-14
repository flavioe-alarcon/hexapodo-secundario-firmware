#!/usr/bin/env python3
"""
====================================================================
MONITOR EN TERMINAL SSH - HEXAPODO SECUNDARIO (Opción A: Tablero TUI)
Tesis Mecatrónica UTEC 2026 - Inspección Ambiental y Minera
====================================================================
No requiere librerías externas (solo módulos nativos de Python 3).
Funciona 100% offline sin conexión a internet.
====================================================================
"""

import socket
import json
import urllib.request
import threading
import time
import sys
import os
import select

# Configuración de Red
UDP_PORT = 5005
UDP_BIND_IP = "0.0.0.0"

# Estado Global de Telemetría
g_lock = threading.Lock()
g_running = True
g_esp32_ip = None
g_last_gas_data = None
g_last_udp_time = 0.0

# Métricas de Cámara UVC
g_cam_fps = 0.0
g_cam_kbs = 0.0
g_cam_status = "Buscando ESP32..."
g_cam_frames = 0
g_cam_bytes = 0

# Estado de Luz
g_light_state = False

def gas_udp_listener():
    """Hilo receptor UDP de telemetría de gases a 20 Hz."""
    global g_esp32_ip, g_last_gas_data, g_last_udp_time, g_running, g_light_state
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((UDP_BIND_IP, UDP_PORT))
    sock.settimeout(0.5)

    while g_running:
        try:
            data, addr = sock.recvfrom(2048)
            now = time.time()
            text = data.decode("utf-8", errors="ignore").strip()
            parsed = json.loads(text)
            
            with g_lock:
                g_last_gas_data = parsed
                g_last_udp_time = now
                if not g_esp32_ip:
                    # Detectar IP remitente automáticamente
                    g_esp32_ip = parsed.get("ip") or addr[0]
                if "light" in parsed:
                    g_light_state = bool(parsed["light"])
        except (socket.timeout, json.JSONDecodeError):
            continue
        except Exception:
            if not g_running:
                break
            time.sleep(0.05)
            
    sock.close()

def camera_stream_consumer():
    """Hilo consumidor de stream MJPEG (puerto 81) para medir FPS y KB/s reales."""
    global g_cam_fps, g_cam_kbs, g_cam_status, g_running, g_esp32_ip
    
    while g_running:
        ip = None
        with g_lock:
            ip = g_esp32_ip

        if not ip or ip == "0.0.0.0":
            time.sleep(0.5)
            continue

        url = f"http://{ip}:81/stream"
        with g_lock:
            g_cam_status = f"Conectando a {url}..."

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RPi5-TerminalMonitor"})
            with urllib.request.urlopen(req, timeout=3.0) as stream:
                with g_lock:
                    g_cam_status = "ENLACE ACTIVO (Streaming)"
                
                buf = b""
                frame_count = 0
                byte_count = 0
                t_start = time.time()

                while g_running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break
                    
                    byte_count += len(chunk)
                    buf += chunk
                    
                    # Delimitador JPEG SOI / EOI
                    a = buf.find(b"\xff\xd8")
                    b = buf.find(b"\xff\xd9")
                    if a != -1 and b != -1 and b > a:
                        frame_count += 1
                        buf = buf[b+2:]
                    
                    now = time.time()
                    dt = now - t_start
                    if dt >= 1.0:
                        fps = frame_count / dt
                        kbs = (byte_count / 1024.0) / dt
                        with g_lock:
                            g_cam_fps = fps
                            g_cam_kbs = kbs
                        frame_count = 0
                        byte_count = 0
                        t_start = now
        except Exception as e:
            # Si el canal TCP de video esta en uso por la Laptop/Navegador, consultar telemetria interna del ESP32
            try:
                with urllib.request.urlopen(f"http://{ip}/data", timeout=1.0) as resp:
                    d = json.loads(resp.read().decode('utf-8'))
                    fps = d.get("fps", 0.0)
                    connected = d.get("cam_connected", False)
                    streaming = d.get("cam_streaming", False)
                    with g_lock:
                        if streaming and fps > 0.0:
                            g_cam_status = "STREAMING ACTIVO (Visualizado en Laptop/Web)"
                            g_cam_fps = fps
                            g_cam_kbs = fps * 14.5
                        elif connected:
                            g_cam_status = "Camara Conectada (En Espera)"
                            g_cam_fps = 0.0
                        else:
                            g_cam_status = "Camara Desconectada"
                            g_cam_fps = 0.0
            except Exception:
                with g_lock:
                    g_cam_status = f"En espera ({e.__class__.__name__})"
                    g_cam_fps = 0.0
                    g_cam_kbs = 0.0
            time.sleep(1.0)

def toggle_light():
    """Envía comando HTTP GET para conmutar la linterna LED."""
    global g_esp32_ip
    ip = None
    with g_lock:
        ip = g_esp32_ip
    if not ip or ip == "0.0.0.0":
        return
    try:
        urllib.request.urlopen(f"http://{ip}/light?state=toggle", timeout=1.5)
    except Exception:
        pass

def trigger_calibration():
    """Envía comando HTTP GET para calibrar R0 en aire limpio."""
    global g_esp32_ip
    ip = None
    with g_lock:
        ip = g_esp32_ip
    if not ip or ip == "0.0.0.0":
        return
    try:
        urllib.request.urlopen(f"http://{ip}/calibrate", timeout=1.5)
    except Exception:
        pass

def draw_bar(pct, width=30):
    """Genera una barra gráfica ANSI con colores según el nivel de riesgo."""
    filled = int((pct / 100.0) * width)
    if filled > width: filled = width
    if filled < 0: filled = 0
    empty = width - filled
    
    # Colores ANSI
    if pct >= 60.0:
        col = "\033[91;1m" # Rojo brillante (Peligro crítico)
    elif pct >= 30.0:
        col = "\033[93;1m" # Amarillo (Advertencia)
    else:
        col = "\033[92;1m" # Verde (Seguro)
    
    bar = col + "█" * filled + "\033[90m" + "░" * empty + "\033[0m"
    return bar

def render_dashboard():
    """Dibuja el tablero en consola usando secuencias de escape ANSI."""
    # Cursor a posición inicial (0,0) y limpiar pantalla
    sys.stdout.write("\033[2J\033[H")
    
    with g_lock:
        gas = g_last_gas_data
        t_last = g_last_udp_time
        esp_ip = g_esp32_ip
        cam_fps = g_cam_fps
        cam_kbs = g_cam_kbs
        cam_status = g_cam_status
        light_on = g_light_state

    now = time.time()
    gas_online = (gas is not None) and (now - t_last < 2.0)

    # Encabezado
    print("\033[1;36m╔════════════════════════════════════════════════════════════════════════════╗\033[0m")
    print("\033[1;36m║   HEXAPODO SECUNDARIO · MONITOREO AMBIENTAL Y VISION (TESIS UTEC 2026)     ║\033[0m")
    print("\033[1;36m╚════════════════════════════════════════════════════════════════════════════╝\033[0m")
    
    # Enlace de Red
    ip_display = esp_ip if esp_ip else "Buscando paquete UDP..."
    status_net = "\033[92;1mCONECTADO (UDP 20 Hz)\033[0m" if gas_online else "\033[91;1mDESCONECTADO / ESPERANDO\033[0m"
    print(f" Red Host: \033[1maleskypi-5\033[0m  |  ESP32 IP: \033[1;33m{ip_display}\033[0m  |  Estado: {status_net}")
    print("\033[90m" + "─" * 78 + "\033[0m")

    # Módulo de Gases
    print("\033[1;34m[ 1. SENSOR DE GASES MEMS (MiCS-5524 / CO & Combustibles) ]\033[0m")
    if gas_online and gas:
        pct = gas.get("gas_pct", 0.0)
        v_ema = gas.get("v_ema", 0.0)
        v_raw = gas.get("v_raw", 0.0)
        rs = gas.get("rs", 0.0)
        r0 = gas.get("r0", 0.0)
        ratio = gas.get("ratio", 1.0)
        calib = gas.get("calibrating", False)
        seq = gas.get("seq", 0)

        # Barra visual
        bar = draw_bar(pct, width=32)
        if calib:
            alert_tag = "\033[93;1m[ CALIBRANDO R0 EN AIRE LIMPIO... ]\033[0m"
        elif pct >= 60.0:
            alert_tag = "\033[91;1m[ PELIGRO: GAS DETECTADO - EVACUAR ]\033[0m"
        elif pct >= 30.0:
            alert_tag = "\033[93;1m[ ALERTA: PRESENCIA MODERADA ]\033[0m"
        else:
            alert_tag = "\033[92;1m[ SEGURO: CONCENTRACION NORMAL ]\033[0m"

        print(f"  Intensidad Gas : [{bar}] {pct:5.1f} %  {alert_tag}")
        print(f"  Voltaje Sensor : {v_ema:5.3f} V (Raw ADC: {v_raw:5.3f} V)  |  Ratio R0/Rs: \033[1m{ratio:5.3f}\033[0m")
        print(f"  Resistencia    : Rs = {rs/1000.0:5.2f} kΩ  |  R0 Base = {r0/1000.0:5.2f} kΩ  |  Paquetes: #{seq}")
    else:
        print("  \033[90mEsperando datagramas UDP del ESP32-S3 en el puerto 5005...\033[0m")
        print("  \033[90m(El sensor se actualiza automáticamente al conectar)\033[0m")

    print("\033[90m" + "─" * 78 + "\033[0m")

    # Módulo de Visión UVC
    print("\033[1;35m[ 2. SUBSISTEMA DE VISION UVC (Camara Mini Type-C / TCP 81) ]\033[0m")
    status_cam_col = "\033[92;1m" if "ENLACE ACTIVO" in cam_status else "\033[93m"
    print(f"  Estado Cámara  : {status_cam_col}{cam_status}\033[0m")
    print(f"  Rendimiento    : \033[1;32m{cam_fps:4.1f} FPS\033[0m  |  Ancho de Banda: \033[1;36m{cam_kbs:6.1f} KB/s\033[0m")
    print(f"  Resolución     : 480x320 MJPEG (Host Nativo ESP32-S3 Core 1)")

    print("\033[90m" + "─" * 78 + "\033[0m")

    # Módulo de Iluminación y Controles
    print("\033[1;33m[ 3. ACTUADORES & CONTROLES DE CAMPO ]\033[0m")
    luz_txt = "\033[93;1m💡 ENCENDIDA (100% Lux Blanco)\033[0m" if light_on else "\033[90mAPAGADA\033[0m"
    print(f"  Luz de Inspección : {luz_txt}")
    print("\n  \033[1mCOMANDOS DIRECTOS POR TECLADO:\033[0m")
    print("    [\033[1;33mL\033[0m] Conmutar Luz de Inspección (Encender/Apagar)")
    print("    [\033[1;36mC\033[0m] Calibrar R0 en Aire Limpio (Auto-cero)")
    print("    [\033[1;31mQ\033[0m] Salir del Monitor")
    print("\033[90m" + "═" * 78 + "\033[0m")
    sys.stdout.flush()

def main():
    global g_running
    
    # Iniciar hilos receptores
    t_udp = threading.Thread(target=gas_udp_listener, daemon=True)
    t_cam = threading.Thread(target=camera_stream_consumer, daemon=True)
    t_udp.start()
    t_cam.start()

    # Configuración de lectura no bloqueante de teclado (Linux / Raspberry Pi)
    fd = sys.stdin.fileno()
    old_term = None
    try:
        import termios, tty
        old_term = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:
        pass

    try:
        while g_running:
            render_dashboard()
            
            # Chequear teclado durante 200 ms
            r, _, _ = select.select([sys.stdin], [], [], 0.25)
            if r:
                ch = sys.stdin.read(1).lower()
                if ch == 'q':
                    g_running = False
                    break
                elif ch == 'l':
                    toggle_light()
                elif ch == 'c':
                    trigger_calibration()
    except KeyboardInterrupt:
        g_running = False
    finally:
        if old_term:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old_term)
        print("\n\033[0mMonitor detenido correctamente.\n")

if __name__ == "__main__":
    main()
