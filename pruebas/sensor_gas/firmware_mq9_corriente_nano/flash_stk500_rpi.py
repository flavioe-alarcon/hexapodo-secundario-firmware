#!/usr/bin/env python3
"""
Programador STK500v1 (Optiboot @ 115200 baud) para Arduino Nano (ATmega328P)
conectado por USB (/dev/ttyUSB0) a la Raspberry Pi 5.
Incluye liberacion automatica y transparente del puerto si telemetria_nano (ROS 2)
lo tiene abierto en modo exclusivo, reanudando el nodo ROS 2 al finalizar.
"""

import os
import sys
import time
import signal
import subprocess
import serial


def load_intel_hex(hex_path, page_size=128):
    memory = {}
    max_addr = 0
    with open(hex_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line.startswith(':'):
                continue
            count = int(line[1:3], 16)
            addr = int(line[3:7], 16)
            rec_type = int(line[7:9], 16)
            data = bytes.fromhex(line[9:9 + count * 2])
            if rec_type == 0x00:
                for i, b in enumerate(data):
                    memory[addr + i] = b
                if addr + count > max_addr:
                    max_addr = addr + count
            elif rec_type == 0x01:
                break
    padded_len = ((max_addr + page_size - 1) // page_size) * page_size
    buf = bytearray([0xFF] * padded_len)
    for addr, b in memory.items():
        buf[addr] = b
    return bytes(buf)


def read_exact(ser, n):
    buf = bytearray()
    t0 = time.time()
    while len(buf) < n and (time.time() - t0) < 2.0:
        chunk = ser.read(n - len(buf))
        if chunk:
            buf.extend(chunk)
    return bytes(buf)


def expect_ok(ser, msg=""):
    resp = read_exact(ser, 2)
    if resp != b'\x14\x10':
        raise RuntimeError(f"Error STK500 en {msg}: esperado 0x14 0x10, recibido {resp.hex()}")


def get_telemetria_pid():
    try:
        out = subprocess.check_output(['pgrep', '-f', 'hexapodo_pkg/telemetria_nano'], text=True).strip()
        if out:
            return int(out.splitlines()[0])
    except Exception:
        pass
    return None


def sudo_sh(cmd):
    p = subprocess.Popen(
        ['sudo', '-S', 'sh', '-c', cmd],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    p.communicate('alesky69\n')


def flash_nano(port, hex_path, baud=115200):
    firmware = load_intel_hex(hex_path, page_size=128)
    print(f"[+] Firmware HEX cargado: {len(firmware)} bytes ({len(firmware)//128} paginas de 128 B)")

    nano_pid = get_telemetria_pid()
    usb_id = "4-2:1.0"
    try:
        if nano_pid:
            print(f"[+] Nodo ROS 2 telemetria_nano detectado (PID {nano_pid}). Liberando {port} temporalmente...")
            sudo_sh(f'echo "{usb_id}" > /sys/bus/usb/drivers/ftdi_sio/unbind')
            time.sleep(0.4)
            os.kill(nano_pid, signal.SIGSTOP)
            sudo_sh(f'echo "{usb_id}" > /sys/bus/usb/drivers/ftdi_sio/bind')
            time.sleep(0.6)
            print(f"[+] Puerto {port} liberado y telemetria_nano en pausa segura.")

        ser = serial.Serial(port, baud, timeout=0.5)
        try:
            synced = False
            for attempt in range(1, 6):
                ser.dtr = False
                ser.rts = False
                time.sleep(0.08)
                ser.dtr = True
                ser.rts = True
                time.sleep(0.08)
                ser.dtr = False
                ser.rts = False
                time.sleep(0.22)
                ser.reset_input_buffer()

                for _ in range(3):
                    ser.reset_input_buffer()
                    ser.write(b'\x30\x20')  # STK_GET_SYNC
                    resp = read_exact(ser, 2)
                    if resp == b'\x14\x10':
                        time.sleep(0.08)
                        ser.read(ser.in_waiting or 0)
                        ser.reset_input_buffer()
                        synced = True
                        break
                    time.sleep(0.05)
                if synced:
                    print(f"[+] Sincronizado con Optiboot en {port} (intento {attempt})")
                    break

            if not synced:
                raise RuntimeError("No se logro sincronizar con el bootloader Optiboot.")

            ser.write(b'\x50\x20')
            expect_ok(ser, "STK_ENTER_PROGMODE")

            ser.write(b'\x75\x20')
            sig_resp = read_exact(ser, 5)
            if sig_resp[:1] != b'\x14' or sig_resp[-1:] != b'\x10':
                raise RuntimeError(f"Respuesta de firma invalida: {sig_resp.hex()}")
            sig = sig_resp[1:4]
            print(f"[+] Firma del microcontrolador: {sig.hex().upper()} (ATmega328P)")
            if sig != b'\x1e\x95\x0f':
                raise RuntimeError(f"Firma inesperada: {sig.hex()}")

            total_pages = len(firmware) // 128
            for idx, byte_addr in enumerate(range(0, len(firmware), 128)):
                word_addr = byte_addr >> 1
                ser.write(bytes([0x55, word_addr & 0xFF, (word_addr >> 8) & 0xFF, 0x20]))
                expect_ok(ser, f"LOAD_ADDRESS write pag {idx}")

                page = firmware[byte_addr:byte_addr + 128]
                ser.write(bytes([0x64, 0x00, 0x80, ord('F')]) + page + b'\x20')
                expect_ok(ser, f"PROG_PAGE pag {idx}")

            print(f"[+] {len(firmware)} bytes escritos en Flash ({total_pages} paginas). Verificando...")

            for idx, byte_addr in enumerate(range(0, len(firmware), 128)):
                word_addr = byte_addr >> 1
                ser.write(bytes([0x55, word_addr & 0xFF, (word_addr >> 8) & 0xFF, 0x20]))
                expect_ok(ser, f"LOAD_ADDRESS verify pag {idx}")

                ser.write(bytes([0x74, 0x00, 0x80, ord('F'), 0x20]))
                resp = read_exact(ser, 130)
                if len(resp) != 130 or resp[0] != 0x14 or resp[-1] != 0x10:
                    raise RuntimeError(f"Fallo lectura en verificacion pag {idx}")
                if resp[1:129] != firmware[byte_addr:byte_addr + 128]:
                    raise RuntimeError(f"Mismatch de datos en pagina {idx}")

            print(f"[+] Verificacion 100% EXITOSA ({len(firmware)} bytes verificados).")

            ser.write(b'\x51\x20')
            expect_ok(ser, "STK_LEAVE_PROGMODE")

            print("[+] Esperando calibracion inicial en aire limpio del Arduino Nano...")
            ser.timeout = 2.0
            for _ in range(6):
                line = ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    print(f"    [NANO -> RPi] {line}")
        finally:
            ser.close()
    finally:
        if not os.path.exists(port):
            sudo_sh(f'echo "{usb_id}" > /sys/bus/usb/drivers/ftdi_sio/bind')
            time.sleep(0.5)
        if nano_pid:
            try:
                os.kill(nano_pid, signal.SIGCONT)
                print(f"[+] Nodo ROS 2 telemetria_nano (PID {nano_pid}) reanudado automaticamente.")
            except Exception:
                pass


if __name__ == '__main__':
    port_arg = sys.argv[1] if len(sys.argv) > 1 else '/dev/ttyUSB0'
    hex_arg = sys.argv[2] if len(sys.argv) > 2 else '/tmp/firmware_mq9_corriente_nano.ino.hex'
    flash_nano(port_arg, hex_arg)
