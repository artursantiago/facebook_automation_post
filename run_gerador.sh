#!/bin/bash

set -e

echo "🔧 Criando ambiente virtual..."
python3 -m venv venv

echo "📦 Ativando ambiente virtual..."
source venv/bin/activate

echo "📥 Instalando dependências..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🚀 Executando script..."
python scripts/gerador/gerar_imagens.py
