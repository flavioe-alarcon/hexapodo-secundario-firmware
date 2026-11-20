"""
========================================================================================
Visualizador y Analizador de Archivos CSV - Sensor de Corriente ACS758LCB
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Genera graficas analiticas con calidad de publicacion para la tesis (Corriente,
Potencia instantanea y consumo energetico acumulado).
========================================================================================
"""

import sys
import os
import csv
import warnings
warnings.filterwarnings('ignore')
import tkinter as tk
from tkinter import filedialog
import numpy as np
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = 'Segoe UI', 'DejaVu Sans', 'Arial'
plt.rcParams['axes.edgecolor'] = '#cbd5e1'
plt.rcParams['axes.linewidth'] = 0.8

def select_csv_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    current_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datos_mision")
    if not os.path.exists(current_dir):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
    file_path = filedialog.askopenfilename(
        title="Selecciona el archivo CSV de datos de corriente",
        initialdir=current_dir,
        filetypes=[("Archivos CSV (*.csv)", "*.csv"), ("Todos los archivos (*.*)", "*.*")]
    )
    root.destroy()
    return file_path

def plot_current_data(csv_path):
    if not csv_path or not os.path.exists(csv_path):
        print("[-] No se selecciono ningun archivo valido.")
        return

    t_rel, curr, power, mah = [], [], [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t_rel.append(float(row.get("Tiempo_Relativo_s", 0.0)))
                curr.append(float(row.get("Corriente_A", 0.0)))
                power.append(float(row.get("Potencia_W", 0.0)))
                mah.append(float(row.get("Consumo_mAh", 0.0)))
            except Exception:
                continue

    if not t_rel:
        print("[-] El archivo CSV no contiene registros validos.")
        return

    t_rel = np.array(t_rel)
    curr = np.array(curr)
    power = np.array(power)
    mah = np.array(mah)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 8), sharex=True)
    fig.patch.set_facecolor('#ffffff')

    # Subplot 1: Corriente
    ax1.set_facecolor('#f8fafc')
    ax1.plot(t_rel, curr, color='#0284c7', linewidth=1.5, label='Corriente Total (A)')
    ax1.axhline(0, color='#64748b', linestyle='--', linewidth=0.8)
    ax1.set_ylabel('Corriente (A)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title(f'Perfil Energetico - Sensor Allegro ACS758LCB-050B (Robot Primario Chipo)\nArchivo: {os.path.basename(csv_path)}', fontsize=12, fontweight='bold', pad=10)
    ax1.grid(True, linestyle=':', alpha=0.6)
    ax1.legend(loc='upper right')

    # Subplot 2: Potencia
    ax2.set_facecolor('#f8fafc')
    ax2.plot(t_rel, power, color='#ea580c', linewidth=1.5, label='Potencia Instantanea (W @ 11.1V)')
    ax2.set_ylabel('Potencia (W)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.grid(True, linestyle=':', alpha=0.6)
    ax2.legend(loc='upper right')

    # Subplot 3: Carga acumulada
    ax3.set_facecolor('#f8fafc')
    ax3.plot(t_rel, mah, color='#7c3aed', linewidth=1.5, label='Carga Consumida (mAh)')
    ax3.set_xlabel('Tiempo de Mision (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax3.set_ylabel('Consumo (mAh)', fontsize=11, fontweight='bold', color='#1e293b')
    ax3.grid(True, linestyle=':', alpha=0.6)
    ax3.legend(loc='upper left')

    plt.tight_layout()
    out_png = csv_path.replace('.csv', '_analisis.png')
    plt.savefig(out_png, dpi=300)
    print(f"[+] Grafica guardada con calidad de publicacion en: {out_png}")
    plt.show()

if __name__ == '__main__':
    csv_f = select_csv_file()
    if csv_f:
        plot_current_data(csv_f)
