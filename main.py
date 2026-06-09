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

URL_PAGINA = 'https://www.ssp.rs.gov.br/indicadores-da-violencia-contra-a-mulher'
URL_BASE = 'https://www.ssp.rs.gov.br'
ADMIN_URL = 'https://admin.ssp.rs.gov.br'

ANOS_DESEJADOS = ['2022', '2023', '2024', '2025', '2026']

INDICADORES = {
    'Feminicídio Consumado': 'Feminicídio Consumado',
    'Feminicídio Tentado': 'Feminicídio Tentado',
    'Ameaça': 'Ameaça',
    'Estupro': 'Estupro',
    'Lesão Corporal': 'Lesão Corporal'
}

MESES_COLUNAS = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

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
    def __init__(self):
        self.urls = {}
        self.base_url = URL_BASE
        self.admin_url = 'https://admin.ssp.rs.gov.br'
    
    def obter_links_da_pagina(self):
        print("\n🔍 Buscando links na página da SSP/RS...")
        
        for tentativa in range(1, 4):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0'
                }
                
                print(f"   Tentativa {tentativa}/3...")
                response = requests.get(URL_PAGINA, headers=headers, timeout=45)
                response.raise_for_status()
                response.encoding = 'utf-8'
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                todos_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '.xlsx' in href.lower():
                        texto = link.get_text(strip=True)
                        todos_links.append({'href': href, 'texto': texto, 'ano': None})
                        ano_match = re.search(r'\b(202[2-6])\b', texto)
                        if not ano_match:
                            ano_match = re.search(r'\b(202[2-6])\b', href)
                        if ano_match:
                            todos_links[-1]['ano'] = ano_match.group(1)
                
                for ano in ANOS_DESEJADOS:
                    links_do_ano = [l for l in todos_links if l['ano'] == ano]
                    if not links_do_ano:
                        continue
                    
                    link_escolhido = None
                    if ano == '2023':
                        for l in links_do_ano:
                            if 'janeiro-2026' in l['href'].lower() or 'janeiro-2026' in l['texto'].lower():
                                link_escolhido = l
                                break
                    if not link_escolhido and ano == '2023':
                        for l in links_do_ano:
                            if 'junho-2025' not in l['href'].lower():
                                link_escolhido = l
                                break
                    if not link_escolhido and links_do_ano:
                        link_escolhido = links_do_ano[0]
                    
                    if link_escolhido:
                        href = link_escolhido['href']
                        if href.startswith('/upload'):
                            url_completa = 'https://admin.ssp.rs.gov.br' + href
                        elif href.startswith('/'):
                            url_completa = URL_BASE + href
                        else:
                            url_completa = href
                        self.urls[ano] = url_completa
                        print(f"   📎 Encontrado link para {ano}: {os.path.basename(url_completa)}")
                
                self.urls = {ano: url for ano, url in self.urls.items() if ano in ANOS_DESEJADOS}
                self.urls = dict(sorted(self.urls.items(), key=lambda x: int(x[0])))
                
                print("\n📋 URLs encontradas:")
                for ano, url in self.urls.items():
                    print(f"   {ano}: {url}")
                
                if self.urls:
                    print(f"\n✅ Encontrados {len(self.urls)} links para os anos {', '.join(self.urls.keys())}")
                    return True
                else:
                    print(f"❌ Nenhum link encontrado para os anos {', '.join(ANOS_DESEJADOS)}")
                    return False
                    
            except requests.exceptions.Timeout:
                print(f"   ⏰ Timeout na tentativa {tentativa}")
                if tentativa < 3:
                    time.sleep(tentativa * 10)
            except requests.exceptions.ConnectionError as e:
                print(f"   🔌 Erro de conexão na tentativa {tentativa}: {e}")
                if tentativa < 3:
                    time.sleep(tentativa * 15)
            except Exception as e:
                logger.error(f"Erro na tentativa {tentativa}: {e}")
                if tentativa < 3:
                    time.sleep(tentativa * 10)
        
        print(f"❌ Falha após 3 tentativas")
        return False
    
    def get_urls(self):
        if not self.urls:
            self.obter_links_da_pagina()
        return self.urls

class MonthlyDataExtractor:
    def __init__(self):
        self.meses = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
    
    def _mes_abreviado(self, mes_nome):
        abreviacoes = {
            'Janeiro': 'JAN', 'Fevereiro': 'FEV', 'Março': 'MAR',
            'Abril': 'ABR', 'Maio': 'MAI', 'Junho': 'JUN',
            'Julho': 'JUL', 'Agosto': 'AGO', 'Setembro': 'SET',
            'Outubro': 'OUT', 'Novembro': 'NOV', 'Dezembro': 'DEZ'
        }
        return abreviacoes.get(mes_nome, mes_nome[:3].upper())
    
    def _normalizar_chave(self, indicador_nome):
        mapping = {
            'Feminicídio Consumado': 'feminicidio_consumado',
            'Feminicídio Tentado': 'feminicidio_tentado',
            'Ameaça': 'ameaca',
            'Estupro': 'estupro',
            'Lesão Corporal': 'lesao_corporal'
        }
        return mapping.get(indicador_nome, indicador_nome.lower().replace(' ', '_'))
    
    def _converter_para_numero(self, valor):
        try:
            if isinstance(valor, str):
                valor = re.sub(r'[^\d]', '', valor)
                return int(valor) if valor else 0
            return int(valor) if pd.notna(valor) else 0
        except:
            return 0


class AutomatedDashboard:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.last_check_time = None
        self.link_extractor = LinkExtractor()
        self.urls = {}
        self.criar_pastas()
        self.monthly_extractor = MonthlyDataExtractor()
        self.dados_mensais = {}

    def criar_pastas(self):
        for pasta in [PASTA_DOWNLOADS, PASTA_DADOS, PASTA_LOGS, PASTA_CONFIG]:
            pasta.mkdir(parents=True, exist_ok=True)

    def _converter_para_numero(self, valor):
        try:
            if isinstance(valor, str):
                valor = re.sub(r'[^\d]', '', valor)
                return int(valor) if valor else 0
            return int(valor) if pd.notna(valor) else 0
        except:
            return 0

    def extrair_dados_mensais_reais(self, arquivo_path, ano):
        """
        Extrai dados mês a mês diretamente das colunas Jan..Dez de cada aba.
        Retorna dict: { 'ameaca': [jan, fev, ..., dez], 'feminicidio_consumado': [...], ... }
        Meses sem dados (NaN) ficam como 0.
        """
        resultado = {
            'feminicidio_consumado': [0]*12,
            'feminicidio_tentado':   [0]*12,
            'ameaca':                [0]*12,
            'estupro':               [0]*12,
            'lesao_corporal':        [0]*12,
        }
        chave_map = {
            'Feminicídio Consumado': 'feminicidio_consumado',
            'Feminicídio Tentado':   'feminicidio_tentado',
            'Ameaça':                'ameaca',
            'Estupro':               'estupro',
            'Lesão Corporal':        'lesao_corporal',
        }
        try:
            excel_file = pd.ExcelFile(arquivo_path)
            for sheet_name, chave in chave_map.items():
                if sheet_name not in excel_file.sheet_names:
                    continue
                # Tentar header=2 primeiro, depois 1 e 0
                for header_row in [2, 1, 0]:
                    df = pd.read_excel(arquivo_path, sheet_name=sheet_name, header=header_row)
                    cols_upper = [str(c).strip().upper() for c in df.columns]
                    # Precisamos achar colunas Jan..Dez e coluna Município
                    mun_idx = next((i for i, c in enumerate(cols_upper) if 'MUNIC' in c), None)
                    mes_indices = []
                    for mes_abrev in MESES_COLUNAS:
                        idx = next((i for i, c in enumerate(cols_upper) if c == mes_abrev.upper()), None)
                        mes_indices.append(idx)
                    if mun_idx is None or all(i is None for i in mes_indices):
                        continue
                    # Procurar linha de São Leopoldo
                    col_municipio = df.columns[mun_idx]
                    linha_sl = None
                    for _, row in df.iterrows():
                        val = str(row[col_municipio]).upper().strip()
                        if 'SAO LEOPOLDO' in val or 'SÃO LEOPOLDO' in val:
                            linha_sl = row
                            break
                    if linha_sl is None:
                        continue
                    for m_idx, col_idx in enumerate(mes_indices):
                        if col_idx is None:
                            continue
                        valor = linha_sl[df.columns[col_idx]]
                        resultado[chave][m_idx] = self._converter_para_numero(valor) if pd.notna(valor) else 0
                    break  # header encontrado, sair do loop
        except Exception as e:
            logger.error(f"Erro ao extrair dados mensais reais de {ano}: {e}")
        return resultado

    def atualizar_links(self):
        print("\n" + "="*60)
        print("🔍 ATUALIZANDO LINKS DOS ARQUIVOS")
        print("="*60)
        sucesso = self.link_extractor.obter_links_da_pagina()
        if sucesso:
            self.urls = self.link_extractor.get_urls()
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
                    print(f"✅ {nome_arquivo} baixado! ({len(response.content) / 1024:.1f} KB)")
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
            for header_row in [2, 1, 0]:
                try:
                    df = pd.read_excel(arquivo_path, sheet_name=sheet_name, header=header_row)
                    colunas = [str(col).upper().strip() for col in df.columns]
                    municipio_col = None
                    total_col = None
                    for i, col in enumerate(colunas):
                        if 'MUNICIP' in col or 'MUNICÍP' in col:
                            municipio_col = i
                        if 'TOTAL' in col:
                            total_col = i
                    if municipio_col is not None and total_col is not None:
                        col_municipio = df.columns[municipio_col]
                        col_total = df.columns[total_col]
                        df[col_municipio] = df[col_municipio].astype(str).str.upper().str.strip()
                        mascara = (df[col_municipio] == 'SAO LEOPOLDO') | (df[col_municipio] == 'SÃO LEOPOLDO')
                        if mascara.any():
                            valor = df.loc[mascara, col_total].iloc[0]
                            if pd.notna(valor):
                                try:
                                    if isinstance(valor, str):
                                        valor = re.sub(r'[^\d]', '', valor)
                                        return int(valor) if valor else 0
                                    return int(valor) if isinstance(valor, (int, float)) else 0
                                except:
                                    return 0
                except Exception:
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
        arquivos = sorted(PASTA_DOWNLOADS.glob('*.xlsx'))
        if not arquivos:
            print("📥 Nenhum arquivo encontrado. Baixando arquivos...")
            if not self.baixar_todos_arquivos():
                return None
            arquivos = sorted(PASTA_DOWNLOADS.glob('*.xlsx'))
        resultados = []
        print(f"📁 Encontrados {len(arquivos)} arquivos")
        for arquivo in arquivos:
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

    def processar_dados_mensais(self):
        """Extrai dados mensais reais de cada arquivo baixado e salva em JSON."""
        print("\n" + "="*60)
        print("📊 EXTRAINDO DADOS MENSAIS REAIS")
        print("="*60)
        arquivos = sorted(PASTA_DOWNLOADS.glob('*.xlsx'))
        if not arquivos:
            print("❌ Nenhum arquivo encontrado em downloads/")
            return None

        todos_mensais = {}  # { ano: { indicador: [jan..dez] } }
        for arquivo in arquivos:
            ano = None
            for possivel_ano in ANOS_DESEJADOS:
                if possivel_ano in arquivo.name:
                    ano = int(possivel_ano)
                    break
            if ano is None:
                continue
            print(f"   📅 Extraindo mensais de {arquivo.name}...")
            mensais = self.extrair_dados_mensais_reais(arquivo, ano)
            todos_mensais[str(ano)] = mensais
            # Log resumo
            print(f"      Ameaça: {mensais['ameaca']}")

        json_path = PASTA_DADOS / 'indicadores_mensais_reais.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(todos_mensais, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Dados mensais reais salvos em {json_path}")
        return todos_mensais

    def _normalizar_chave_para_json(self, indicador_nome):
        mapping = {
            'Feminicídio Consumado': 'feminicidio_consumado',
            'Feminicídio Tentado': 'feminicidio_tentado',
            'Ameaça': 'ameaca',
            'Estupro': 'estupro',
            'Lesão Corporal': 'lesao_corporal'
        }
        return mapping.get(indicador_nome, indicador_nome.lower().replace(' ', '_'))
    
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
    
    def gerar_dashboard_anual(self, df, check_time):
        from datetime import datetime

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

        # ── Carregar dados mensais reais (gerados por processar_dados_mensais) ──
        # Estrutura: { "2026": { "ameaca": [52,44,48,61,0,...], ... }, ... }
        dados_mensais_reais = {}
        json_mensais_path = PASTA_DADOS / 'indicadores_mensais_reais.json'
        if json_mensais_path.exists():
            with open(json_mensais_path, 'r', encoding='utf-8') as f:
                dados_mensais_reais = json.load(f)

        # Para anos sem dados mensais reais, derivar do total anual ÷ 12 uniformemente
        # (fallback apenas para anos históricos onde não temos o arquivo detalhado)
        for d in dados_json:
            ano_str = str(d['ano'])
            if ano_str not in dados_mensais_reais:
                dados_mensais_reais[ano_str] = {
                    'feminicidio_consumado': [round(d['feminicidio_consumado'] / 12)] * 12,
                    'feminicidio_tentado':   [round(d['feminicidio_tentado'] / 12)] * 12,
                    'ameaca':                [round(d['ameaca'] / 12)] * 12,
                    'estupro':               [round(d['estupro'] / 12)] * 12,
                    'lesao_corporal':        [round(d['lesao_corporal'] / 12)] * 12,
                }

        # mes_max_dados: quantos meses têm dados reais em cada ano
        # Determinado pelos valores não-zero na série mensal
        mes_max_dados_py = {}
        for d in dados_json:
            ano_str = str(d['ano'])
            mensais = dados_mensais_reais.get(ano_str, {})
            ameaca_m = mensais.get('ameaca', [0]*12)
            # Último mês com dado > 0 (índice 0-based → +1 para numero do mês)
            ultimo_mes = 0
            for m in range(11, -1, -1):
                if ameaca_m[m] > 0:
                    ultimo_mes = m + 1
                    break
            # Se todos zero mas tem total anual, usar 12
            if ultimo_mes == 0 and d['ameaca'] > 0:
                ultimo_mes = 12
            mes_max_dados_py[d['ano']] = ultimo_mes if ultimo_mes > 0 else 12

        mes_max_dados_js = json.dumps(mes_max_dados_py)
        dados_mensais_js = json.dumps(dados_mensais_reais)

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
        tendencia = feminicidio_stats.get('tendencia', 'estavel')
        media_anual = feminicidio_stats.get('media', 0)

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
            tabela_rows += f"""
                    <tr>
                        <td><strong>{int(row['Ano'])}</strong>{' ⚠️' if int(row['Ano']) == 2026 else ''}</td>
                        <td>{int(row['Feminicídio Consumado']) if pd.notna(row['Feminicídio Consumado']) else 0}</td>
                        <td>{int(row['Feminicídio Tentado']) if pd.notna(row['Feminicídio Tentado']) else 0}</td>
                        <td>{int(row['Ameaça']) if pd.notna(row['Ameaça']) else 0:,}</td>
                        <td>{int(row['Estupro']) if pd.notna(row['Estupro']) else 0}</td>
                        <td>{int(row['Lesão Corporal']) if pd.notna(row['Lesão Corporal']) else 0:,}</td>
                        <td><strong>{total:,}</strong></td>
                        <td>{variacao_html}</td>
                    </tr>"""

        if tendencia == 'crescente':
            tendencia_label = '↑ Crescente'
        elif tendencia == 'decrescente':
            tendencia_label = '↓ Decrescente'
        else:
            tendencia_label = '→ Estável'

        html = f'''<!DOCTYPE html>
        <html lang="pt-br">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Dashboard | Violência Contra Mulheres - São Leopoldo</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"></script>
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
                .update-info {{ display: flex; justify-content: space-between; align-items: center; margin-top: 20px; padding-top: 20px; border-top: 1px solid rgba(255,255,255,0.1); flex-wrap: wrap; gap: 10px; }}
                .update-time {{ background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 50px; display: inline-flex; align-items: center; gap: 10px; }}
                .update-time i {{ color: #48c774; }}
                .refresh-btn {{ background: linear-gradient(135deg, #667eea, #764ba2); border: none; padding: 10px 25px; border-radius: 50px; color: white; font-weight: 600; cursor: pointer; transition: all 0.3s; }}
                .refresh-btn:hover {{ transform: translateY(-2px); box-shadow: 0 10px 25px rgba(0,0,0,0.3); }}
                .btn-export {{ background: linear-gradient(135deg, #48c774, #3a8e5e); border: none; padding: 8px 20px; border-radius: 10px; color: white; cursor: pointer; margin-left: 10px; }}
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
                .filters-section {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 25px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }}
                .filters-title {{ color: white; margin-bottom: 20px; font-size: 1.2em; display: flex; align-items: center; gap: 10px; }}
                .filters-tabs {{ display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }}
                .filter-tab {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); color: rgba(255,255,255,0.7); padding: 8px 18px; border-radius: 20px; cursor: pointer; font-size: 0.85em; transition: all 0.2s; font-family: 'Inter', sans-serif; }}
                .filter-tab.active {{ background: linear-gradient(135deg, #667eea, #764ba2); border-color: transparent; color: white; font-weight: 600; }}
                .filter-tab:hover:not(.active) {{ background: rgba(255,255,255,0.15); color: white; }}
                .filter-panel {{ display: none; }}
                .filter-panel.active {{ display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-end; }}
                .filter-group {{ display: flex; flex-direction: column; gap: 6px; }}
                .filter-group label {{ color: rgba(255,255,255,0.7); font-size: 0.82em; font-weight: 500; letter-spacing: 0.5px; }}
                .filter-group select {{ background: rgba(0,0,0,0.35); border: 1px solid rgba(255,255,255,0.2); padding: 9px 13px; border-radius: 10px; color: white; cursor: pointer; font-family: 'Inter', sans-serif; font-size: 0.9em; min-width: 110px; transition: border-color 0.2s; }}
                .filter-group select:focus {{ outline: none; border-color: #667eea; }}
                .filter-group select option {{ background: #302b63; color: white; }}
                .filter-sep {{ color: rgba(255,255,255,0.5); font-size: 0.85em; }}
                .btn-apply {{ background: linear-gradient(135deg, #667eea, #764ba2); border: none; padding: 9px 20px; border-radius: 10px; color: white; font-weight: 600; cursor: pointer; font-family: 'Inter', sans-serif; transition: all 0.2s; white-space: nowrap; }}
                .btn-apply:hover {{ opacity: 0.9; transform: translateY(-1px); box-shadow: 0 5px 15px rgba(102,126,234,0.4); }}
                .btn-clear {{ background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.2); padding: 9px 20px; border-radius: 10px; color: white; cursor: pointer; font-family: 'Inter', sans-serif; transition: all 0.2s; }}
                .btn-clear:hover {{ background: rgba(255,255,255,0.25); }}
                .filter-hint {{ font-size: 0.72em; color: rgba(255,255,255,0.45); margin-top: 6px; display: block; }}
                .indicadores-filter {{ display: flex; flex-wrap: wrap; gap: 8px; }}
                .ind-check {{ display: flex; align-items: center; gap: 6px; background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 6px 12px; cursor: pointer; transition: all 0.2s; }}
                .ind-check input[type=checkbox] {{ accent-color: #667eea; width: 14px; height: 14px; cursor: pointer; }}
                .ind-check label {{ color: rgba(255,255,255,0.75); font-size: 0.82em; cursor: pointer; white-space: nowrap; }}
                .ind-check.checked {{ border-color: rgba(102,126,234,0.6); background: rgba(102,126,234,0.15); }}
                .ind-check label span.dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; }}
                .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 25px; margin-bottom: 25px; }}
                .chart-card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }}
                .chart-card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 8px; }}
                .chart-card-header h3 {{ color: white; font-size: 1.1em; display: flex; align-items: center; gap: 10px; }}
                .chart-actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
                .chart-btn {{ background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.15); color: rgba(255,255,255,0.7); padding: 4px 10px; border-radius: 6px; cursor: pointer; font-size: 0.75em; font-family: 'Inter', sans-serif; transition: all 0.2s; }}
                .chart-btn:hover, .chart-btn.active {{ background: rgba(102,126,234,0.4); border-color: rgba(102,126,234,0.6); color: white; }}
                .chart-container {{ position: relative; height: 380px; }}
                .chart-container-tall {{ position: relative; height: 430px; }}
                .table-container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 25px; overflow-x: auto; }}
                .table-container h3 {{ color: white; margin-bottom: 15px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 12px; text-align: center; font-weight: 600; }}
                td {{ padding: 10px; text-align: center; color: white; border-bottom: 1px solid rgba(255,255,255,0.1); }}
                tr:hover {{ background: rgba(255,255,255,0.05); }}
                .footer {{ background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; text-align: center; color: rgba(255,255,255,0.5); font-size: 0.85em; }}
                .periodo-msg {{ background: rgba(102,126,234,0.3); padding: 10px 15px; border-radius: 10px; margin-bottom: 15px; text-align: center; color: white; }}
                .zoom-hint {{ font-size: 0.7em; color: rgba(255,255,255,0.35); margin-top: 6px; text-align: right; }}
                @media (max-width: 768px) {{ .charts-grid {{ grid-template-columns: 1fr; }} .stats-grid {{ grid-template-columns: 1fr 1fr; }} .header h1 {{ font-size: 1.5em; }} .filter-panel.active {{ flex-direction: column; }} }}
                @media (max-width: 480px) {{ .stats-grid {{ grid-template-columns: 1fr; }} }}
            </style>
        </head>
        <body>
        <div class="dashboard">
            <div class="header">
                <h1><i class="fas fa-chart-line"></i> Violência Contra Mulheres</h1>
                <div class="subtitle">Dashboard Interativo com Filtros | São Leopoldo - RS</div>
                <div class="update-info">
                    <div class="update-time"><i class="fas fa-clock"></i><span>Última atualização: {check_time.strftime('%d/%m/%Y às %H:%M:%S')}</span></div>
                    <div>
                        <button class="refresh-btn" onclick="location.reload()"><i class="fas fa-sync-alt"></i> Atualizar</button>
                        <button class="btn-export" onclick="exportarCSV()"><i class="fas fa-file-csv"></i> Exportar CSV</button>
                    </div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card"><div class="icon"><i class="fas fa-gavel"></i></div><h3>⚖️ FEMINICÍDIO CONSUMADO</h3><div class="value" id="totalFem">{int(totais['feminicidio_total'])}</div></div>
                <div class="stat-card"><div class="icon"><i class="fas fa-exclamation-triangle"></i></div><h3>⚠️ FEMINICÍDIO TENTADO</h3><div class="value" id="totalFemTent">{int(totais['feminicidio_tentado_total'])}</div></div>
                <div class="stat-card"><div class="icon"><i class="fas fa-comment-dots"></i></div><h3>💬 AMEAÇAS</h3><div class="value" id="totalAmeaca">{int(totais['ameaca_total']):,}</div></div>
                <div class="stat-card"><div class="icon"><i class="fas fa-shield-alt"></i></div><h3>🔞 ESTUPROS</h3><div class="value" id="totalEstupro">{int(totais['estupro_total'])}</div></div>
                <div class="stat-card"><div class="icon"><i class="fas fa-heart-broken"></i></div><h3>💔 LESÕES CORPORAIS</h3><div class="value" id="totalLesao">{int(totais['lesao_total']):,}</div></div>
            </div>

            <div class="insights-grid">
                <div class="insight-card"><h4><i class="fas fa-chart-simple"></i> Média Anual</h4><div class="insight-value" id="mediaAnual">{media_anual:.1f}</div><div class="insight-label">Feminicídios por ano</div></div>
                <div class="insight-card"><h4><i class="fas fa-trend-up"></i> Tendência</h4><div class="insight-value" id="tendencia">{tendencia.upper()}</div><div class="insight-label" id="tendenciaLabel">{tendencia_label}</div></div>
                <div class="insight-card"><h4><i class="fas fa-calendar"></i> Projeção 2026</h4><div class="insight-value" id="proj2026">{projecao_2026:.0f}</div><div class="insight-label">Feminicídios estimados</div></div>
                <div class="insight-card"><h4><i class="fas fa-chart-pie"></i> Total Geral</h4><div class="insight-value" id="totalGeral">{int(totais['total_geral']):,}</div><div class="insight-label">Casos registrados (2022-2026)</div></div>
            </div>

            <div class="filters-section">
                <div class="filters-title"><i class="fas fa-sliders-h"></i> Filtros Avançados</div>
                <div class="filters-tabs">
                    <button class="filter-tab active" onclick="trocarAba('anual', this)">📅 Por Ano</button>
                    <button class="filter-tab" onclick="trocarAba('mensal', this)">📆 Por Mês/Ano</button>
                    <button class="filter-tab" onclick="trocarAba('indicadores', this)">📊 Por Indicador</button>
                    <button class="filter-tab" onclick="trocarAba('visualizacao', this)">🎨 Visualização</button>
                </div>
                <div class="filter-panel active" id="panel-anual">
                    <div class="filter-group">
                        <label>Ano inicial</label>
                        <select id="anoInicio">
                            <option value="2022" selected>2022</option><option value="2023">2023</option>
                            <option value="2024">2024</option><option value="2025">2025</option><option value="2026">2026</option>
                        </select>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:9px"><span class="filter-sep">até</span></div>
                    <div class="filter-group">
                        <label>Ano final</label>
                        <select id="anoFim">
                            <option value="2022">2022</option><option value="2023">2023</option>
                            <option value="2024">2024</option><option value="2025">2025</option><option value="2026" selected>2026</option>
                        </select>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:2px">
                        <button class="btn-apply" onclick="aplicarFiltroAnual()"><i class="fas fa-check"></i> Aplicar</button>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:2px">
                        <button class="btn-clear" onclick="limparFiltros()"><i class="fas fa-times"></i> Limpar</button>
                    </div>
                </div>
                <div class="filter-panel" id="panel-mensal">
                    <div class="filter-group">
                        <label>Mês inicial</label>
                        <select id="mesInicio">
                            <option value="1">Janeiro</option><option value="2">Fevereiro</option><option value="3">Março</option>
                            <option value="4">Abril</option><option value="5">Maio</option><option value="6">Junho</option>
                            <option value="7">Julho</option><option value="8">Agosto</option><option value="9">Setembro</option>
                            <option value="10">Outubro</option><option value="11">Novembro</option><option value="12">Dezembro</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Ano inicial</label>
                        <select id="anoInicioMes">
                            <option value="2022" selected>2022</option><option value="2023">2023</option>
                            <option value="2024">2024</option><option value="2025">2025</option><option value="2026">2026</option>
                        </select>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:9px"><span class="filter-sep">até</span></div>
                    <div class="filter-group">
                        <label>Mês final</label>
                        <select id="mesFim">
                            <option value="1">Janeiro</option><option value="2">Fevereiro</option><option value="3">Março</option>
                            <option value="4">Abril</option><option value="5">Maio</option><option value="6">Junho</option>
                            <option value="7">Julho</option><option value="8">Agosto</option><option value="9">Setembro</option>
                            <option value="10">Outubro</option><option value="11">Novembro</option><option value="12" selected>Dezembro</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>Ano final</label>
                        <select id="anoFimMes">
                            <option value="2022">2022</option><option value="2023">2023</option>
                            <option value="2024">2024</option><option value="2025">2025</option><option value="2026" selected>2026</option>
                        </select>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:2px">
                        <button class="btn-apply" onclick="aplicarFiltroMensal()"><i class="fas fa-check"></i> Aplicar</button>
                        <span class="filter-hint">💡 Usa dados mensais reais da planilha</span>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:2px">
                        <button class="btn-clear" onclick="limparFiltros()"><i class="fas fa-times"></i> Limpar</button>
                    </div>
                </div>
                <div class="filter-panel" id="panel-indicadores">
                    <div class="filter-group" style="width:100%">
                        <label>Selecione os indicadores a exibir nos gráficos</label>
                        <div class="indicadores-filter" id="indicadoresCheckboxes">
                            <div class="ind-check checked" id="chk-feminicidio_consumado">
                                <input type="checkbox" id="cb-feminicidio_consumado" checked onchange="atualizarVisibildadeIndicador('feminicidio_consumado', this.checked)">
                                <label for="cb-feminicidio_consumado"><span class="dot" style="background:#e74c3c"></span>Feminicídio Consumado</label>
                            </div>
                            <div class="ind-check checked" id="chk-feminicidio_tentado">
                                <input type="checkbox" id="cb-feminicidio_tentado" checked onchange="atualizarVisibildadeIndicador('feminicidio_tentado', this.checked)">
                                <label for="cb-feminicidio_tentado"><span class="dot" style="background:#e67e22"></span>Feminicídio Tentado</label>
                            </div>
                            <div class="ind-check checked" id="chk-ameaca">
                                <input type="checkbox" id="cb-ameaca" checked onchange="atualizarVisibildadeIndicador('ameaca', this.checked)">
                                <label for="cb-ameaca"><span class="dot" style="background:#f39c12"></span>Ameaça</label>
                            </div>
                            <div class="ind-check checked" id="chk-estupro">
                                <input type="checkbox" id="cb-estupro" checked onchange="atualizarVisibildadeIndicador('estupro', this.checked)">
                                <label for="cb-estupro"><span class="dot" style="background:#3498db"></span>Estupro</label>
                            </div>
                            <div class="ind-check checked" id="chk-lesao_corporal">
                                <input type="checkbox" id="cb-lesao_corporal" checked onchange="atualizarVisibildadeIndicador('lesao_corporal', this.checked)">
                                <label for="cb-lesao_corporal"><span class="dot" style="background:#9b59b6"></span>Lesão Corporal</label>
                            </div>
                        </div>
                    </div>
                    <div class="filter-group" style="justify-content:flex-end;padding-bottom:2px;margin-top:5px">
                        <button class="btn-apply" onclick="aplicarFiltroIndicadores()"><i class="fas fa-eye"></i> Aplicar</button>
                        <button class="btn-clear" onclick="selecionarTodosIndicadores()" style="margin-left:8px">Todos</button>
                    </div>
                </div>
                <div class="filter-panel" id="panel-visualizacao">
                    <div class="filter-group">
                        <label>📈 Tipo de gráfico (Evolução)</label>
                        <select id="chartType" onchange="mudarTipoGrafico()">
                            <option value="line">Linha</option>
                            <option value="bar">Barras</option>
                            <option value="bar-stacked">Barras Empilhadas</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>📐 Escala Y (Evolução)</label>
                        <select id="scaleType" onchange="mudarEscala()">
                            <option value="linear">Linear</option>
                            <option value="logarithmic">Logarítmica</option>
                        </select>
                    </div>
                    <div class="filter-group">
                        <label>🎯 Mostrar pontos</label>
                        <select id="showPoints" onchange="mudarPontos()">
                            <option value="yes">Sim</option>
                            <option value="no">Não</option>
                        </select>
                    </div>
                </div>
            </div>

            <div id="periodoMsg" class="periodo-msg" style="display: none;"></div>

            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-chart-line"></i> Evolução Temporal dos Indicadores</h3>
                        <div class="chart-actions">
                            <button class="chart-btn" onclick="resetZoom('evolutionChart')" title="Resetar zoom"><i class="fas fa-search-minus"></i> Reset Zoom</button>
                        </div>
                    </div>
                    <div class="chart-container"><canvas id="evolutionChart"></canvas></div>
                    <div class="zoom-hint">🔍 Scroll para zoom · Arrastar para mover</div>
                </div>
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-chart-pie"></i> Distribuição por Tipo de Violência</h3>
                        <div class="chart-actions">
                            <button class="chart-btn active" id="distBtn-doughnut" onclick="mudarTipoDistribuicao('doughnut', this)">Rosca</button>
                            <button class="chart-btn" id="distBtn-pie" onclick="mudarTipoDistribuicao('pie', this)">Pizza</button>
                            <button class="chart-btn" id="distBtn-polarArea" onclick="mudarTipoDistribuicao('polarArea', this)">Polar</button>
                        </div>
                    </div>
                    <div class="chart-container"><canvas id="distributionChart"></canvas></div>
                </div>
            </div>

            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-percent"></i> Variação Percentual Anual</h3>
                        <div class="chart-actions">
                            <button class="chart-btn active" id="varBtn-total" onclick="mudarTipoVariacao('total', this)">Total</button>
                            <button class="chart-btn" id="varBtn-feminicidio_consumado" onclick="mudarTipoVariacao('feminicidio_consumado', this)">Fem. Consumado</button>
                            <button class="chart-btn" id="varBtn-ameaca" onclick="mudarTipoVariacao('ameaca', this)">Ameaça</button>
                            <button class="chart-btn" id="varBtn-lesao_corporal" onclick="mudarTipoVariacao('lesao_corporal', this)">Lesão Corp.</button>
                        </div>
                    </div>
                    <div class="chart-container"><canvas id="variationChart"></canvas></div>
                </div>
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-chart-line"></i> Projeção para Próximos Anos</h3>
                        <div class="chart-actions">
                            <button class="chart-btn active" id="projBtn-feminicidio_consumado" onclick="mudarIndicadorProjecao('feminicidio_consumado', this)">Fem. Consumado</button>
                            <button class="chart-btn" id="projBtn-ameaca" onclick="mudarIndicadorProjecao('ameaca', this)">Ameaça</button>
                            <button class="chart-btn" id="projBtn-lesao_corporal" onclick="mudarIndicadorProjecao('lesao_corporal', this)">Lesão Corp.</button>
                        </div>
                    </div>
                    <div class="chart-container"><canvas id="projectionChart"></canvas></div>
                </div>
            </div>

            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-star"></i> Perfil por Indicador (Radar)</h3>
                    </div>
                    <div class="chart-container"><canvas id="radarChart"></canvas></div>
                </div>
                <div class="chart-card">
                    <div class="chart-card-header">
                        <h3><i class="fas fa-chart-bar"></i> Comparativo Indicadores por Ano</h3>
                        <div class="chart-actions">
                            <button class="chart-btn active" id="compBtn-grouped" onclick="mudarModoComparativo('grouped', this)">Agrupado</button>
                            <button class="chart-btn" id="compBtn-stacked" onclick="mudarModoComparativo('stacked', this)">Empilhado</button>
                        </div>
                    </div>
                    <div class="chart-container-tall"><canvas id="comparativoChart"></canvas></div>
                </div>
            </div>

            <div class="table-container">
                <h3><i class="fas fa-table"></i> Dados Detalhados por Ano</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Ano</th><th>Fem. Consumado</th><th>Fem. Tentado</th>
                            <th>Ameaça</th><th>Estupro</th><th>Lesão Corporal</th>
                            <th>Total</th><th>Variação %</th>
                        </tr>
                    </thead>
                    <tbody id="tableBody">{tabela_rows}</tbody>
                </table>
            </div>

            <div class="footer">
                <p><i class="fas fa-database"></i> Fonte: Secretaria de Segurança Pública do Rio Grande do Sul (SSP/RS)</p>
                <p><i class="fas fa-chart-line"></i> Dashboard Interativo | São Leopoldo - RS</p>
            </div>
        </div>

        <script>
        const dadosIniciais = {json.dumps(dados_json)};
        const mesMaxDados = {mes_max_dados_js};

        // dadosMensaisReais: {{ "2026": {{ "ameaca": [52,44,48,61,0,...], ... }}, ... }}
        // Índice 0 = Janeiro, índice 11 = Dezembro
        const dadosMensaisReais = {dados_mensais_js};

        let dados = [...dadosIniciais];
        let dadosOriginais = [...dadosIniciais];
        let evolutionChart, distributionChart, variationChart, projectionChart, radarChart, comparativoChart;
        let indicadoresVisiveis = {{
            feminicidio_consumado: true, feminicidio_tentado: true,
            ameaca: true, estupro: true, lesao_corporal: true
        }};
        const CORES = {{
            feminicidio_consumado: '#e74c3c', feminicidio_tentado: '#e67e22',
            ameaca: '#f39c12', estupro: '#3498db', lesao_corporal: '#9b59b6'
        }};
        const LABELS = {{
            feminicidio_consumado: 'Feminicídio Consumado', feminicidio_tentado: 'Feminicídio Tentado',
            ameaca: 'Ameaça', estupro: 'Estupro', lesao_corporal: 'Lesão Corporal'
        }};
        const tooltipPlugin = {{
            backgroundColor: 'rgba(15,12,41,0.92)', titleColor: '#a8c0ff', bodyColor: 'white',
            borderColor: 'rgba(102,126,234,0.4)', borderWidth: 1, padding: 12, cornerRadius: 10,
            titleFont: {{size: 13, weight: '700'}}, bodyFont: {{size: 12}},
            callbacks: {{ label: function(ctx) {{ const v = ctx.raw; if (v === null || v === undefined) return null; return ' ' + ctx.dataset.label + ': ' + (typeof v === 'number' ? v.toLocaleString('pt-BR') : v); }} }}
        }};
        const gridStyle = {{color: 'rgba(255,255,255,0.07)'}};
        const tickStyle = {{color: 'rgba(255,255,255,0.65)', font: {{size: 11}}}};
        const legendStyle = {{labels: {{color: 'white', font: {{size: 11}}, padding: 14, usePointStyle: true, pointStyleWidth: 10}}}};

        function initCharts() {{
            criarGraficoEvolucao();
            criarGraficoDistribuicao();
            criarGraficoVariacao();
            criarGraficoProjecao();
            criarGraficoRadar();
            criarGraficoComparativo();
        }}

        function criarGraficoEvolucao() {{
            const ctx = document.getElementById('evolutionChart').getContext('2d');
            const anos = dados.map(d => d.ano);
            const type = document.getElementById('chartType').value;
            const isStacked = type === 'bar-stacked';
            const realType = isStacked ? 'bar' : type;
            const showPoints = document.getElementById('showPoints').value === 'yes';
            const scale = document.getElementById('scaleType').value;
            const datasets = Object.keys(CORES).map(key => ({{
                label: LABELS[key], data: dados.map(d => d[key]),
                borderColor: CORES[key], backgroundColor: isStacked ? CORES[key]+'cc' : CORES[key]+'25',
                borderWidth: 2.5, fill: !isStacked && realType === 'line', tension: 0.4,
                pointRadius: showPoints ? 5 : 0, pointHoverRadius: 8, pointBackgroundColor: CORES[key],
                hidden: !indicadoresVisiveis[key]
            }}));
            if (evolutionChart) evolutionChart.destroy();
            evolutionChart = new Chart(ctx, {{
                type: realType, data: {{labels: anos, datasets}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    interaction: {{mode: 'index', intersect: false}},
                    plugins: {{legend: legendStyle, tooltip: tooltipPlugin,
                        zoom: {{zoom: {{wheel: {{enabled: true}}, pinch: {{enabled: true}}, mode: 'x'}}, pan: {{enabled: true, mode: 'x'}}}}
                    }},
                    scales: {{
                        y: {{type: scale, stacked: isStacked, ticks: {{...tickStyle, callback: v => v.toLocaleString('pt-BR')}}, grid: gridStyle}},
                        x: {{stacked: isStacked, ticks: tickStyle, grid: gridStyle}}
                    }}
                }}
            }});
        }}

        function criarGraficoDistribuicao(tipo = 'doughnut') {{
            const ctx = document.getElementById('distributionChart').getContext('2d');
            const totais = {{
                'Feminicídio (Cons. + Tent.)': dados.reduce((s,d) => s + d.feminicidio_consumado + d.feminicidio_tentado, 0),
                'Ameaça': dados.reduce((s,d) => s + d.ameaca, 0),
                'Estupro': dados.reduce((s,d) => s + d.estupro, 0),
                'Lesão Corporal': dados.reduce((s,d) => s + d.lesao_corporal, 0)
            }};
            const total = Object.values(totais).reduce((a,b) => a+b, 0);
            if (distributionChart) distributionChart.destroy();
            distributionChart = new Chart(ctx, {{
                type: tipo,
                data: {{labels: Object.keys(totais), datasets: [{{data: Object.values(totais), backgroundColor: ['#e74c3c','#f39c12','#3498db','#9b59b6'], borderWidth: 0, hoverOffset: 16}}]}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{
                        legend: {{position: 'bottom', labels: {{color: 'white', font: {{size: 11}}, padding: 14, usePointStyle: true}}}},
                        tooltip: {{...tooltipPlugin, callbacks: {{label: function(ctx) {{ const v = ctx.raw; const pct = ((v/total)*100).toFixed(1); return ` ${{ctx.label}}: ${{v.toLocaleString('pt-BR')}} (${{pct}}%)`; }}}}}}
                    }}
                }}
            }});
        }}

        function mudarTipoDistribuicao(tipo, btn) {{
            document.querySelectorAll('[id^="distBtn-"]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            criarGraficoDistribuicao(tipo);
        }}

        function calcularVariacoes(campo) {{
            const result = [];
            for (let i = 1; i < dados.length; i++) {{
                let curr, prev;
                if (campo === 'total') {{
                    curr = dados[i].feminicidio_consumado + dados[i].feminicidio_tentado + dados[i].ameaca + dados[i].estupro + dados[i].lesao_corporal;
                    prev = dados[i-1].feminicidio_consumado + dados[i-1].feminicidio_tentado + dados[i-1].ameaca + dados[i-1].estupro + dados[i-1].lesao_corporal;
                }} else {{ curr = dados[i][campo]; prev = dados[i-1][campo]; }}
                result.push(prev > 0 ? parseFloat(((curr-prev)/prev*100).toFixed(1)) : 0);
            }}
            return result;
        }}

        function criarGraficoVariacao(campo = 'total') {{
            const ctx = document.getElementById('variationChart').getContext('2d');
            const variacoes = calcularVariacoes(campo);
            const labels = dados.slice(1).map(d => d.ano);
            if (variationChart) variationChart.destroy();
            variationChart = new Chart(ctx, {{
                type: 'bar',
                data: {{labels, datasets: [{{label: 'Variação %', data: variacoes, backgroundColor: variacoes.map(v => v >= 0 ? '#ff6b6b' : '#48c774'), borderRadius: 10, borderSkipped: false}}]}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    interaction: {{mode: 'index', intersect: false}},
                    plugins: {{legend: {{display: false}}, tooltip: {{...tooltipPlugin, callbacks: {{label: ctx => ` Variação: ${{ctx.raw > 0 ? '+' : ''}}${{ctx.raw}}%`, afterLabel: ctx => ctx.raw > 0 ? ' ↑ Aumento' : ' ↓ Redução'}}}}}},
                    scales: {{
                        y: {{ticks: {{...tickStyle, callback: v => v + '%'}}, grid: {{...gridStyle}}}},
                        x: {{ticks: tickStyle, grid: {{display: false}}}}
                    }}
                }}
            }});
        }}

        function mudarTipoVariacao(campo, btn) {{
            document.querySelectorAll('[id^="varBtn-"]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            criarGraficoVariacao(campo);
        }}

        function criarGraficoProjecao(campo = 'feminicidio_consumado') {{
            const ctx = document.getElementById('projectionChart').getContext('2d');
            const anos = dados.map(d => d.ano);
            const valores = dados.map(d => d[campo]);
            const n = anos.length;
            const xMean = anos.reduce((a,b) => a+b,0)/n;
            const yMean = valores.reduce((a,b) => a+b,0)/n;
            const slope = anos.reduce((s,x,i) => s+(x-xMean)*(valores[i]-yMean),0) / anos.reduce((s,x) => s+(x-xMean)**2,0);
            const intercept = yMean - slope*xMean;
            const anoMax = Math.max(...anos);
            const futuro = [anoMax+1, anoMax+2];
            const projecoes = futuro.map(a => Math.max(0, Math.round(intercept+slope*a)));
            const labelsExt = [...anos, ...futuro];
            const dadosHistorico = [...valores, null, null];
            const dadosProjecao = [...Array(n-1).fill(null), valores[n-1], ...projecoes];
            if (projectionChart) projectionChart.destroy();
            projectionChart = new Chart(ctx, {{
                type: 'line',
                data: {{labels: labelsExt, datasets: [
                    {{label: 'Histórico', data: dadosHistorico, borderColor: '#667eea', backgroundColor: '#667eea30', borderWidth: 3, fill: true, pointRadius: 6, pointBackgroundColor: '#667eea', tension: 0.3}},
                    {{label: 'Projeção', data: dadosProjecao, borderColor: '#ffd93d', backgroundColor: '#ffd93d20', borderWidth: 2.5, borderDash: [6,4], fill: false, pointRadius: 7, pointStyle: 'triangle', pointBackgroundColor: '#ffd93d', tension: 0.3}}
                ]}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    interaction: {{mode: 'index', intersect: false}},
                    plugins: {{legend: legendStyle, tooltip: {{...tooltipPlugin, callbacks: {{label: ctx => {{ if(ctx.raw===null) return null; return ` ${{ctx.dataset.label}}: ${{ctx.raw.toLocaleString('pt-BR')}}`; }}}}}}}},
                    scales: {{
                        y: {{ticks: {{...tickStyle, callback: v => v.toLocaleString('pt-BR')}}, grid: gridStyle}},
                        x: {{ticks: tickStyle, grid: gridStyle}}
                    }}
                }}
            }});
        }}

        function mudarIndicadorProjecao(campo, btn) {{
            document.querySelectorAll('[id^="projBtn-"]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            criarGraficoProjecao(campo);
        }}

        function criarGraficoRadar() {{
            const ctx = document.getElementById('radarChart').getContext('2d');
            const campos = Object.keys(CORES);
            const labelsRadar = ['Fem. Consumado','Fem. Tentado','Ameaça','Estupro','Lesão Corp.'];
            const maximos = campos.map(k => Math.max(...dadosOriginais.map(d => d[k])));
            const coresBg = ['rgba(102,126,234,0.3)','rgba(255,107,107,0.3)','rgba(255,217,61,0.3)','rgba(72,199,116,0.3)','rgba(168,192,255,0.3)'];
            const coresBd = ['#667eea','#ff6b6b','#ffd93d','#48c774','#a8c0ff'];
            const datasets = dadosOriginais.map((d, i) => ({{
                label: String(d.ano),
                data: campos.map((k,j) => maximos[j]>0 ? Math.round(d[k]/maximos[j]*100) : 0),
                backgroundColor: coresBg[i], borderColor: coresBd[i], borderWidth: 2,
                pointBackgroundColor: coresBd[i], pointRadius: 4
            }}));
            if (radarChart) radarChart.destroy();
            radarChart = new Chart(ctx, {{
                type: 'radar', data: {{labels: labelsRadar, datasets}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    plugins: {{legend: legendStyle, tooltip: {{...tooltipPlugin, callbacks: {{label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.raw}}% do máximo`}}}}}},
                    scales: {{r: {{
                        min: 0, max: 100,
                        ticks: {{color: 'rgba(255,255,255,0.5)', font: {{size: 9}}, stepSize: 25, callback: v => v+'%'}},
                        grid: {{color: 'rgba(255,255,255,0.1)'}},
                        pointLabels: {{color: 'rgba(255,255,255,0.8)', font: {{size: 11}}}},
                        angleLines: {{color: 'rgba(255,255,255,0.1)'}}
                    }}}}
                }}
            }});
        }}

        function criarGraficoComparativo(modo = 'grouped') {{
            const ctx = document.getElementById('comparativoChart').getContext('2d');
            const anos = dados.map(d => String(d.ano));
            const campos = Object.keys(CORES).filter(k => indicadoresVisiveis[k]);
            const stacked = modo === 'stacked';
            const datasets = campos.map(k => ({{
                label: LABELS[k], data: dados.map(d => d[k]),
                backgroundColor: CORES[k]+(stacked?'dd':'bb'), borderColor: CORES[k],
                borderWidth: stacked?0:1.5, borderRadius: stacked?0:6
            }}));
            if (comparativoChart) comparativoChart.destroy();
            comparativoChart = new Chart(ctx, {{
                type: 'bar', data: {{labels: anos, datasets}},
                options: {{
                    responsive: true, maintainAspectRatio: false,
                    interaction: {{mode: 'index', intersect: false}},
                    plugins: {{legend: legendStyle, tooltip: {{...tooltipPlugin, callbacks: {{
                        label: ctx => ` ${{ctx.dataset.label}}: ${{ctx.raw.toLocaleString('pt-BR')}}`,
                        footer: items => `Total: ${{items.reduce((s,i)=>s+i.raw,0).toLocaleString('pt-BR')}}`
                    }}}}}},
                    scales: {{
                        y: {{stacked, ticks: {{...tickStyle, callback: v => v.toLocaleString('pt-BR')}}, grid: gridStyle}},
                        x: {{stacked, ticks: tickStyle, grid: {{display: false}}}}
                    }}
                }}
            }});
        }}

        function mudarModoComparativo(modo, btn) {{
            document.querySelectorAll('[id^="compBtn-"]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            criarGraficoComparativo(modo);
        }}

        function mudarTipoGrafico() {{ criarGraficoEvolucao(); }}
        function mudarEscala() {{ criarGraficoEvolucao(); }}
        function mudarPontos() {{ criarGraficoEvolucao(); }}
        function resetZoom() {{ if (evolutionChart) evolutionChart.resetZoom(); }}

        function atualizarVisibildadeIndicador(key, visible) {{
            indicadoresVisiveis[key] = visible;
            const wrapper = document.getElementById('chk-'+key);
            if (wrapper) wrapper.classList.toggle('checked', visible);
        }}

        function aplicarFiltroIndicadores() {{ criarGraficoEvolucao(); criarGraficoComparativo(); }}

        function selecionarTodosIndicadores() {{
            Object.keys(indicadoresVisiveis).forEach(k => {{
                indicadoresVisiveis[k] = true;
                const cb = document.getElementById('cb-'+k);
                if (cb) cb.checked = true;
                const wrapper = document.getElementById('chk-'+k);
                if (wrapper) wrapper.classList.add('checked');
            }});
            criarGraficoEvolucao(); criarGraficoComparativo();
        }}

        function trocarAba(id, btn) {{
            document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.filter-panel').forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('panel-'+id).classList.add('active');
        }}

        function aplicarFiltroAnual() {{
            const anoInicio = parseInt(document.getElementById('anoInicio').value);
            const anoFim = parseInt(document.getElementById('anoFim').value);
            if (anoInicio > anoFim) {{ alert("Ano inicial não pode ser maior que o ano final!"); return; }}
            const dadosFiltrados = dadosOriginais.filter(d => d.ano >= anoInicio && d.ano <= anoFim);
            atualizarDashboard(dadosFiltrados);
            mostrarMsg(`📅 Período: ${{anoInicio}} até ${{anoFim}} (anos completos)`);
        }}

        function aplicarFiltroMensal() {{
            const mesInicio = parseInt(document.getElementById('mesInicio').value);
            const anoInicio = parseInt(document.getElementById('anoInicioMes').value);
            const mesFim = parseInt(document.getElementById('mesFim').value);
            const anoFim = parseInt(document.getElementById('anoFimMes').value);

            if (anoInicio > anoFim || (anoInicio === anoFim && mesInicio > mesFim)) {{
                alert("Período inválido! Data inicial maior que data final."); return;
            }}

            const indicadores = ['feminicidio_consumado','feminicidio_tentado','ameaca','estupro','lesao_corporal'];

            const dadosFiltrados = dadosOriginais
                .filter(d => d.ano >= anoInicio && d.ano <= anoFim)
                .map(d => {{
                    const anoStr = String(d.ano);
                    const mensais = dadosMensaisReais[anoStr];

                    // Se não temos dados mensais reais para este ano, fallback proporcional
                    if (!mensais) {{
                        const mesMaxReal = mesMaxDados[d.ano] || 12;
                        const mesInicioEfetivo = (d.ano === anoInicio) ? mesInicio : 1;
                        const mesFimEfetivo = Math.min((d.ano === anoFim) ? mesFim : mesMaxReal, mesMaxReal);
                        const mesesPedidos = Math.max(0, mesFimEfetivo - mesInicioEfetivo + 1);
                        const fator = mesesPedidos / mesMaxReal;
                        const novo = {{ano: d.ano}};
                        indicadores.forEach(k => {{ novo[k] = Math.round(d[k] * fator); }});
                        return novo;
                    }}

                    // Dados mensais reais disponíveis: somar apenas os meses pedidos
                    // Índice JS: mes 1 (Jan) = índice 0, mes 12 (Dez) = índice 11
                    const mesMaxReal = mesMaxDados[d.ano] || 12;
                    const mesInicioEfetivo = (d.ano === anoInicio) ? mesInicio : 1;
                    // Não pedir meses além do disponível
                    const mesFimEfetivo = Math.min((d.ano === anoFim) ? mesFim : mesMaxReal, mesMaxReal);

                    if (mesFimEfetivo < mesInicioEfetivo) {{
                        // Fora do range disponível → zeros
                        const novo = {{ano: d.ano}};
                        indicadores.forEach(k => {{ novo[k] = 0; }});
                        return novo;
                    }}

                    const novo = {{ano: d.ano}};
                    indicadores.forEach(k => {{
                        const serie = mensais[k] || [];
                        let soma = 0;
                        for (let m = mesInicioEfetivo; m <= mesFimEfetivo; m++) {{
                            soma += (serie[m - 1] || 0);  // índice 0-based
                        }}
                        novo[k] = soma;
                    }});
                    return novo;
                }});

            atualizarDashboard(dadosFiltrados);
            const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
            mostrarMsg(`📆 Período: ${{meses[mesInicio-1]}}/${{anoInicio}} até ${{meses[mesFim-1]}}/${{anoFim}} (dados reais por mês)`);
        }}

        function limparFiltros() {{
            dados = [...dadosOriginais];
            document.getElementById('anoInicio').value = '2022';
            document.getElementById('anoFim').value = '2026';
            document.getElementById('anoInicioMes').value = '2022';
            document.getElementById('anoFimMes').value = '2026';
            document.getElementById('mesInicio').value = '1';
            document.getElementById('mesFim').value = '12';
            destroyAll(); initCharts(); atualizarKPIs(); atualizarTabela();
        }}

        function atualizarDashboard(dadosFiltrados) {{
            if(dadosFiltrados.length === 0) {{ alert("Nenhum dado encontrado no período selecionado!"); return; }}
            dados = dadosFiltrados;
            destroyAll(); initCharts(); atualizarKPIs(); atualizarTabela();
        }}

        function destroyAll() {{
            [evolutionChart, distributionChart, variationChart, projectionChart, radarChart, comparativoChart].forEach(c => {{ if(c) c.destroy(); }});
            evolutionChart = distributionChart = variationChart = projectionChart = radarChart = comparativoChart = null;
        }}

        function atualizarKPIs() {{
            const tF = dados.reduce((s,d) => s+d.feminicidio_consumado,0);
            const tFT = dados.reduce((s,d) => s+d.feminicidio_tentado,0);
            const tA = dados.reduce((s,d) => s+d.ameaca,0);
            const tE = dados.reduce((s,d) => s+d.estupro,0);
            const tL = dados.reduce((s,d) => s+d.lesao_corporal,0);
            document.getElementById('totalFem').innerHTML = tF;
            document.getElementById('totalFemTent').innerHTML = tFT;
            document.getElementById('totalAmeaca').innerHTML = tA.toLocaleString('pt-BR');
            document.getElementById('totalEstupro').innerHTML = tE;
            document.getElementById('totalLesao').innerHTML = tL.toLocaleString('pt-BR');
            document.getElementById('totalGeral').innerHTML = (tF+tFT+tA+tE+tL).toLocaleString('pt-BR');
            document.getElementById('mediaAnual').innerHTML = (tF/dados.length).toFixed(1);
        }}

        function atualizarTabela() {{
            let html = ''; let ant = null;
            for (const d of dados) {{
                const t = d.feminicidio_consumado+d.feminicidio_tentado+d.ameaca+d.estupro+d.lesao_corporal;
                let v = '-';
                if (ant !== null && ant > 0) {{
                    const p = ((t-ant)/ant*100);
                    v = `<span style="color:${{p>0?'#ff6b6b':'#48c774'}}">${{p>0?'+':''}}${{p.toFixed(1)}}%</span>`;
                }}
                html += `<tr><td><strong>${{d.ano}}</strong>${{d.ano===2026?'':''}}</td><td>${{d.feminicidio_consumado}}</td><td>${{d.feminicidio_tentado}}</td><td>${{d.ameaca.toLocaleString('pt-BR')}}</td><td>${{d.estupro}}</td><td>${{d.lesao_corporal.toLocaleString('pt-BR')}}</td><td><strong>${{t.toLocaleString('pt-BR')}}</strong></td><td>${{v}}</td></tr>`;
                ant = t;
            }}
            document.getElementById('tableBody').innerHTML = html;
        }}

        function exportarCSV() {{
            let csv = 'Ano,Feminicídio Consumado,Feminicídio Tentado,Ameaça,Estupro,Lesão Corporal,Total\\n';
            dados.forEach(d => {{
                const total = d.feminicidio_consumado+d.feminicidio_tentado+d.ameaca+d.estupro+d.lesao_corporal;
                csv += `${{d.ano}},${{d.feminicidio_consumado}},${{d.feminicidio_tentado}},${{d.ameaca}},${{d.estupro}},${{d.lesao_corporal}},${{total}}\\n`;
            }});
            const blob = new Blob([csv], {{type:'text/csv;charset=utf-8;'}});
            const link = document.createElement('a');
            link.href = URL.createObjectURL(blob);
            link.download = 'dashboard_sao_leopoldo.csv';
            link.click();
        }}

        function mostrarMsg(txt) {{
            const m = document.getElementById('periodoMsg');
            m.style.display = 'block'; m.innerHTML = txt;
            setTimeout(() => {{ m.style.display = 'none'; }}, 4000);
        }}

        window.onload = initCharts;
        </script>
        </body>
        </html>'''

        return html

    def executar_atualizacao_completa(self, forcar_scraping=True):
        print("\n🔄 EXECUTANDO ATUALIZAÇÃO COMPLETA...")
        
        if forcar_scraping:
            print("🕷️ FORÇANDO SCRAPING - Buscando dados novos da SSP/RS...")
            import shutil
            if PASTA_DOWNLOADS.exists():
                shutil.rmtree(PASTA_DOWNLOADS)
                print("🗑️ Downloads antigos removidos")
            self.criar_pastas()
            self.atualizar_links()
            self.baixar_todos_arquivos()
            df = self.processar_dados()
            if df is None:
                print("❌ Falha no scraping! Tentando usar dados existentes...")
                json_path = PASTA_DADOS / 'indicadores_sao_leopoldo.json'
                if json_path.exists():
                    with open(json_path, 'r', encoding='utf-8') as f:
                        dados = json.load(f)
                    df = pd.DataFrame(dados)
                else:
                    return False
            else:
                self.salvar_dados(df)
                print("\n📊 Extraindo dados mensais reais da planilha...")
                self.processar_dados_mensais()
        else:
            json_path = PASTA_DADOS / 'indicadores_sao_leopoldo.json'
            if json_path.exists():
                print("📁 Carregando dados existentes...")
                with open(json_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                df = pd.DataFrame(dados)
                # Regenerar mensais se não existirem
                json_mensais = PASTA_DADOS / 'indicadores_mensais_reais.json'
                if not json_mensais.exists():
                    self.processar_dados_mensais()
            else:
                print("❌ Nenhum dado encontrado!")
                return False
        
        check_time = datetime.now()
        html_anual = self.gerar_dashboard_anual(df, check_time)
        with open('index.html', 'w', encoding='utf-8') as f:
            f.write(html_anual)
        print(f"✅ Dashboard anual gerado em index.html")
        return True
    
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
    
    def run_automated_task(self):
        logger.info("="*60)
        logger.info("Executando tarefa automatizada")
        logger.info(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)
        try:
            self.executar_atualizacao_completa()
            logger.info("✅ Execução concluída com sucesso!")
        except Exception as e:
            logger.error(f"Erro na tarefa: {e}")
            import traceback
            traceback.print_exc()


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
        return jsonify({'status': 'online', 'last_update': str(dash.last_check_time)})
    def run_server():
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print("\n🌐 API Server rodando em http://127.0.0.1:5000")
    return server_thread


def main():
    dash = AutomatedDashboard()
    servidor_api = iniciar_servidor_api(dash)
    print("="*60)
    print("🎯 SISTEMA DE MONITORAMENTO - SÃO LEOPOLDO/RS")
    print("="*60)
    print("Versão: 6.1 (Filtro Mensal com Dados Reais)")
    print("Município: São Leopoldo - RS")
    print("Período: 2022 a 2026")
    print(f"Fonte: {URL_PAGINA}")
    print("="*60)
    try:
        import bs4
        print("✅ BeautifulSoup4 instalado")
    except ImportError:
        print("❌ BeautifulSoup4 não instalado. Instalando...")
        os.system('pip install beautifulsoup4')
    print("\n📊 Criando dashboard...")
    dash.executar_atualizacao_completa()
    print(f"\n✨ Dashboard disponível: {Path.cwd() / 'index.html'}")
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
            try:
                while True:
                    schedule.run_pending()
                    time.sleep(10)
            except KeyboardInterrupt:
                print("\n\n⏹️ Monitoramento interrompido pelo usuário")
        elif opcao == '4':
            if dash.config['schedule']['enabled']:
                print("\n✅ Agendamento habilitado")
                cfg = dash.config['schedule']
                if cfg['interval_type'] == 'minutes':
                    print(f"📊 A cada {cfg['interval_minutes']} minutos")
                elif cfg['interval_type'] == 'hourly':
                    print(f"📊 A cada {cfg['interval_hours']} hora(s)")
                elif cfg['interval_type'] == 'daily':
                    print(f"📊 Diário às {cfg['time']}")
                elif cfg['interval_type'] == 'monthly':
                    print(f"📊 Mensal - Dia {cfg['day_of_month']} às {cfg['time']}")
                next_run = dash.get_next_run_time()
                if next_run:
                    print(f"📅 Próxima execução: {next_run.strftime('%d/%m/%Y às %H:%M:%S')}")
            else:
                print("\n❌ Agendamento desabilitado")
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
