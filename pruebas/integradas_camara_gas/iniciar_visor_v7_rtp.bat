@echo off
chcp 65001 > nul
title Visor UTEC 2026 - ESP32-S3 Camara UVC (RTP) & Gas (UDP)

echo =======================================================================
echo    SISTEMA DE INSPECCION ROBOTICA COOPERATIVA - UTEC 2026
echo    Visor V7: Protocolo RTP / UDP RFC 3550 + Packet Pacing
echo =======================================================================
echo.
echo Verificando conexion de red con el ESP32-S3 (192.168.4.1)...
ping -n 1 -w 1000 192.168.4.1 > nul
if errorlevel 1 (
    echo [AVISO] No se detecta respuesta ICMP inmediata en 192.168.4.1.
    echo Asegurate de estar conectado a la red Wi-Fi:
    echo   SSID:  ESP32S3-CAM
    echo   Clave: camara123
    echo.
) else (
    echo [OK] Conexion Wi-Fi con ESP32-S3 confirmada en 192.168.4.1.
    echo.
)

echo Iniciando Visor RTP / UDP en Python...
python "%~dp0visor_v7_rtp.py"

echo.
echo El visor se ha cerrado.
pause
