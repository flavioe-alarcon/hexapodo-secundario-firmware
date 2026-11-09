@echo off
title Nodo Raspberry Pi 5 Simulado - Hexapodo Primario UTEC 2026
echo ============================================================
echo  Iniciando Nodo Raspberry Pi 5 Simulado en Laptop
echo  Tesis UTEC 2026 - Conecta tu laptop a: ESP32S3-CAM
echo  Clave Wi-Fi: camara123
echo  IP ESP32-S3: 192.168.4.1
echo ============================================================
cd /d "%~dp0"
python nodo_raspberry_simulado.py
pause
