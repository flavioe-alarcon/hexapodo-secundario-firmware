@echo off
title Visor Integrado ESP32-S3 (Camara + Gas + Control de Luz LED)
echo ============================================================
echo  Iniciando Visor Integrado V8 con Control de Luz LED (WS2812)
echo  Tesis UTEC 2026 - Conecta tu laptop al Wi-Fi: ESP32S3-CAM
echo  Clave Wi-Fi: camara123
echo  IP ESP32-S3: 192.168.4.1
echo ============================================================
echo  Atajo de Luz: Presiona 'L' en la ventana para Encender/Apagar
echo ============================================================
cd /d "%~dp0"
python visor_integrado_con_luz.py http://192.168.4.1
pause
