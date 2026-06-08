import pandas as pd
from pathlib import Path
import time
import sys
from datetime import datetime, timedelta
import json
import schedule
import logging
import io
import numpy as np
from scipy import stats as scipy_stats
import os
import requests
from bs4 import BeautifulSoup
import re

# Configurar encoding para UTF-8 no Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ============================================
# CONFIGURAÇÕES
# ============================================
PASTA_DOWNLOADS = Path.cwd() / 'downloads'
PASTA_DADOS = Path.cwd() / 'dados'
PASTA_LOGS = Path.cwd() / 'logs'
PASTA_CONFIG = Path.cwd() / 'config'

# URL da página com os links dos arquivos
URL_PAGINA = 'https://www.ssp.rs.gov.br/indicadores-da-violencia-contra-a-mulher'

# URL base para links relativos
URL_BASE = 'https://www.ssp.rs.gov.br'

# Anos desejados (2022 a 2026)
ANOS_DESEJADOS = ['2022', '2023', '2024', '2025', '2026']

# Indicadores a serem extraídos
INDICADORES = {
    'Feminicídio Consumado': 'Feminicídio Consumado',
    'Feminicídio Tentado': 'Feminicídio Tentado',
    'Ameaça': 'Ameaça',
    'Estupro': 'Estupro',
    'Lesão Corporal': 'Lesão Corporal'
}

def setup_logging():
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(PASTA_LOGS / f'auto_dashboard_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

class ConfigManager:
    def __init__(self):
        self.config_file = PASTA_CONFIG / 'config.json'
        PASTA_CONFIG.mkdir(parents=True, exist_ok=True)
        self.config = self.load_config()
    
    def load_config(self):
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'schedule': {
                'enabled': False,
                'interval_type': 'minutes',
                'interval_minutes': 30,
                'interval_hours': 1,
                'time': '09:00',
                'day_of_week': 'monday',
                'day_of_month': 4
            }
        }
    
    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        logger.info("Configurações salvas")

class LinkExtractor:
    """Classe para extrair links dos arquivos da página da SSP/RS"""
    
    def __init__(self):
        self.urls = {}
        self.base_url = URL_BASE
    
    def obter_links_da_pagina(self):
        """Faz scraping da página para obter todos os links dos arquivos Excel para os anos 2022-2026"""
        print("\n🔍 Buscando links na página da SSP/RS...")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = requests.get(URL_PAGINA, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscar em todas as tags <a> que contêm href com .xlsx
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '.xlsx' in href.lower():
                    # Extrair o texto do link
                    texto = link.get_text(strip=True)
                    
                    # Tentar extrair o ano do texto ou do href
                    ano = None
                    
                    # Padrões de busca de ano (apenas 2022-2026)
                    ano_match = re.search(r'\b(202[2-6])\b', texto)
                    if not ano_match:
                        ano_match = re.search(r'\b(202[2-6])\b', href)
                    
                    if ano_match:
                        ano = ano_match.group(1)
                        
                        # Construir URL completa se for relativa
                        if href.startswith('/'):
                            url_completa = self.base_url + href
                        elif href.startswith('http'):
                            url_completa = href
                        else:
                            url_completa = self.base_url + '/' + href
                        
                        # Se já temos um link para este ano, verificar se é mais recente
                        if ano not in self.urls:
                            self.urls[ano] = url_completa
                            print(f"   📎 Encontrado link para {ano}: {os.path.basename(url_completa)}")
            
            # Filtrar apenas os anos desejados
            self.urls = {ano: url for ano, url in self.urls.items() if ano in ANOS_DESEJADOS}
            
            # Ordenar por ano
            self.urls = dict(sorted(self.urls.items(), key=lambda x: int(x[0])))
            
            if self.urls:
                print(f"\n✅ Encontrados {len(self.urls)} links para os anos {', '.join(self.urls.keys())}")
                return True
            else:
                print(f"❌ Nenhum link encontrado para os anos {', '.join(ANOS_DESEJADOS)}")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao acessar página: {e}")
            print(f"❌ Erro ao acessar página: {e}")
            return False
    
    def get_urls(self):
        """Retorna os URLs extraídos"""
        if not self.urls:
            self.obter_links_da_pagina()
        return self.urls

class AutomatedDashboard:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.last_check_time = None
        self.link_extractor = LinkExtractor()
        self.urls = {}
        self.criar_pastas()
    
    def criar_pastas(self):
        for pasta in [PASTA_DOWNLOADS, PASTA_DADOS, PASTA_LOGS, PASTA_CONFIG]:
            pasta.mkdir(parents=True, exist_ok=True)
    
    def atualizar_links(self):
        """Atualiza os links dos arquivos a partir da página"""
        print("\n" + "="*60)
        print("🔍 ATUALIZANDO LINKS DOS ARQUIVOS")
        print("="*60)
        
        sucesso = self.link_extractor.obter_links_da_pagina()
        if sucesso:
            self.urls = self.link_extractor.get_urls()
            # Salvar links em um arquivo para referência
            links_path = PASTA_CONFIG / 'urls_encontradas.json'
            with open(links_path, 'w', encoding='utf-8') as f:
                json.dump(self.urls, f, indent=2, ensure_ascii=False)
            print(f"✅ Links salvos em {links_path}")
        return sucesso
    
    def baixar_arquivo(self, url, nome_arquivo, tentativas=3):
        for tentativa in range(tentativas):
            try:
                print(f"\n📥 Baixando {nome_arquivo}...")
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
                if response.status_code == 200:
                    caminho = PASTA_DOWNLOADS / nome_arquivo
                    with open(caminho, 'wb') as f:
                        f.write(response.content)
                    print(f"✅ {nome_arquivo} baixado! ({response.content.__sizeof__() / 1024:.1f} KB)")
                    return True
                else:
                    print(f"❌ Erro HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ Erro: {e}")
            if tentativa < tentativas - 1:
                print(f"   Tentando novamente em 5 segundos... (tentativa {tentativa + 2}/{tentativas})")
                time.sleep(5)
        return False
    
    def baixar_todos_arquivos(self):
        print("\n" + "="*60)
        print("🚀 INICIANDO DOWNLOAD DOS ARQUIVOS")
        print("="*60)
        
        # Primeiro, obter os links mais recentes
        if not self.urls:
            if not self.atualizar_links():
                print("❌ Não foi possível obter os links dos arquivos")
                return False
        
        sucessos = 0
        for ano, url in self.urls.items():
            nome_arquivo = f"violencia_mulheres_{ano}.xlsx"
            if self.baixar_arquivo(url, nome_arquivo):
                sucessos += 1
            time.sleep(2)
        
        print(f"\n📊 Download concluído: {sucessos}/{len(self.urls)} arquivos")
        return sucessos == len(self.urls)
    
    def extrair_indicador(self, arquivo_path, sheet_name):
        try:
            # Tentar diferentes linhas de cabeçalho
            for header_row in [2, 1, 0]:
                try:
                    df = pd.read_excel(arquivo_path, sheet_name=sheet_name, header=header_row)
                    
                    # Verificar se as colunas necessárias existem
                    colunas = [str(col).upper().strip() for col in df.columns]
                    
                    # Procurar por 'MUNICIPIO' e 'TOTAL'
                    municipio_col = None
                    total_col = None
                    
                    for i, col in enumerate(colunas):
                        if 'MUNICIP' in col or 'MUNICÍP' in col:
                            municipio_col = i
                        if 'TOTAL' in col:
                            total_col = i
                    
                    if municipio_col is not None and total_col is not None:
                        # Pegar a coluna real
                        col_municipio = df.columns[municipio_col]
                        col_total = df.columns[total_col]
                        
                        # Converter para string e limpar
                        df[col_municipio] = df[col_municipio].astype(str).str.upper().str.strip()
                        
                        # Buscar São Leopoldo
                        mascara = (df[col_municipio] == 'SAO LEOPOLDO') | (df[col_municipio] == 'SÃO LEOPOLDO')
                        if mascara.any():
                            valor = df.loc[mascara, col_total].iloc[0]
                            if pd.notna(valor):
                                # Converter para número
                                try:
                                    if isinstance(valor, str):
                                        # Remover caracteres não numéricos
                                        valor = re.sub(r'[^\d]', '', valor)
                                        return int(valor) if valor else 0
                                    return int(valor) if isinstance(valor, (int, float)) else 0
                                except:
                                    return 0
                except Exception as e:
                    continue
            return 0
        except Exception as e:
            logger.debug(f"Erro ao extrair indicador: {e}")
            return 0
    
    def extrair_dados_completos(self, arquivo_path, ano):
        dados_ano = {'Ano': ano}
        
        for indicador in INDICADORES.keys():
            dados_ano[indicador] = 0
        
        try:
            excel_file = pd.ExcelFile(arquivo_path)
            sheets_disponiveis = excel_file.sheet_names
            
            print(f"\n   Abas disponíveis: {', '.join(sheets_disponiveis[:5])}...")
            
            for indicador_nome, sheet_name in INDICADORES.items():
                if sheet_name in sheets_disponiveis:
                    valor = self.extrair_indicador(arquivo_path, sheet_name)
                    if valor is not None and valor > 0:
                        dados_ano[indicador_nome] = valor
                        print(f"   ✅ {indicador_nome}: {valor}")
                    else:
                        print(f"   ⚠️ {indicador_nome}: Não encontrado (valor: {valor})")
                else:
                    print(f"   ⚠️ Aba '{sheet_name}' não encontrada")
        except Exception as e:
            logger.error(f"Erro ao extrair {ano}: {e}")
        
        return dados_ano
    
    def processar_dados(self):
        print("\n" + "="*60)
        print("🎯 EXTRAINDO DADOS - SÃO LEOPOLDO")
        print("="*60)
        
        # Verificar se há arquivos baixados
        arquivos = sorted(PASTA_DOWNLOADS.glob('*.xlsx'))
        
        if not arquivos:
            print("📥 Nenhum arquivo encontrado. Baixando arquivos...")
            if not self.baixar_todos_arquivos():
                return None
            arquivos = sorted(PASTA_DOWNLOADS.glob('*.xlsx'))
        
        resultados = []
        print(f"📁 Encontrados {len(arquivos)} arquivos")
        
        for arquivo in arquivos:
            # Extrair ano do nome do arquivo
            ano = None
            for possivel_ano in ANOS_DESEJADOS:
                if possivel_ano in arquivo.name:
                    ano = int(possivel_ano)
                    break
            
            if ano is None:
                continue
            
            print(f"\n📊 Processando {arquivo.name} - Ano {ano}")
            resultado = self.extrair_dados_completos(arquivo, ano)
            resultados.append(resultado)
        
        if not resultados:
            print("❌ Nenhum dado extraído!")
            return None
        
        df = pd.DataFrame(resultados)
        df = df.sort_values('Ano')
        
        # Garantir que temos todos os anos de 2022 a 2026
        for ano in range(2022, 2027):
            if ano not in df['Ano'].values:
                print(f"⚠️ Ano {ano} não encontrado, adicionando com valores zerados")
                novo_registro = {'Ano': ano}
                for indicador in INDICADORES.keys():
                    novo_registro[indicador] = 0
                df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
        
        df = df.sort_values('Ano').reset_index(drop=True)
        
        print("\n📊 Dados extraídos com sucesso!")
        print(df.to_string(index=False))
        
        return df
    
    def salvar_dados(self, df):
        csv_path = PASTA_DADOS / 'indicadores_sao_leopoldo.csv'
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        excel_path = PASTA_DADOS / 'indicadores_sao_leopoldo.xlsx'
        df.to_excel(excel_path, index=False)
        
        json_path = PASTA_DADOS / 'indicadores_sao_leopoldo.json'
        df.to_json(json_path, orient='records', indent=2, force_ascii=False)
        
        logger.info("Dados salvos em todos os formatos")
        print(f"\n💾 Dados salvos em:")
        print(f"   - {csv_path}")
        print(f"   - {excel_path}")
        print(f"   - {json_path}")
    
    def calcular_estatisticas(self, df):
        stats = {}
        for indicador in INDICADORES.keys():
            valores = df[indicador].dropna().tolist()
            if len(valores) > 0:
                valores_numericos = [float(v) for v in valores if v is not None]
                if len(valores_numericos) > 0:
                    stats[indicador] = {
                        'total': sum(valores_numericos),
                        'media': round(np.mean(valores_numericos), 1),
                        'mediana': round(np.median(valores_numericos), 1),
                        'minimo': min(valores_numericos),
                        'maximo': max(valores_numericos),
                        'desvio_padrao': round(np.std(valores_numericos), 1),
                        'tendencia': 'crescente' if valores_numericos[-1] > valores_numericos[0] else 'decrescente' if valores_numericos[-1] < valores_numericos[0] else 'estavel'
                    }
                    if len(valores_numericos) >= 2:
                        x = np.arange(len(valores_numericos))
                        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, valores_numericos)
                        stats[indicador]['projecao_2026'] = round(intercept + slope * len(valores_numericos), 1)
                        stats[indicador]['projecao_2027'] = round(intercept + slope * (len(valores_numericos) + 1), 1)
        return stats
    
    def executar_atualizacao_completa(self):
        """Executa atualização completa (busca links + download + processamento)"""
        print("\n🔄 EXECUTANDO ATUALIZAÇÃO COMPLETA...")
        
        # Atualizar links da página
        print("🔍 Buscando links mais recentes...")
        self.atualizar_links()
        
        # Forçar novo download
        print("📥 Baixando arquivos mais recentes...")
        self.baixar_todos_arquivos()
        
        # Processar dados
        df = self.processar_dados()
        if df is None:
            print("❌ Falha ao processar dados")
            return False
        
        # Salvar dados
        self.salvar_dados(df)
        
        # Gerar dashboard com timestamp atual
        check_time = datetime.now()
        self.gerar_dashboard(df, check_time)
        
        print(f"✅ Atualização concluída em {check_time.strftime('%d/%m/%Y %H:%M:%S')}")
        return True
    
    def gerar_dashboard(self, df, check_time):
        """Gera o dashboard HTML completo"""
        
        # Preparar dados JSON
        dados_json = []
        for _, row in df.iterrows():
            dados_json.append({
                'ano': int(row['Ano']),
                'feminicidio_consumado': int(row['Feminicídio Consumado']) if pd.notna(row['Feminicídio Consumado']) else 0,
                'feminicidio_tentado': int(row['Feminicídio Tentado']) if pd.notna(row['Feminicídio Tentado']) else 0,
                'ameaca': int(row['Ameaça']) if pd.notna(row['Ameaça']) else 0,
                'estupro': int(row['Estupro']) if pd.notna(row['Estupro']) else 0,
                'lesao_corporal': int(row['Lesão Corporal']) if pd.notna(row['Lesão Corporal']) else 0
            })
        
        stats = self.calcular_estatisticas(df)
        
        totais = {
            'feminicidio_total': sum(d['feminicidio_consumado'] for d in dados_json),
            'feminicidio_tentado_total': sum(d['feminicidio_tentado'] for d in dados_json),
            'ameaca_total': sum(d['ameaca'] for d in dados_json),
            'estupro_total': sum(d['estupro'] for d in dados_json),
            'lesao_total': sum(d['lesao_corporal'] for d in dados_json),
            'total_geral': sum(d['feminicidio_consumado'] + d['feminicidio_tentado'] + d['ameaca'] + d['estupro'] + d['lesao_corporal'] for d in dados_json)
        }
        
        feminicidio_stats = stats.get('Feminicídio Consumado', {})
        projecao_2026 = feminicidio_stats.get('projecao_2026', dados_json[-1]['feminicidio_consumado'] if dados_json else 0)
        projecao_2027 = feminicidio_stats.get('projecao_2027', dados_json[-1]['feminicidio_consumado'] if dados_json else 0)
        tendencia = feminicidio_stats.get('tendencia', 'estavel')
        media_anual = feminicidio_stats.get('media', 0)
        
        # Gerar HTML
        html = self._gerar_html_completo(dados_json, totais, projecao_2026, projecao_2027, tendencia, media_anual, check_time, df)
        
        html_path = Path('index.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"\n✅ Dashboard gerado: {html_path.absolute()}")
        return html_path
    
    def _gerar_html_completo(self, dados_json, totais, projecao_2026, projecao_2027, tendencia, media_anual, check_time, df):
        """Gera o HTML completo do dashboard"""
        
        # Preparar dados para a tabela
        tabela_rows = ""
        for i, row in df.iterrows():
            total = sum([
                row['Feminicídio Consumado'] if pd.notna(row['Feminicídio Consumado']) else 0,
                row['Feminicídio Tentado'] if pd.notna(row['Feminicídio Tentado']) else 0,
                row['Ameaça'] if pd.notna(row['Ameaça']) else 0,
                row['Estupro'] if pd.notna(row['Estupro']) else 0,
                row['Lesão Corporal'] if pd.notna(row['Lesão Corporal']) else 0
            ])
            
            variacao_html = '-'
            if i > 0:
                total_ant = sum([
                    df.iloc[i-1]['Feminicídio Consumado'] if pd.notna(df.iloc[i-1]['Feminicídio Consumado']) else 0,
                    df.iloc[i-1]['Feminicídio Tentado'] if pd.notna(df.iloc[i-1]['Feminicídio Tentado']) else 0,
                    df.iloc[i-1]['Ameaça'] if pd.notna(df.iloc[i-1]['Ameaça']) else 0,
                    df.iloc[i-1]['Estupro'] if pd.notna(df.iloc[i-1]['Estupro']) else 0,
                    df.iloc[i-1]['Lesão Corporal'] if pd.notna(df.iloc[i-1]['Lesão Corporal']) else 0
                ])
                if total_ant > 0:
                    pct = ((total - total_ant) / total_ant) * 100
                    cor = '#ff6b6b' if pct > 0 else '#48c774'
                    sinal = '+' if pct > 0 else ''
                    variacao_html = f'<span style="color:{cor}">{sinal}{pct:.1f}%</span>'
            
            tabela_rows += f'''
            <tr>
                <td><strong>{int(row['Ano'])}</strong></td>
                <td>{int(row['Feminicídio Consumado']) if pd.notna(row['Feminicídio Consumado']) else 0}</td>
                <td>{int(row['Feminicídio Tentado']) if pd.notna(row['Feminicídio Tentado']) else 0}</td>
                <td>{int(row['Ameaça']) if pd.notna(row['Ameaça']) else 0:,}</td>
                <td>{int(row['Estupro']) if pd.notna(row['Estupro']) else 0}</td>
                <td>{int(row['Lesão Corporal']) if pd.notna(row['Lesão Corporal']) else 0:,}</td>
                <td><strong>{total:,}</strong></td>
                <td>{variacao_html}</td>
            </tr>'''
        
        html = f'''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard de Monitoramento | Violência Contra Mulheres - São Leopoldo</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); padding: 20px; min-height: 100vh; }}
        .dashboard {{ max-width: 1600px; margin: 0 auto; }}
        .header {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 25px; padding: 30px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.2); }}
        .header h1 {{ font-size: 2.5em; background: linear-gradient(135deg, #fff 0%, #a8c0ff 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 10px; }}
        .header .subtitle {{ color: rgba(255,255,255,0.7); font-size: 1.1em; }}
        .update-info {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); }}
        .update-time {{ background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 50px; display: inline-flex; align-items: center; gap: 10px; }}
        .update-time i {{ color: #48c774; }}
        .refresh-btn {{ background: linear-gradient(135deg, #667eea, #764ba2); border: none; padding: 10px 25px; border-radius: 50px; color: white; font-weight: 600; cursor: pointer; transition: all 0.3s; position: relative; overflow: hidden; }}
        .refresh-btn:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
        .refresh-btn.loading {{ opacity: 0.7; cursor: wait; }}
        .refresh-btn.loading::after {{
            content: '';
            position: absolute;
            width: 16px;
            height: 16px;
            top: 50%;
            left: 50%;
            margin-top: -8px;
            margin-left: -8px;
            border: 2px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        .notification {{
            position: fixed;
            top: 20px;
            right: 20px;
            background: #48c774;
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }}
        .notification.error {{ background: #ff6b6b; }}
        @keyframes slideIn {{
            from {{ transform: translateX(100%); opacity: 0; }}
            to {{ transform: translateX(0); opacity: 1; }}
        }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 25px; }}
        .stat-card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; transition: all 0.3s; cursor: pointer; border: 1px solid rgba(255,255,255,0.1); }}
        .stat-card:hover {{ transform: translateY(-5px); background: rgba(255,255,255,0.15); }}
        .stat-card .icon {{ font-size: 2em; margin-bottom: 15px; }}
        .stat-card h3 {{ color: rgba(255,255,255,0.7); font-size: 0.85em; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }}
        .stat-card .value {{ font-size: 2.5em; font-weight: 800; color: white; margin-bottom: 5px; }}
        .insights-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 25px; }}
        .insight-card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .insight-card h4 {{ color: white; margin-bottom: 15px; font-size: 1em; display: flex; align-items: center; gap: 10px; }}
        .insight-value {{ font-size: 1.8em; font-weight: 700; color: #667eea; }}
        .insight-label {{ color: rgba(255,255,255,0.6); font-size: 0.85em; }}
        .filters-section {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }}
        .filters-title {{ color: white; margin-bottom: 15px; font-size: 1.2em; display: flex; align-items: center; gap: 10px; }}
        .filter-group {{ display: inline-block; margin-right: 20px; margin-bottom: 10px; }}
        .filter-group label {{ display: block; color: rgba(255,255,255,0.7); font-size: 0.85em; margin-bottom: 5px; }}
        .filter-group select {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); padding: 10px 15px; border-radius: 10px; color: white; cursor: pointer; font-family: 'Inter', sans-serif; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 25px; margin-bottom: 25px; }}
        .chart-card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .chart-card h3 {{ color: white; margin-bottom: 15px; font-size: 1.2em; display: flex; align-items: center; gap: 10px; }}
        .chart-container {{ position: relative; height: 400px; }}
        .table-container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 25px; overflow-x: auto; }}
        .table-container h3 {{ color: white; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 12px; text-align: center; font-weight: 600; }}
        td {{ padding: 10px; text-align: center; color: white; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .footer {{ background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; text-align: center; color: rgba(255,255,255,0.5); font-size: 0.85em; }}
        .btn-export {{ background: linear-gradient(135deg, #48c774, #3a8e5e); border: none; padding: 8px 20px; border-radius: 10px; color: white; cursor: pointer; margin-left: 10px; }}
        @media (max-width: 768px) {{ .charts-grid {{ grid-template-columns: 1fr; }} .stats-grid {{ grid-template-columns: 1fr; }} .header h1 {{ font-size: 1.5em; }} }}
    </style>
</head>
<body>
<div class="dashboard">
    <div class="header">
        <h1><i class="fas fa-chart-line"></i> Violência Contra Mulheres</h1>
        <div class="subtitle">Dashboard Interativo de Monitoramento | São Leopoldo - RS</div>
        <div class="update-info">
            <div class="update-time"><i class="fas fa-clock"></i><span id="lastUpdateTime">Última atualização: {check_time.strftime('%d/%m/%Y às %H:%M:%S')}</span></div>
            <div>
                <button class="refresh-btn" id="btnAtualizar" onclick="executarAtualizacao()"><i class="fas fa-sync-alt"></i> Atualizar Dados</button>
                <button class="btn-export" onclick="exportarCSV()"><i class="fas fa-file-csv"></i> Exportar CSV</button>
            </div>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card"><div class="icon"><i class="fas fa-gavel"></i></div><h3>⚖️ FEMINICÍDIO CONSUMADO</h3><div class="value" id="totalFeminicidio">{int(totais['feminicidio_total'])}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-exclamation-triangle"></i></div><h3>⚠️ FEMINICÍDIO TENTADO</h3><div class="value" id="totalFeminicidioTentado">{int(totais['feminicidio_tentado_total'])}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-comment-dots"></i></div><h3>💬 AMEAÇAS</h3><div class="value" id="totalAmeaca">{int(totais['ameaca_total']):,}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-shield-alt"></i></div><h3>🔞 ESTUPROS</h3><div class="value" id="totalEstupro">{int(totais['estupro_total'])}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-heart-broken"></i></div><h3>💔 LESÕES CORPORAIS</h3><div class="value" id="totalLesao">{int(totais['lesao_total']):,}</div></div>
    </div>
    
    <div class="insights-grid">
        <div class="insight-card"><h4><i class="fas fa-chart-simple"></i> Média Anual</h4><div class="insight-value" id="mediaAnual">{media_anual:.1f}</div><div class="insight-label">Feminicídios por ano</div></div>
        <div class="insight-card"><h4><i class="fas fa-trend-up"></i> Tendência</h4><div class="insight-value" id="tendencia">{tendencia.upper()}</div><div class="insight-label" id="tendenciaLabel">{'↑ Crescente' if tendencia == 'crescente' else '↓ Decrescente' if tendencia == 'decrescente' else '→ Estável'}</div></div>
        <div class="insight-card"><h4><i class="fas fa-calendar"></i> Projeção 2026</h4><div class="insight-value" id="projecao2026">{projecao_2026:.0f}</div><div class="insight-label">Feminicídios estimados</div></div>
        <div class="insight-card"><h4><i class="fas fa-chart-pie"></i> Total Geral</h4><div class="insight-value" id="totalGeral">{int(totais['total_geral']):,}</div><div class="insight-label">Casos registrados (2022-2026)</div></div>
    </div>
    
    <div class="filters-section">
        <div class="filters-title"><i class="fas fa-sliders-h"></i> Filtros Avançados</div>
        <div class="filter-group"><label>📅 Período</label><select id="anoFilter" onchange="aplicarFiltros()"><option value="all">Todos os anos</option><option value="2022">2022</option><option value="2023">2023</option><option value="2024">2024</option><option value="2025">2025</option><option value="2026">2026</option></select></div>
        <div class="filter-group"><label>📊 Tipo de Gráfico</label><select id="chartType" onchange="mudarTipoGrafico()"><option value="line">📈 Linha</option><option value="bar">📊 Barras</option></select></div>
    </div>
    
    <div class="charts-grid">
        <div class="chart-card"><h3><i class="fas fa-chart-line"></i> Evolução Temporal dos Indicadores</h3><div class="chart-container"><canvas id="evolutionChart"></canvas></div></div>
        <div class="chart-card"><h3><i class="fas fa-chart-pie"></i> Distribuição por Tipo de Violência</h3><div class="chart-container"><canvas id="distributionChart"></canvas></div></div>
    </div>
    
    <div class="charts-grid">
        <div class="chart-card"><h3><i class="fas fa-percent"></i> Variação Percentual Anual</h3><div class="chart-container"><canvas id="variationChart"></canvas></div></div>
        <div class="chart-card"><h3><i class="fas fa-chart-line"></i> Projeção para Próximos Anos</h3><div class="chart-container"><canvas id="projectionChart"></canvas></div></div>
    </div>
    
    <div class="table-container">
        <h3><i class="fas fa-table"></i> Dados Detalhados por Ano</h3>
        <table id="dataTable">
            <thead><tr><th>Ano</th><th>Feminicídio Consumado</th><th>Feminicídio Tentado</th><th>Ameaça</th><th>Estupro</th><th>Lesão Corporal</th><th>Total</th><th>Variação %</th></tr></thead>
            <tbody id="tableBody">'''
        
        for i, (_, row) in enumerate(df.iterrows()):
            total = sum([
                row['Feminicídio Consumado'] if pd.notna(row['Feminicídio Consumado']) else 0,
                row['Feminicídio Tentado'] if pd.notna(row['Feminicídio Tentado']) else 0,
                row['Ameaça'] if pd.notna(row['Ameaça']) else 0,
                row['Estupro'] if pd.notna(row['Estupro']) else 0,
                row['Lesão Corporal'] if pd.notna(row['Lesão Corporal']) else 0
            ])
            
            variacao_html = '-'
            if i > 0:
                total_ant = sum([
                    df.iloc[i-1]['Feminicídio Consumado'] if pd.notna(df.iloc[i-1]['Feminicídio Consumado']) else 0,
                    df.iloc[i-1]['Feminicídio Tentado'] if pd.notna(df.iloc[i-1]['Feminicídio Tentado']) else 0,
                    df.iloc[i-1]['Ameaça'] if pd.notna(df.iloc[i-1]['Ameaça']) else 0,
                    df.iloc[i-1]['Estupro'] if pd.notna(df.iloc[i-1]['Estupro']) else 0,
                    df.iloc[i-1]['Lesão Corporal'] if pd.notna(df.iloc[i-1]['Lesão Corporal']) else 0
                ])
                if total_ant > 0:
                    pct = ((total - total_ant) / total_ant) * 100
                    cor = '#ff6b6b' if pct > 0 else '#48c774'
                    sinal = '+' if pct > 0 else ''
                    variacao_html = f'<span style="color:{cor}">{sinal}{pct:.1f}%</span>'
            
            html += f'<tr><td><strong>{int(row["Ano"])}</strong></td><td>{int(row["Feminicídio Consumado"]) if pd.notna(row["Feminicídio Consumado"]) else "-"}</td><td>{int(row["Feminicídio Tentado"]) if pd.notna(row["Feminicídio Tentado"]) else "-"}</td><td>{int(row["Ameaça"]) if pd.notna(row["Ameaça"]) else "-"}</td><td>{int(row["Estupro"]) if pd.notna(row["Estupro"]) else "-"}</td><td>{int(row["Lesão Corporal"]) if pd.notna(row["Lesão Corporal"]) else "-"}</td><td><strong>{total}</strong></td><td>{variacao_html}</td></tr>'
        
        html += f'''
            </tbody>
        </table>
    </div>
    
    <div class="footer">
        <p><i class="fas fa-database"></i> Fonte: Secretaria de Segurança Pública do Rio Grande do Sul (SSP/RS)</p>
        <p><i class="fas fa-chart-line"></i> Dashboard gerado automaticamente | São Leopoldo - RS</p>
        <p><i class="fas fa-sync-alt"></i> Última atualização: {check_time.strftime('%d/%m/%Y %H:%M:%S')}</p>
    </div>
</div>

<script>
const dadosIniciais = {json.dumps(dados_json)};
let dados = [...dadosIniciais];
let evolutionChart, distributionChart, variationChart, projectionChart;

function mostrarNotificacao(mensagem, tipo = 'success') {{
    const notificacao = $(`<div class="notification ${{tipo === 'error' ? 'error' : ''}}">${{mensagem}}</div>`);
    $('body').append(notificacao);
    setTimeout(() => notificacao.fadeOut(300, () => notificacao.remove()), 3000);
}}

function initCharts() {{
    criarGraficoEvolucao();
    criarGraficoDistribuicao();
    criarGraficoVariacao();
    criarGraficoProjecao();
}}

function criarGraficoEvolucao() {{
    const ctx = document.getElementById('evolutionChart').getContext('2d');
    const anos = dados.map(d => d.ano);
    evolutionChart = new Chart(ctx, {{
        type: document.getElementById('chartType').value,
        data: {{
            labels: anos,
            datasets: [
                {{label: 'Feminicídio Consumado', data: dados.map(d => d.feminicidio_consumado), borderColor: '#e74c3c', backgroundColor: '#e74c3c20', borderWidth: 3, fill: true, tension: 0.4}},
                {{label: 'Feminicídio Tentado', data: dados.map(d => d.feminicidio_tentado), borderColor: '#e67e22', backgroundColor: '#e67e2220', borderWidth: 3, fill: true, tension: 0.4}},
                {{label: 'Ameaça', data: dados.map(d => d.ameaca), borderColor: '#f39c12', backgroundColor: '#f39c1220', borderWidth: 3, fill: true, tension: 0.4}},
                {{label: 'Estupro', data: dados.map(d => d.estupro), borderColor: '#3498db', backgroundColor: '#3498db20', borderWidth: 3, fill: true, tension: 0.4}},
                {{label: 'Lesão Corporal', data: dados.map(d => d.lesao_corporal), borderColor: '#9b59b6', backgroundColor: '#9b59b620', borderWidth: 3, fill: true, tension: 0.4}}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{legend: {{labels: {{color: 'white', font: {{size: 12}}}}}}}},
            scales: {{
                y: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}},
                x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}
            }}
        }}
    }});
}}

function criarGraficoDistribuicao() {{
    const ctx = document.getElementById('distributionChart').getContext('2d');
    const totais = {{
        'Feminicídio': dados.reduce((s,d) => s + d.feminicidio_consumado + d.feminicidio_tentado, 0),
        'Ameaça': dados.reduce((s,d) => s + d.ameaca, 0),
        'Estupro': dados.reduce((s,d) => s + d.estupro, 0),
        'Lesão Corporal': dados.reduce((s,d) => s + d.lesao_corporal, 0)
    }};
    distributionChart = new Chart(ctx, {{
        type: 'doughnut',
        data: {{
            labels: Object.keys(totais),
            datasets: [{{
                data: Object.values(totais),
                backgroundColor: ['#e74c3c', '#f39c12', '#3498db', '#9b59b6'],
                borderWidth: 0,
                hoverOffset: 15
            }}]
        }},
        options: {{responsive: true, maintainAspectRatio: false, plugins: {{legend: {{position: 'bottom', labels: {{color: 'white'}}}}}}}}
    }});
}}

function criarGraficoVariacao() {{
    const ctx = document.getElementById('variationChart').getContext('2d');
    const variacoes = [];
    for (let i = 1; i < dados.length; i++) {{
        const totalAtual = dados[i].feminicidio_consumado + dados[i].feminicidio_tentado + dados[i].ameaca + dados[i].estupro + dados[i].lesao_corporal;
        const totalAnterior = dados[i-1].feminicidio_consumado + dados[i-1].feminicidio_tentado + dados[i-1].ameaca + dados[i-1].estupro + dados[i-1].lesao_corporal;
        const variacao = totalAnterior > 0 ? ((totalAtual - totalAnterior) / totalAnterior * 100) : 0;
        variacoes.push({{ano: dados[i].ano, variacao: variacao}});
    }}
    
    variationChart = new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: variacoes.map(v => v.ano),
            datasets: [{{
                label: 'Variação %',
                data: variacoes.map(v => v.variacao),
                backgroundColor: variacoes.map(v => v.variacao >= 0 ? '#ff6b6b' : '#48c774'),
                borderRadius: 10
            }}]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{tooltip: {{callbacks: {{label: function(ctx) {{ return 'Variação: ' + ctx.raw.toFixed(1) + '%'; }}}}}}}},
            scales: {{
                y: {{ticks: {{color: 'white', callback: function(v) {{ return v + '%'; }}}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}},
                x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}
            }}
        }}
    }});
}}

function criarGraficoProjecao() {{
    const ctx = document.getElementById('projectionChart').getContext('2d');
    const anos = dados.map(d => d.ano);
    const valores = dados.map(d => d.feminicidio_consumado);
    const proj2026 = {projecao_2026};
    const proj2027 = {projecao_2027};
    
    projectionChart = new Chart(ctx, {{
        type: 'line',
        data: {{
            labels: [...anos, 2026, 2027],
            datasets: [
                {{label: 'Histórico', data: [...valores, null, null], borderColor: '#667eea', borderWidth: 3, fill: false, pointRadius: 6}},
                {{label: 'Projeção', data: [...Array(anos.length-1).fill(null), valores[valores.length-1], proj2026, proj2027], borderColor: '#ffd93d', borderWidth: 3, borderDash: [5, 5], fill: false, pointRadius: 6, pointStyle: 'triangle'}}
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{legend: {{labels: {{color: 'white'}}}}}},
            scales: {{
                y: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}},
                x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}
            }}
        }}
    }});
}}

function aplicarFiltros() {{
    const ano = document.getElementById('anoFilter').value;
    const dadosFiltrados = ano === 'all' ? dados : dados.filter(d => d.ano == ano);
    if(evolutionChart) {{
        evolutionChart.data.labels = dadosFiltrados.map(d => d.ano);
        evolutionChart.data.datasets[0].data = dadosFiltrados.map(d => d.feminicidio_consumado);
        evolutionChart.data.datasets[1].data = dadosFiltrados.map(d => d.feminicidio_tentado);
        evolutionChart.data.datasets[2].data = dadosFiltrados.map(d => d.ameaca);
        evolutionChart.data.datasets[3].data = dadosFiltrados.map(d => d.estupro);
        evolutionChart.data.datasets[4].data = dadosFiltrados.map(d => d.lesao_corporal);
        evolutionChart.update();
    }}
}}

function mudarTipoGrafico() {{
    if(evolutionChart) {{
        evolutionChart.config.type = document.getElementById('chartType').value;
        evolutionChart.update();
    }}
}}

function exportarCSV() {{
    let csv = 'Ano,Feminicídio Consumado,Feminicídio Tentado,Ameaça,Estupro,Lesão Corporal,Total\\n';
    dados.forEach(d => {{
        const total = d.feminicidio_consumado + d.feminicidio_tentado + d.ameaca + d.estupro + d.lesao_corporal;
        csv += `${{d.ano}},${{d.feminicidio_consumado}},${{d.feminicidio_tentado}},${{d.ameaca}},${{d.estupro}},${{d.lesao_corporal}},${{total}}\\n`;
    }});
    const blob = new Blob([csv], {{type: 'text/csv;charset=utf-8;'}});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'dashboard_sao_leopoldo.csv';
    link.click();
}}

window.onload = initCharts;
</script>
</body>
</html>'''
        
        return html
    
    def get_next_run_time(self):
        if not self.config['schedule']['enabled']:
            return None
        interval_type = self.config['schedule']['interval_type']
        if interval_type == 'minutes':
            return datetime.now() + timedelta(minutes=self.config['schedule']['interval_minutes'])
        elif interval_type == 'hourly':
            return datetime.now() + timedelta(hours=self.config['schedule']['interval_hours'])
        elif interval_type == 'daily':
            next_run = datetime.now()
            target_time = datetime.strptime(self.config['schedule']['time'], '%H:%M').time()
            next_run = next_run.replace(hour=target_time.hour, minute=target_time.minute, second=0)
            if next_run <= datetime.now():
                next_run += timedelta(days=1)
            return next_run
        elif interval_type == 'monthly':
            today = datetime.now()
            target_day = self.config['schedule']['day_of_month']
            target_time = datetime.strptime(self.config['schedule']['time'], '%H:%M').time()
            if today.day < target_day:
                next_run = today.replace(day=target_day, hour=target_time.hour, minute=target_time.minute, second=0)
            else:
                next_run = today.replace(day=1) + timedelta(days=32)
                next_run = next_run.replace(day=target_day, hour=target_time.hour, minute=target_time.minute, second=0)
            return next_run
        return datetime.now() + timedelta(days=1)
    
    def run_automated_task(self):
        logger.info("="*60)
        logger.info("Executando tarefa automatizada")
        logger.info(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)
        
        check_time = datetime.now()
        
        try:
            # Atualizar links antes de processar
            self.atualizar_links()
            
            df = self.processar_dados()
            if df is None:
                logger.error("Falha ao processar dados")
                return
            
            self.salvar_dados(df)
            dashboard_path = self.gerar_dashboard(df, check_time)
            logger.info(f"Dashboard atualizado: {check_time.strftime('%d/%m/%Y %H:%M:%S')}")
            logger.info("✅ Execução concluída com sucesso!")
            
        except Exception as e:
            logger.error(f"Erro na tarefa: {e}")
            import traceback
            traceback.print_exc()
    
    def setup_schedule(self):
        schedule.clear()
        if not self.config['schedule']['enabled']:
            logger.info("Agendamento desabilitado")
            return
        
        interval_type = self.config['schedule']['interval_type']
        
        if interval_type == 'minutes':
            minutes = self.config['schedule']['interval_minutes']
            schedule.every(minutes).minutes.do(self.run_automated_task)
            logger.info(f"✅ Agendado: A cada {minutes} minutos")
        elif interval_type == 'hourly':
            hours = self.config['schedule']['interval_hours']
            schedule.every(hours).hours.do(self.run_automated_task)
            logger.info(f"✅ Agendado: A cada {hours} hora(s)")
        elif interval_type == 'daily':
            time_str = self.config['schedule']['time']
            schedule.every().day.at(time_str).do(self.run_automated_task)
            logger.info(f"✅ Agendado: Diariamente às {time_str}")
        elif interval_type == 'monthly':
            def monthly_job():
                today = datetime.now()
                if today.day == self.config['schedule']['day_of_month']:
                    self.run_automated_task()
            time_str = self.config['schedule']['time']
            schedule.every().day.at(time_str).do(monthly_job)
            logger.info(f"✅ Agendado: Mensalmente no dia {self.config['schedule']['day_of_month']} às {time_str}")

def configurar_agendamento(dash):
    print("\n" + "="*60)
    print("⚙️ CONFIGURAÇÃO DE AGENDAMENTO")
    print("="*60)
    
    enable = input("\nHabilitar agendamento automático? (s/n): ").lower() == 's'
    dash.config['schedule']['enabled'] = enable
    
    if enable:
        print("\nTipo de intervalo:")
        print("1. Minutos (executar a cada X minutos)")
        print("2. Horas (executar a cada X horas)")
        print("3. Diário (executar em horário específico)")
        print("4. Mensal (executar em dia específico do mês)")
        
        choice = input("\nEscolha (1-4): ")
        
        if choice == '1':
            dash.config['schedule']['interval_type'] = 'minutes'
            minutes = int(input("Intervalo em minutos (ex: 30): "))
            dash.config['schedule']['interval_minutes'] = minutes
            print(f"\n✅ Configurado para executar a cada {minutes} minutos")
        elif choice == '2':
            dash.config['schedule']['interval_type'] = 'hourly'
            hours = int(input("Intervalo em horas (ex: 2): "))
            dash.config['schedule']['interval_hours'] = hours
            print(f"\n✅ Configurado para executar a cada {hours} hora(s)")
        elif choice == '3':
            dash.config['schedule']['interval_type'] = 'daily'
            time_str = input("Horário (HH:MM, ex: 09:00): ")
            dash.config['schedule']['time'] = time_str
            print(f"\n✅ Configurado para executar diariamente às {time_str}")
        elif choice == '4':
            dash.config['schedule']['interval_type'] = 'monthly'
            dia = int(input("Dia do mês (1-31, ex: 4): "))
            dash.config['schedule']['day_of_month'] = dia
            time_str = input("Horário (HH:MM, ex: 04:00): ")
            dash.config['schedule']['time'] = time_str
            print(f"\n✅ Configurado para executar mensalmente no dia {dia} às {time_str}")
    
    dash.config_manager.save_config()
    print("\n✅ Configurações salvas!")

def iniciar_servidor_api(dash):
    """Inicia um servidor simples para permitir atualização via botão"""
    from flask import Flask, jsonify, request
    import threading
    
    app = Flask(__name__)
    
    @app.route('/api/atualizar', methods=['POST', 'OPTIONS'])
    def atualizar():
        if request.method == 'OPTIONS':
            return jsonify({'status': 'ok'})
        try:
            dash.executar_atualizacao_completa()
            return jsonify({'success': True, 'message': 'Atualização concluída'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    
    @app.route('/api/status', methods=['GET'])
    def status():
        return jsonify({'status': 'online', 'last_update': dash.last_check_time})
    
    def run_server():
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("\n🌐 API Server rodando em http://127.0.0.1:5000")
    return server_thread

def main():
    dash = AutomatedDashboard()
    
    # Iniciar servidor API (para o botão de atualização)
    servidor_api = iniciar_servidor_api(dash)
    
    print("="*60)
    print("🎯 SISTEMA DE MONITORAMENTO - SÃO LEOPOLDO/RS")
    print("="*60)
    print("Versão: 5.0 (Scraping Dinâmico)")
    print("Município: São Leopoldo - RS")
    print("Período: 2022 a 2026")
    print(f"Fonte: {URL_PAGINA}")
    print("="*60)
    
    # Verificar dependências
    try:
        import bs4
        print("✅ BeautifulSoup4 instalado")
    except ImportError:
        print("❌ BeautifulSoup4 não instalado. Instalando...")
        os.system('pip install beautifulsoup4')
    
    # Criar dashboard inicial
    print("\n📊 Criando dashboard inicial...")
    dash.executar_atualizacao_completa()
    
    print(f"\n✨ Dashboard disponível em: {Path.cwd() / 'index.html'}")
    print(f"📁 Dados salvos em: {PASTA_DADOS}")
    
    while True:
        print("\n" + "="*60)
        print("MENU PRINCIPAL")
        print("="*60)
        print("1. Executar uma vez (buscar links + baixar + processar)")
        print("2. Configurar agendamento automático")
        print("3. Iniciar monitoramento contínuo")
        print("4. Ver status do agendamento")
        print("5. Atualizar links da página")
        print("6. Sair")
        
        opcao = input("\nEscolha (1-6): ").strip()
        
        if opcao == '1':
            dash.executar_atualizacao_completa()
            print(f"\n✅ Execução concluída!")
            print(f"📁 Dashboard: {Path.cwd() / 'index.html'}")
        elif opcao == '2':
            configurar_agendamento(dash)
        elif opcao == '3':
            if not dash.config['schedule']['enabled']:
                print("\n❌ Agendamento não configurado! Configure primeiro (opção 2)")
                continue
            
            dash.setup_schedule()
            next_run = dash.get_next_run_time()
            print(f"\n🔄 Monitoramento iniciado!")
            if next_run:
                print(f"📅 Próxima execução: {next_run.strftime('%d/%m/%Y às %H:%M:%S')}")
            
            cfg = dash.config['schedule']
            if cfg['interval_type'] == 'minutes':
                print(f"⏰ Frequência: A cada {cfg['interval_minutes']} minutos")
            elif cfg['interval_type'] == 'hourly':
                print(f"⏰ Frequência: A cada {cfg['interval_hours']} hora(s)")
            elif cfg['interval_type'] == 'daily':
                print(f"⏰ Horário: {cfg['time']}")
            elif cfg['interval_type'] == 'monthly':
                print(f"⏰ Mensal: Dia {cfg['day_of_month']} às {cfg['time']}")
            
            print("\n✨ Dashboard atualizado automaticamente")
            print("🔍 Pressione Ctrl+C para parar o monitoramento\n")
            
            try:
                while True:
                    schedule.run_pending()
                    time.sleep(10)
            except KeyboardInterrupt:
                print("\n\n⏹️ Monitoramento interrompido pelo usuário")
        elif opcao == '4':
            if dash.config['schedule']['enabled']:
                print("\n" + "="*60)
                print("STATUS DO AGENDAMENTO")
                print("="*60)
                print(f"✅ Habilitado: Sim")
                cfg = dash.config['schedule']
                if cfg['interval_type'] == 'minutes':
                    print(f"📊 Tipo: Minutos - A cada {cfg['interval_minutes']} minutos")
                elif cfg['interval_type'] == 'hourly':
                    print(f"📊 Tipo: Horas - A cada {cfg['interval_hours']} hora(s)")
                elif cfg['interval_type'] == 'daily':
                    print(f"📊 Tipo: Diário - {cfg['time']}")
                elif cfg['interval_type'] == 'monthly':
                    print(f"📊 Tipo: Mensal - Dia {cfg['day_of_month']} às {cfg['time']}")
                next_run = dash.get_next_run_time()
                if next_run:
                    print(f"📅 Próxima execução: {next_run.strftime('%d/%m/%Y às %H:%M:%S')}")
            else:
                print("\n❌ Agendamento desabilitado")
            print(f"\n📁 Dashboard: {Path.cwd() / 'index.html'}")
        elif opcao == '5':
            dash.atualizar_links()
        elif opcao == '6':
            print("\n👋 Encerrando o programa...")
            break
        else:
            print("\n❌ Opção inválida!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Programa interrompido")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
