"""
========================================================================================
Graficador Analitico de Telemetria RPi 5 (Gas MQ-9 en PPM + Corriente ACS758)
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Lee los archivos gas.csv y corriente.csv generados en ~/datos_telemetria/
(carpetas ultima_medicion o medicion_anterior) y genera figuras a 300 DPI.
========================================================================================
"""

import argparse
import csv
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import warnings

warnings.filterwarnings('ignore')

import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'Segoe UI', 'Tahoma']
plt.rcParams['axes.edgecolor'] = '#cbd5e1'
plt.rcParams['axes.linewidth'] = 0.8


def select_measurement_dir(initial_dir):
    """Abre el explorador nativo para elegir ultima_medicion o medicion_anterior."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder = filedialog.askdirectory(
        title='Selecciona la carpeta de medicion (ultima_medicion o medicion_anterior)',
        initialdir=str(initial_dir),
    )
    root.destroy()
    return Path(folder) if folder else None


def _compute_relative_time_s(t_ms_list):
    t_arr = np.array(t_ms_list, dtype=float)
    if len(t_arr) == 0:
        return t_arr
    # Manejar posibles reinicios del contador millis() si ocurrieran
    diffs = np.diff(t_arr, prepend=t_arr[0])
    diffs = np.where(diffs < 0, 50.0, diffs)
    return np.cumsum(diffs) / 1000.0


def load_gas_csv(csv_path):
    t_ms, gas_v, gas_raw, ppm_alc, rs_r0, alerta = [], [], [], [], [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t_ms.append(float(row['tiempo_nano_ms']))
                gas_v.append(float(row['gas_v']))
                gas_raw.append(float(row['gas_raw']))
                ppm_val = row.get('ppm_alc') or row.get('gas_ratio') or '0'
                ppm_alc.append(float(ppm_val))
                rs_val = row.get('rs_r0') or '9.8'
                rs_r0.append(float(rs_val))
                alerta.append(int(float(row.get('gas_alerta', 0))))
            except (ValueError, KeyError):
                continue
    return {
        't_s': _compute_relative_time_s(t_ms),
        'gas_v': np.array(gas_v, dtype=float),
        'gas_raw': np.array(gas_raw, dtype=float),
        'ppm_alc': np.array(ppm_alc, dtype=float),
        'rs_r0': np.array(rs_r0, dtype=float),
        'alerta': np.array(alerta, dtype=int),
    }


def load_current_csv(csv_path):
    t_ms, i_amp, i_v, pot_w = [], [], [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t_ms.append(float(row['tiempo_nano_ms']))
                i_amp.append(float(row['i_amp']))
                i_v.append(float(row['i_v']))
                pot_w.append(float(row['pot_w']))
            except (ValueError, KeyError):
                continue
    t_s = _compute_relative_time_s(t_ms)
    i_arr = np.array(i_amp, dtype=float)
    # Carga acumulada en mAh mediante integracion trapezoidal: sum(I_avg * dt_horas * 1000)
    if len(t_s) > 1:
        dt_h = np.diff(t_s) / 3600.0
        i_mid = 0.5 * (i_arr[:-1] + i_arr[1:])
        mah = np.concatenate(([0.0], np.cumsum(i_mid * dt_h * 1000.0)))
    else:
        mah = np.zeros_like(i_arr)
    return {
        't_s': t_s,
        'i_amp': i_arr,
        'i_v': np.array(i_v, dtype=float),
        'pot_w': np.array(pot_w, dtype=float),
        'mah': mah,
    }


def find_top_peaks(ppm, freq, k=3):
    """Selecciona los k puntos mas altos evitando solapamiento temporal."""
    n = len(ppm)
    if n == 0 or np.max(ppm) <= 0.0:
        return []
    order = np.argsort(ppm)[::-1]
    for sep_s in (1.5, 0.4, 0.0):
        min_sep = max(1, int(round(freq * sep_s))) if sep_s > 0 else 1
        selected = []
        for idx in order:
            if ppm[idx] <= 0.0:
                continue
            if all(abs(int(idx) - int(s)) >= min_sep for s in selected):
                selected.append(int(idx))
                if len(selected) == k:
                    return selected
    return selected


def plot_gas(data, folder_path):
    t = data['t_s']
    n = len(t)
    if n == 0:
        print('[!] gas.csv no contiene filas validas.')
        return None

    ppm = data['ppm_alc']
    v = data['gas_v']
    rs_r0 = data['rs_r0']
    alerta = data['alerta']

    dur = t[-1] - t[0] if n > 1 else 0.0
    freq = (n / dur) if dur > 0 else 0.0
    ppm_base = np.percentile(ppm, 10)
    ppm_max = np.max(ppm)
    v_max = np.max(v)
    top_peaks = find_top_peaks(ppm, freq, k=3)

    print('=' * 68)
    print(f' RESUMEN DE GAS MQ-9 ({folder_path.name}/gas.csv)')
    print(f' - Muestras:          {n:,} puntos ({freq:.1f} Hz, {dur:.1f} s)')
    print(f' - Concentracion base:{ppm_base:8.2f} ppm')
    print(f' - Pico maximo:       {ppm_max:8.2f} ppm ({v_max:.3f} V)')
    print(f' - Muestras en alerta:{int(np.sum(alerta == 1))} puntos')
    if top_peaks:
        print(' - Top 3 picos detectados:')
        for rank, idx in enumerate(top_peaks, start=1):
            print(
                f'     #{rank}: {ppm[idx]:8.2f} ppm | {v[idx]:.3f} V '
                f'| Rs/R0={rs_r0[idx]:.2f} | t={t[idx]:.2f} s'
            )
    print('=' * 68)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True)
    fig.patch.set_facecolor('#ffffff')

    # Panel 1: Concentracion en PPM
    ax1.set_facecolor('#f8fafc')
    ax1.plot(t, ppm, color='#0f766e', linewidth=1.8, label='Concentracion Etanol (ppm)')
    if np.any(alerta == 1):
        ax1.fill_between(
            t, 0, ppm, where=(alerta == 1), color='#ef4444', alpha=0.22,
            label='Alarma Digital D0 Activa'
        )
    ax1.axhline(ppm_base, color='#64748b', linestyle='--', linewidth=0.9,
                label=f'Linea base ({ppm_base:.1f} ppm)')

    peak_colors = ['#dc2626', '#ea580c', '#9333ea']
    y_offsets_ppm = [(0, 12), (-38, 16), (12, 14)]
    y_offsets_v = [(0, 12), (-38, 14), (12, 14)]

    if top_peaks:
        y_top_pad = max(ppm_max * 1.18, 10.0)
        ax1.set_ylim(-0.04 * y_top_pad, y_top_pad)
        for rank, idx in enumerate(top_peaks, start=1):
            col = peak_colors[rank - 1]
            ax1.axvline(t[idx], color=col, linestyle=':', linewidth=1.0, alpha=0.65)
            ax1.scatter([t[idx]], [ppm[idx]], color=col, s=55, zorder=6, edgecolors='#ffffff',
                        linewidths=0.9, label=f'Pico #{rank}: {ppm[idx]:.1f} ppm ({v[idx]:.3f} V)')
            ox, oy = y_offsets_ppm[rank - 1]
            ax1.annotate(
                f'#{rank}: {ppm[idx]:.1f} ppm\n(t={t[idx]:.1f}s)',
                xy=(t[idx], ppm[idx]), xytext=(ox, oy), textcoords='offset points',
                ha='center', fontsize=8.2, fontweight='bold', color=col,
                bbox=dict(boxstyle='round,pad=0.2', fc='#ffffff', ec=col, alpha=0.88),
                arrowprops=dict(arrowstyle='->', color=col, lw=1.0),
            )

    ax1.set_ylabel('Concentracion (ppm)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title(
        f'Monitoreo de Gas MQ-9 (Modelo Datasheet Wolkenstein) - Carpeta: {folder_path.name}',
        fontsize=12, fontweight='bold', pad=10,
    )
    ax1.grid(True, linestyle=':', alpha=0.65)
    ax1.legend(loc='upper right', fontsize=8.5)

    # Panel 2: Voltaje A0 y Ratio Rs/R0
    ax2.set_facecolor('#f8fafc')
    l1 = ax2.plot(t, v, color='#0284c7', linewidth=1.6, label='Voltaje A0 (V)')
    if top_peaks:
        v_min_p, v_max_p = np.min(v), np.max(v)
        v_span = max(v_max_p - v_min_p, 0.05)
        ax2.set_ylim(v_min_p - 0.10 * v_span, v_max_p + 0.28 * v_span)
        for rank, idx in enumerate(top_peaks, start=1):
            col = peak_colors[rank - 1]
            ax2.axvline(t[idx], color=col, linestyle=':', linewidth=1.0, alpha=0.65)
            ax2.scatter([t[idx]], [v[idx]], color=col, s=55, zorder=6, edgecolors='#ffffff',
                        linewidths=0.9)
            ox, oy = y_offsets_v[rank - 1]
            ax2.annotate(
                f'#{rank}: {v[idx]:.3f} V',
                xy=(t[idx], v[idx]), xytext=(ox, oy), textcoords='offset points',
                ha='center', fontsize=8.2, fontweight='bold', color=col,
                bbox=dict(boxstyle='round,pad=0.2', fc='#ffffff', ec=col, alpha=0.88),
                arrowprops=dict(arrowstyle='->', color=col, lw=1.0),
            )

    ax2.set_xlabel('Tiempo de Medicion (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.set_ylabel('Voltaje Sensor (V)', fontsize=11, fontweight='bold', color='#0284c7')
    ax2.grid(True, linestyle=':', alpha=0.65)

    ax2_r = ax2.twinx()
    l2 = ax2_r.plot(t, rs_r0, color='#d97706', linewidth=1.3, linestyle='-.',
                    label='Ratio Rs/R0')
    ax2_r.set_ylabel('Ratio Rs / R0', fontsize=11, fontweight='bold', color='#d97706')

    lines = l1 + l2
    labels = [ln.get_label() for ln in lines]
    ax2.legend(lines, labels, loc='upper right', fontsize=8.5)

    plt.tight_layout()
    out_png = folder_path / 'grafica_gas_mq9.png'
    plt.savefig(out_png, dpi=300)
    print(f'[+] Grafica de gas guardada en: {out_png}')
    return fig


def plot_current(data, folder_path):
    t = data['t_s']
    n = len(t)
    if n == 0:
        print('[!] corriente.csv no contiene filas validas.')
        return None

    curr = data['i_amp']
    power = data['pot_w']
    mah = data['mah']

    dur = t[-1] - t[0] if n > 1 else 0.0
    print('=' * 68)
    print(f' RESUMEN DE CORRIENTE ACS758 ({folder_path.name}/corriente.csv)')
    print(f' - Muestras:          {n:,} puntos ({dur:.1f} s)')
    print(f' - Corriente promedio:{np.mean(curr):8.2f} A (Pico: {np.max(curr):.2f} A)')
    print(f' - Potencia promedio: {np.mean(power):8.2f} W (Pico: {np.max(power):.2f} W)')
    print(f' - Consumo acumulado: {mah[-1]:8.3f} mAh')
    print('=' * 68)

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(11, 8.0), sharex=True)
    fig.patch.set_facecolor('#ffffff')

    ax1.set_facecolor('#f8fafc')
    ax1.plot(t, curr, color='#0284c7', linewidth=1.5, label='Corriente Total (A)')
    ax1.axhline(0, color='#64748b', linestyle='--', linewidth=0.8)
    ax1.set_ylabel('Corriente (A)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title(
        f'Perfil Energetico ACS758LCB-050B (Chipo) - Carpeta: {folder_path.name}',
        fontsize=12, fontweight='bold', pad=10,
    )
    ax1.grid(True, linestyle=':', alpha=0.65)
    ax1.legend(loc='upper right', fontsize=9)

    ax2.set_facecolor('#f8fafc')
    ax2.plot(t, power, color='#ea580c', linewidth=1.5, label='Potencia Instantanea (W @ 11.1V)')
    ax2.set_ylabel('Potencia (W)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.grid(True, linestyle=':', alpha=0.65)
    ax2.legend(loc='upper right', fontsize=9)

    ax3.set_facecolor('#f8fafc')
    ax3.plot(t, mah, color='#7c3aed', linewidth=1.6, label='Carga Consumida (mAh)')
    ax3.set_xlabel('Tiempo de Medicion (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax3.set_ylabel('Consumo (mAh)', fontsize=11, fontweight='bold', color='#1e293b')
    ax3.grid(True, linestyle=':', alpha=0.65)
    ax3.legend(loc='upper left', fontsize=9)

    plt.tight_layout()
    out_png = folder_path / 'grafica_corriente_acs758.png'
    plt.savefig(out_png, dpi=300)
    print(f'[+] Grafica de corriente guardada en: {out_png}')
    return fig


def main():
    parser = argparse.ArgumentParser(description='Graficador de telemetria RPi (gas.csv y corriente.csv)')
    parser.add_argument('carpeta', nargs='?', help='Ruta a ultima_medicion o medicion_anterior')
    parser.add_argument('--no-show', action='store_true', help='Guardar PNGs sin abrir ventana')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    default_base = repo_root / 'pruebas' / 'datos_mision' / 'datos_telemetria'
    if not default_base.exists():
        default_base = repo_root / 'pruebas' / 'datos_mision'

    if args.carpeta:
        folder = Path(args.carpeta).resolve()
    else:
        folder = select_measurement_dir(default_base)

    if not folder or not folder.exists():
        print('[-] No se selecciono una carpeta valida.')
        return

    gas_csv = folder / 'gas.csv'
    cur_csv = folder / 'corriente.csv'
    if not gas_csv.exists() and not cur_csv.exists():
        print(f'[-] No se encontro gas.csv ni corriente.csv dentro de: {folder}')
        return

    figs = []
    if gas_csv.exists():
        fig_g = plot_gas(load_gas_csv(gas_csv), folder)
        if fig_g is not None:
            figs.append(fig_g)
    if cur_csv.exists():
        fig_c = plot_current(load_current_csv(cur_csv), folder)
        if fig_c is not None:
            figs.append(fig_c)

    if figs and not args.no_show:
        plt.show()


if __name__ == '__main__':
    main()
