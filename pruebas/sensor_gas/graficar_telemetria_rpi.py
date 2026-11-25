"""
========================================================================================
Graficador Unificado de Archivos CSV (MQ-9, MiCS-5524 y Corriente ACS758)
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Permite seleccionar un unico archivo .csv (gas MQ-9, gas MiCS-5524 o corriente ACS758),
detecta automaticamente su formato por sus columnas y genera la grafica a 300 DPI.
========================================================================================
"""

import argparse
import csv
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


def select_csv_file(initial_dir):
    """Abre el explorador nativo para elegir un unico archivo .csv."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(
        title='Selecciona el archivo CSV a graficar (Gas MQ-9, MiCS-5524 o Corriente)',
        initialdir=str(initial_dir),
        filetypes=[('Archivos CSV (*.csv)', '*.csv'), ('Todos los archivos (*.*)', '*.*')],
    )
    root.destroy()
    return Path(file_path) if file_path else None


def _compute_relative_time_s(t_ms_list):
    t_arr = np.array(t_ms_list, dtype=float)
    if len(t_arr) == 0:
        return t_arr
    diffs = np.diff(t_arr, prepend=t_arr[0])
    diffs = np.where(diffs < 0, 50.0, diffs)
    return np.cumsum(diffs) / 1000.0


def find_top_peaks(values, freq, k=3):
    """Selecciona los k puntos mas altos evitando solapamiento temporal."""
    n = len(values)
    if n == 0 or np.max(values) <= 0.0:
        return []
    order = np.argsort(values)[::-1]
    for sep_s in (1.5, 0.4, 0.0):
        min_sep = max(1, int(round(freq * sep_s))) if sep_s > 0 else 1
        selected = []
        for idx in order:
            if values[idx] <= 0.0:
                continue
            if all(abs(int(idx) - int(s)) >= min_sep for s in selected):
                selected.append(int(idx))
                if len(selected) == k:
                    return selected
    return selected


def detect_csv_format(csv_path):
    """Detecta el formato del CSV segun los nombres de sus columnas."""
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = set(next(reader, []))
    if 'gas_v' in headers and 'tiempo_nano_ms' in headers:
        return 'mq9_rpi'
    if 'i_amp' in headers and 'tiempo_nano_ms' in headers:
        return 'corriente_rpi'
    if 'v_raw' in headers and 'rs_ohm' in headers:
        return 'mics5524'
    if 'Corriente_A' in headers and 'Tiempo_Relativo_s' in headers:
        return 'corriente_pc'
    return 'desconocido'


def load_mq9_csv(csv_path):
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


def load_mics_csv(csv_path):
    t_epoch, v_raw, v_med, v_ema, ratio_inv = [], [], [], [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t_epoch.append(float(row['timestamp_epoch']))
                v_raw.append(float(row['v_raw']))
                v_med.append(float(row['v_med']))
                v_ema.append(float(row['v_ema']))
                rs = float(row['rs_ohm'])
                r0 = float(row.get('r0_ohm', 10000.0))
                ratio_inv.append(r0 / max(1.0, rs))
            except (ValueError, KeyError):
                continue
    t_arr = np.array(t_epoch, dtype=float)
    t_s = (t_arr - t_arr[0]) if len(t_arr) > 0 else t_arr
    return {
        't_s': t_s,
        'v_raw': np.array(v_raw, dtype=float),
        'v_med': np.array(v_med, dtype=float),
        'v_ema': np.array(v_ema, dtype=float),
        'ratio_inv': np.array(ratio_inv, dtype=float),
    }


def load_current_rpi_csv(csv_path):
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


def load_current_pc_csv(csv_path):
    t_s, i_amp, pot_w, mah = [], [], [], []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t_s.append(float(row['Tiempo_Relativo_s']))
                i_amp.append(float(row['Corriente_A']))
                pot_w.append(float(row['Potencia_W']))
                mah.append(float(row['Consumo_mAh']))
            except (ValueError, KeyError):
                continue
    return {
        't_s': np.array(t_s, dtype=float),
        'i_amp': np.array(i_amp, dtype=float),
        'pot_w': np.array(pot_w, dtype=float),
        'mah': np.array(mah, dtype=float),
    }


def _annotate_peaks(ax1, ax2, t, y1, y2, top_peaks, unit1, unit2, fmt1='.1f', fmt2='.3f'):
    peak_colors = ['#dc2626', '#ea580c', '#9333ea']
    y_offsets = [(0, 12), (-38, 16), (12, 14)]

    y1_max = np.max(y1)
    y1_min = np.min(y1)
    span1 = max(y1_max - y1_min, 10.0 if unit1 == 'ppm' else 0.5)
    ax1.set_ylim(y1_min - 0.06 * span1, y1_max + 0.25 * span1)

    y2_max = np.max(y2)
    y2_min = np.min(y2)
    span2 = max(y2_max - y2_min, 0.05)
    ax2.set_ylim(y2_min - 0.10 * span2, y2_max + 0.28 * span2)

    for rank, idx in enumerate(top_peaks, start=1):
        col = peak_colors[rank - 1]
        ox, oy = y_offsets[rank - 1]
        ax1.axvline(t[idx], color=col, linestyle=':', linewidth=1.0, alpha=0.65)
        ax1.scatter(
            [t[idx]], [y1[idx]], color=col, s=55, zorder=6,
            edgecolors='#ffffff', linewidths=0.9,
            label=f'Pico #{rank}: {y1[idx]:{fmt1}} {unit1} ({y2[idx]:{fmt2}} {unit2})',
        )
        ax1.annotate(
            f'#{rank}: {y1[idx]:{fmt1}} {unit1}\n(t={t[idx]:.1f}s)',
            xy=(t[idx], y1[idx]), xytext=(ox, oy), textcoords='offset points',
            ha='center', fontsize=8.2, fontweight='bold', color=col,
            bbox=dict(boxstyle='round,pad=0.2', fc='#ffffff', ec=col, alpha=0.88),
            arrowprops=dict(arrowstyle='->', color=col, lw=1.0),
        )

        ax2.axvline(t[idx], color=col, linestyle=':', linewidth=1.0, alpha=0.65)
        ax2.scatter(
            [t[idx]], [y2[idx]], color=col, s=55, zorder=6,
            edgecolors='#ffffff', linewidths=0.9,
        )
        ax2.annotate(
            f'#{rank}: {y2[idx]:{fmt2}} {unit2}',
            xy=(t[idx], y2[idx]), xytext=(ox, oy), textcoords='offset points',
            ha='center', fontsize=8.2, fontweight='bold', color=col,
            bbox=dict(boxstyle='round,pad=0.2', fc='#ffffff', ec=col, alpha=0.88),
            arrowprops=dict(arrowstyle='->', color=col, lw=1.0),
        )


def plot_mq9(data, csv_path):
    t = data['t_s']
    n = len(t)
    if n == 0:
        print('[!] El archivo CSV de MQ-9 no contiene filas validas.')
        return None

    ppm = data['ppm_alc']
    v = data['gas_v']
    rs_r0 = data['rs_r0']
    alerta = data['alerta']

    dur = t[-1] - t[0] if n > 1 else 0.0
    freq = (n / dur) if dur > 0 else 0.0
    ppm_base = np.percentile(ppm, 10)
    top_peaks = find_top_peaks(ppm, freq, k=3)

    print('=' * 68)
    print(f' RESUMEN DE GAS MQ-9 ({csv_path.name})')
    print(f' - Muestras:          {n:,} puntos ({freq:.1f} Hz, {dur:.1f} s)')
    print(f' - Concentracion base:{ppm_base:8.2f} ppm')
    print(f' - Pico maximo:       {np.max(ppm):8.2f} ppm ({np.max(v):.3f} V)')
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

    ax1.set_facecolor('#f8fafc')
    ax1.plot(t, ppm, color='#0f766e', linewidth=1.8, label='Concentracion Etanol (ppm)')
    if np.any(alerta == 1):
        ax1.fill_between(
            t, 0, ppm, where=(alerta == 1), color='#ef4444', alpha=0.22,
            label='Alarma Digital D0 Activa',
        )
    ax1.axhline(ppm_base, color='#64748b', linestyle='--', linewidth=0.9,
                label=f'Linea base ({ppm_base:.1f} ppm)')
    ax1.set_ylabel('Concentracion (ppm)', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title(
        f'Monitoreo de Gas MQ-9 (Modelo Datasheet Wolkenstein) - {csv_path.parent.name}/{csv_path.name}',
        fontsize=12, fontweight='bold', pad=10,
    )
    ax1.grid(True, linestyle=':', alpha=0.65)

    ax2.set_facecolor('#f8fafc')
    l1 = ax2.plot(t, v, color='#0284c7', linewidth=1.6, label='Voltaje A0 (V)')
    ax2.set_xlabel('Tiempo de Medicion (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.set_ylabel('Voltaje Sensor (V)', fontsize=11, fontweight='bold', color='#0284c7')
    ax2.grid(True, linestyle=':', alpha=0.65)

    if top_peaks:
        _annotate_peaks(ax1, ax2, t, ppm, v, top_peaks, 'ppm', 'V')

    ax1.legend(loc='upper right', fontsize=8.5)

    ax2_r = ax2.twinx()
    l2 = ax2_r.plot(t, rs_r0, color='#d97706', linewidth=1.3, linestyle='-.', label='Ratio Rs/R0')
    ax2_r.set_ylabel('Ratio Rs / R0', fontsize=11, fontweight='bold', color='#d97706')

    lines = l1 + l2
    ax2.legend(lines, [ln.get_label() for ln in lines], loc='upper right', fontsize=8.5)

    plt.tight_layout()
    out_png = csv_path.with_name(f'{csv_path.stem}_grafica_mq9.png')
    plt.savefig(out_png, dpi=300)
    print(f'[+] Grafica guardada en: {out_png}')
    return fig


def plot_mics(data, csv_path):
    t = data['t_s']
    n = len(t)
    if n == 0:
        print('[!] El archivo CSV de MiCS-5524 no contiene filas validas.')
        return None

    v_raw = data['v_raw']
    v_med = data['v_med']
    v_ema = data['v_ema']
    ratio_inv = data['ratio_inv']

    dur = t[-1] - t[0] if n > 1 else 0.0
    freq = (n / dur) if dur > 0 else 0.0
    top_peaks = find_top_peaks(ratio_inv, freq, k=3)

    print('=' * 68)
    print(f' RESUMEN DE GAS MiCS-5524 ({csv_path.name})')
    print(f' - Muestras:          {n:,} puntos ({freq:.1f} Hz, {dur:.1f} s)')
    print(f' - Voltaje pico max:  {np.max(v_med):.3f} V (Ratio R0/Rs max: {np.max(ratio_inv):.2f}x)')
    if top_peaks:
        print(' - Top 3 picos detectados:')
        for rank, idx in enumerate(top_peaks, start=1):
            print(
                f'     #{rank}: R0/Rs={ratio_inv[idx]:.2f}x | {v_med[idx]:.3f} V '
                f'| t={t[idx]:.2f} s'
            )
    print('=' * 68)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.2), sharex=True)
    fig.patch.set_facecolor('#ffffff')

    ax1.set_facecolor('#f8fafc')
    ax1.plot(t, ratio_inv, color='#0f766e', linewidth=1.8, label='Proporcion R0 / Rs')
    ax1.axhline(1.0, color='#64748b', linestyle='--', linewidth=0.9, label='Aire limpio (1.0x)')
    ax1.set_ylabel('Ratio R0 / Rs', fontsize=11, fontweight='bold', color='#1e293b')
    ax1.set_title(
        f'Monitoreo de Gas MiCS-5524 - {csv_path.parent.name}/{csv_path.name}',
        fontsize=12, fontweight='bold', pad=10,
    )
    ax1.grid(True, linestyle=':', alpha=0.65)

    ax2.set_facecolor('#f8fafc')
    ax2.plot(t, v_raw, color='#94a3b8', linewidth=0.9, alpha=0.7, label='Voltaje Crudo (V)')
    ax2.plot(t, v_med, color='#0284c7', linewidth=1.6, label='Filtro Mediana N=5 (V)')
    ax2.plot(t, v_ema, color='#d97706', linewidth=1.4, linestyle='--', label='Filtro EMA (V)')
    ax2.set_xlabel('Tiempo de Medicion (segundos)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.set_ylabel('Voltaje Sensor (V)', fontsize=11, fontweight='bold', color='#1e293b')
    ax2.grid(True, linestyle=':', alpha=0.65)

    if top_peaks:
        _annotate_peaks(ax1, ax2, t, ratio_inv, v_med, top_peaks, 'x', 'V', fmt1='.2f', fmt2='.3f')

    ax1.legend(loc='upper right', fontsize=8.5)
    ax2.legend(loc='upper right', fontsize=8.5)

    plt.tight_layout()
    out_png = csv_path.with_name(f'{csv_path.stem}_grafica_mics.png')
    plt.savefig(out_png, dpi=300)
    print(f'[+] Grafica guardada en: {out_png}')
    return fig


def plot_current(data, csv_path):
    t = data['t_s']
    n = len(t)
    if n == 0:
        print('[!] El archivo CSV de corriente no contiene filas validas.')
        return None

    curr = data['i_amp']
    power = data['pot_w']
    mah = data['mah']

    dur = t[-1] - t[0] if n > 1 else 0.0
    print('=' * 68)
    print(f' RESUMEN DE CORRIENTE ACS758 ({csv_path.name})')
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
        f'Perfil Energetico ACS758LCB-050B (Chipo) - {csv_path.parent.name}/{csv_path.name}',
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
    out_png = csv_path.with_name(f'{csv_path.stem}_grafica_corriente.png')
    plt.savefig(out_png, dpi=300)
    print(f'[+] Grafica guardada en: {out_png}')
    return fig


def process_file(csv_path):
    fmt = detect_csv_format(csv_path)
    if fmt == 'mq9_rpi':
        return plot_mq9(load_mq9_csv(csv_path), csv_path)
    if fmt == 'mics5524':
        return plot_mics(load_mics_csv(csv_path), csv_path)
    if fmt == 'corriente_rpi':
        return plot_current(load_current_rpi_csv(csv_path), csv_path)
    if fmt == 'corriente_pc':
        return plot_current(load_current_pc_csv(csv_path), csv_path)
    print(f'[-] Formato CSV no reconocido en: {csv_path}')
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Graficador unico de CSVs (MQ-9, MiCS-5524 y Corriente ACS758)'
    )
    parser.add_argument('ruta', nargs='?', help='Ruta a un archivo .csv (o carpeta)')
    parser.add_argument('--no-show', action='store_true', help='Guardar PNGs sin abrir ventana')
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    default_base = repo_root / 'pruebas' / 'datos_mision' / 'datos_telemetria'
    if not default_base.exists():
        default_base = repo_root / 'pruebas' / 'datos_mision'

    if args.ruta:
        target = Path(args.ruta).resolve()
    else:
        target = select_csv_file(default_base)

    if not target or not target.exists():
        print('[-] No se selecciono ningun archivo valido.')
        return

    figs = []
    if target.is_file():
        fig = process_file(target)
        if fig is not None:
            figs.append(fig)
    elif target.is_dir():
        for name in ('gas.csv', 'corriente.csv'):
            candidate = target / name
            if candidate.exists():
                fig = process_file(candidate)
                if fig is not None:
                    figs.append(fig)
        if not figs:
            print(f'[-] No se encontro gas.csv ni corriente.csv dentro de: {target}')

    if figs and not args.no_show:
        plt.show()


if __name__ == '__main__':
    main()
