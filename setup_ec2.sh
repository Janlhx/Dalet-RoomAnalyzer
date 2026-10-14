#!/bin/bash
# ==============================================================================
# 🏛️ Dalet-RoomAnalyzer — Script de Instalación y Despliegue para AWS EC2 (Ubuntu)
# ==============================================================================
# Este script automatiza la configuración completa de una instancia EC2 en AWS Academy:
# 1. Configuración de memoria Swap (vital para evitar caídas de MongoDB/Orion en t2.micro/t3.small)
# 2. Instalación de Docker y Docker Compose v2
# 3. Instalación de Python 3 y dependencias del proyecto
# 4. Despliegue de la pila FIWARE (Mongo, Orion, IoT Agent JSON)
# ==============================================================================

set -e

echo "=========================================================="
echo "🚀 INICIANDO DESPLIEGUE DE DALET-ROOMANALYZER EN AWS EC2"
echo "=========================================================="

# 1. Actualización del sistema
echo "📦 1. Actualizando paquetes del sistema..."
sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release git python3-pip python3-venv htop

# 2. Configurar 2GB de Swap si no existe (indispensable para AWS Academy t2.micro / t3.small)
if [ $(swapon --show | wc -l) -eq 0 ]; then
    echo "💾 2. Creando 2GB de memoria Swap..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    echo "  ✅ Memoria Swap activada exitosamente."
else
    echo "  ℹ️ Memoria Swap ya configurada."
fi

# 3. Instalación oficial de Docker
echo "🐳 3. Instalando Docker y Docker Compose..."
if ! command -v docker &> /dev/null; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Agregar usuario actual al grupo docker
    sudo usermod -aG docker $USER
    echo "  ✅ Docker instalado correctamente."
else
    echo "  ℹ️ Docker ya se encuentra instalado."
fi

# Asegurar que el servicio docker esté iniciado
sudo systemctl enable docker
sudo systemctl start docker

# 4. Despliegue de contenedores FIWARE
echo "🏗️ 4. Levantando la infraestructura FIWARE..."
if [ -f "docker-compose.yml" ]; then
    sudo docker compose up -d
    echo "  ✅ Contenedores iniciados:"
    sudo docker compose ps
else
    echo "  ⚠️ No se encontró docker-compose.yml en el directorio actual. Asegúrate de ejecutar el script en la raíz del repositorio."
fi

echo "=========================================================="
echo "🎉 INSTALACIÓN COMPLETADA EXITOSAMENTE"
echo "=========================================================="
echo "👉 Siguientes pasos en tu instancia EC2:"
echo "   1. Aprovisionar servicio y sensor: python3 scripts/provision.py"
echo "   2. Enviar datos de prueba:          python3 scripts/simulator.py --once"
echo "   3. Verificar en Orion:             python3 scripts/verify_orion.py"
echo "=========================================================="
