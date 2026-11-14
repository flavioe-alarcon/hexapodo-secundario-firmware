"""
========================================================================================
Visualizador y Analizador de Archivos CSV - Sensor de Gas MiCS-5524
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Permite seleccionar interactivamente un archivo .csv generado por el visor de gas
y generar graficas analiticas de alta calidad con calidad de publicacion academica.
========================================================================================
"""

import sys
import os
import csv
import warnings
warnings.filterwarnings('ignore')
import datetime
import tkinter as tk
from tkinter import filedialog
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Configurar estilo visual limpio
plt.rcParams['font.sans-serif'] = 'Segoe UI', 'DejaVu Sans', 'Arial'
plt.rcParams['axes.edgecolor'] = '#cbd5e1'
plt.rcParams['axes.linewidth'] = 0.8

def select_csv_file():
    """Abre el explorador de archivos nativo de Windows para elegir el CSV"""
    root = tk.Tk()
    root.withdraw() # Ocultar ventana principal vacia
    root.attributes('-topmost', True) # Traer al frente
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = filedialog.askopenfilename(
        title="Selecciona el archivo CSV de datos de gas para graficar",
        initialdir=current_dir,
        filetypes=[("Archivos CSV (*.csv)", "*.csv"), ("Todos los archivos (*.*)", "*.*")]
    )
    root.destroy()
    return file_path

def load_gas_csv(file_path):
    """Carga y procesa las columnas del archivo CSV"""
    times_rel = []
    times_iso = []
    v_raw = []
    v_med = []
    v_ema = []
    rs_kohm = []
    r0_kohm = []
    ratio_inv = []
    
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        t0 = None
        for row in reader:
            try:
                t_epoch = float(row['timestamp_epoch'])
                if t0 is None:
                    t0 = t_epoch
                
                t_rel = t_epoch - t0
                times_rel.append(t_rel)
                times_iso.append(row.get('timestamp_iso', ''))
                
                vr = float(row['v_raw'])
                vm = float(row['v_med'])
                ve = float(row['v_ema'])
                rs = float(row['rs_ohm'])
                r0 = float(row.get('r0_ohm', 10000.0))
                
                v_raw.append(vr)
                v_med.append(vm)
                v_ema.append(ve)
                rs_kohm.append(rs / 1000.0)
                r0_kohm.append(r0 / 1000.0)
                
                # Proporcion ascendente R0 / Rs
                inv_r = r0 / max(1.0, rs)
                ratio_inv.append(inv_r)
            except Exception:
                continue
                
    return {
        'times_rel': np.array(times_rel),
        'v_raw': np.array(v_raw),
        'v_med': np.array(v_med),
        'v_ema': np.array(v_ema),
        'rs_kohm': np.array(rs_kohm),
        'r0_kohm': np.array(r0_kohm),
        'ratio_inv': np.array(ratio_inv),
        'n_samples': len(times_rel)
    }

def plot_gas_data(data, file_name):
    """Genera la figura analitica de dos paneles para tesis"""
    t = data['times_rel']
    n = data['n_samples']
    if n == 0:
        print("[!] El archivo CSV no contiene registros validos.")
        return
        
    duration_sec = t[-1] - t[0] if n > 1 else 0.0
    sampling_freq = (n / duration_sec) if duration_sec > 0 else 0.0
    
    v_max = np.max(data['v_raw'])
    v_base = np.percentile(data['v_ema'], 10)
    rs_min = np.min(data['rs_kohm'])
    ratio_max = np.max(data['ratio_inv'])
    
    print("=" * 65)
    print(f" RESUMEN ANALITICO DE LA MEDICION: {file_name}")
    print(f" - Muestras procesadas:   {n:,} puntos")
    print(f" - Duracion del ensayo:   {duration_sec:.1f} s ({duration_sec/60.0:.2f} min)")
    print(f" - Frecuencia promedio:   {sampling_freq:.1f} Hz")
    print(f" - Voltaje base (limpio): {v_base:.3f} V")
    print(f" - Voltaje pico maximo:   {v_max:.3f} V")
    print(f" - Resistencia Rs minima: {rs_min:.2f} kOhm")
    print(f" - Proporcion R0/Rs max:  {ratio_max:.2f}x (aumento de conductividad)")
    print("=" * 65)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, dpi=110)
    fig.patch.set_facecolor('#ffffff')

    # ------------------ PANEL 1: VOLTAJES Y FILTROS ------------------
    ax1.set_facecolor('#f8fafc')
    ax1.plot(t, data['v_raw'], label='Senal Cruda (Raw)', color='#ef4444', alpha=0.5, linewidth=1.0)
    ax1.plot(t, data['v_med'], label='Filtro Mediana (N=5)', color='#f59e0b', linewidth=1.6)
    ax1.plot(t, data['v_ema'], label='Filtro EMA (α=0.20)', color='#0284c7', linewidth=2.0)
    
    # Linea de saturacion del ADC ESP32-S3
    ax1.axhline(3.14, color='#94a3b8', linestyle='--', linewidth=1.2, label='Tope ADC ESP32-S3 (~3.14 V)')
    
    ax1.set_ylabel('Voltaje Analógico (V)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_ylim(-0.05, 3.45)
    ax1.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')
    ax1.legend(loc='upper right', framealpha=0.95, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9.5)
    ax1.set_title(f"Análisis de Sensado de Gas MiCS-5524 y Filtrado Digital\nArchivo: {file_name}",
                  fontsize=12, fontweight='bold', pad=12, color='#0f172a')

    # Anotaciones de estadisticas en caja de texto
    stats_text = (f"Puntos: {n:,} | Freq: {sampling_freq:.1f} Hz\n"
                  f"V_base: {v_base:.3f} V | V_pico: {v_max:.3f} V")
    ax1.text(0.015, 0.92, stats_text, transform=ax1.transAxes, fontsize=9,
             verticalalignment='top', bbox=dict(boxstyle='round,pad=0.5', facecolor='#ffffff', edgecolor='#cbd5e1', alpha=0.9))

    # ------------------ PANEL 2: PROPORCION ASCENDENTE Y RESISTENCIA ------------------
    ax2.set_facecolor('#f8fafc')
    line_ratio = ax2.plot(t, data['ratio_inv'], label='Proporcion Gas (R0 / Rs)', color='#10b981', linewidth=1.8)
    ax2.axhline(1.0, color='#64748b', linestyle=':', label='Linea Base Aire Limpio (R0/Rs = 1.0)')
    ax2.set_ylabel('Proporción R0 / Rs (Ascendente)', fontsize=11, fontweight='bold', color='#065f46')
    ax2.tick_params(axis='y', labelcolor='#065f46')
    ax2.set_xlabel('Tiempo Transcurrido (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.grid(True, linestyle=':', alpha=0.6, color='#cbd5e1')

    # Eje secundario para Resistencia Rs (kOhm)
    ax2_rs = ax2.twinx()
    line_rs = ax2_rs.plot(t, data['rs_kohm'], label='Resistencia Sensor Rs', color='#8b5cf6', linestyle='--', linewidth=1.4, alpha=0.85)
    ax2_rs.set_ylabel('Resistencia Rs (kΩ)', fontsize=11, fontweight='bold', color='#5b21b6')
    ax2_rs.tick_params(axis='y', labelcolor='#5b21b6')

    # Leyenda combinada para panel 2
    lines = line_ratio + line_rs
    labels = [l.get_label() for l in lines]
    ax2.legend(lines, labels, loc='upper right', framealpha=0.95, facecolor='#ffffff', edgecolor='#cbd5e1', fontsize=9.5)

    plt.tight_layout()
    plt.show()

def main():
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        file_path = sys.argv[1]
    else:
        print("[*] Abriendo explorador de archivos para seleccionar CSV...")
        file_path = select_csv_file()
        
    if not file_path:
        print("[-] Operacion cancelada: No se selecciono ningun archivo.")
        return

    print(f"[+] Cargando archivo: {file_path}")
    data = load_gas_csv(file_path)
    file_name = os.path.basename(file_path)
    plot_gas_data(data, file_name)

if __name__ == '__main__':
    main()
