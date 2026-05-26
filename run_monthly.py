#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para execução via GitHub Actions
Com suporte ao horário de Brasília (UTC-3)
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
import logging
import traceback

# Configurar diretório de trabalho para o local do script
script_dir = Path(__file__).parent.absolute()
os.chdir(script_dir)

# Configurar logging ANTES de qualquer import
log_dir = script_dir / 'logs'
log_dir.mkdir(exist_ok=True)

# Configurar fuso horário de Brasília (UTC-3)
class BrasiliaTime:
    @staticmethod
    def now():
        return datetime.now(timezone(timedelta(hours=-3)))
    
    @staticmethod
    def strftime(format_str):
        return BrasiliaTime.now().strftime(format_str)

# Usar horário de Brasília para logs
now_brasilia = BrasiliaTime.now()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / f'agendado_{now_brasilia.strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Horário de Brasília
    now_brasilia = BrasiliaTime.now()
    
    logger.info("="*60)
    logger.info("🚀 EXECUÇÃO VIA GITHUB ACTIONS - SÃO LEOPOLDO")
    logger.info(f"📅 Data/Hora (Brasília): {now_brasilia.strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info(f"📂 Diretório: {script_dir}")
    logger.info("="*60)
    
    try:
        # Importar após configurar diretório
        sys.path.insert(0, str(script_dir))
        from main import AutomatedDashboard
        
        # Instanciar e executar atualização completa
        dash = AutomatedDashboard()
        
        # Forçar download e processamento completos
        logger.info("📥 Iniciando atualização completa...")
        sucesso = dash.executar_atualizacao_completa()
        
        if sucesso:
            logger.info("✅ Execução concluída com sucesso!")
            logger.info(f"📁 Dashboard: {script_dir / 'dados' / 'index.html'}")
        else:
            logger.error("❌ Execução falhou!")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Erro na execução: {str(e)}")
        logger.error(traceback.format_exc())
        return 1
    
    logger.info("="*60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
