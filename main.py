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

    # Calcular mês máximo com dados reais para cada ano.
    ano_atual = check_time.year
    mes_atual = check_time.month
    mes_max_ano_atual = mes_atual - 1 if mes_atual > 1 else 12
    mes_max_dados_py = {}
    for d in dados_json:
        if d['ano'] < ano_atual:
            mes_max_dados_py[d['ano']] = 12
        elif d['ano'] == ano_atual:
            mes_max_dados_py[d['ano']] = mes_max_ano_atual
        else:
            mes_max_dados_py[d['ano']] = 12
    mes_max_dados_js = json.dumps(mes_max_dados_py)

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

    # Gerar tabela
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
                    <td><strong>{int(row['Ano'])}</strong>{int(row['Ano']) == 2026 and ' ⚠️' or ''}</td>
                    <td>{int(row['Feminicídio Consumado']) if pd.notna(row['Feminicídio Consumado']) else 0}</td>
                    <td>{int(row['Feminicídio Tentado']) if pd.notna(row['Feminicídio Tentado']) else 0}</td>
                    <td>{int(row['Ameaça']) if pd.notna(row['Ameaça']) else 0:,}</td>
                    <td>{int(row['Estupro']) if pd.notna(row['Estupro']) else 0}</td>
                    <td>{int(row['Lesão Corporal']) if pd.notna(row['Lesão Corporal']) else 0:,}</td>
                    <td><strong>{total:,}</strong></td>
                    <td>{variacao_html}</td>
                </tr>'''

    data_hora = check_time.strftime('%d/%m/%Y às %H:%M:%S')
    dados_json_str = json.dumps(dados_json)
    total_fem = totais['feminicidio_total']
    total_tent = totais['feminicidio_tentado_total']
    total_ame = totais['ameaca_total']
    total_est = totais['estupro_total']
    total_les = totais['lesao_total']
    total_geral = totais['total_geral']
    media_anual_fmt = f"{media_anual:.1f}"
    tendencia_display = tendencia.upper()
    tendencia_label = '↑ Crescente' if tendencia == 'crescente' else '↓ Decrescente' if tendencia == 'decrescente' else '→ Estável'
    proj2026_display = int(projecao_2026)

    html = f'''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard | Violência Contra Mulheres - São Leopoldo</title>
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
        .update-time {{ background: rgba(255,255,255,0.9); padding: 10px 20px; border-radius: 50px; display: inline-flex; align-items: center; gap: 10px; color: #333; }}
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
        .filters-section {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 25px; border: 1px solid rgba(255,255,255,0.1); }}
        .filters-title {{ color: white; margin-bottom: 15px; font-size: 1.2em; display: flex; align-items: center; gap: 10px; }}
        .filter-group {{ display: inline-block; margin-right: 20px; margin-bottom: 10px; vertical-align: top; }}
        .filter-group label {{ display: block; color: rgba(255,255,255,0.7); font-size: 0.85em; margin-bottom: 5px; }}
        .filter-group select, .filter-group button {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); padding: 8px 12px; border-radius: 8px; color: white; cursor: pointer; font-family: 'Inter', sans-serif; }}
        .filter-group button {{ background: linear-gradient(135deg, #667eea, #764ba2); border: none; }}
        .filter-group button:hover {{ opacity: 0.9; transform: translateY(-1px); }}
        .categories-filter {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 5px; }}
        .cat-toggle {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); padding: 6px 14px; border-radius: 50px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.2s; color: rgba(255,255,255,0.7); font-family: 'Inter', sans-serif; }}
        .cat-toggle.active {{ color: white; }}
        .cat-toggle[data-cat="feminicidio"].active {{ background: rgba(248,113,113,0.3); border-color: #f87171; color: #f87171; }}
        .cat-toggle[data-cat="tentado"].active {{ background: rgba(251,146,60,0.3); border-color: #fb923c; color: #fb923c; }}
        .cat-toggle[data-cat="ameaca"].active {{ background: rgba(250,204,21,0.3); border-color: #facc15; color: #facc15; }}
        .cat-toggle[data-cat="estupro"].active {{ background: rgba(96,165,250,0.3); border-color: #60a5fa; color: #60a5fa; }}
        .cat-toggle[data-cat="lesao"].active {{ background: rgba(167,139,250,0.3); border-color: #a78bfa; color: #a78bfa; }}
        .chart-type-toggle {{ display: flex; gap: 4px; }}
        .type-btn {{ background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.2); color: rgba(255,255,255,0.7); padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; font-family: 'Inter', sans-serif; transition: all 0.2s; }}
        .type-btn.active {{ background: rgba(102,126,234,0.4); border-color: #667eea; color: white; }}
        .charts-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 25px; margin-bottom: 25px; }}
        .chart-card {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }}
        .chart-card h3 {{ color: white; margin-bottom: 15px; font-size: 1.2em; display: flex; align-items: center; gap: 10px; justify-content: space-between; flex-wrap: wrap; }}
        .chart-container {{ position: relative; height: 400px; }}
        .table-container {{ background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px; padding: 20px; margin-bottom: 25px; overflow-x: auto; }}
        .table-container h3 {{ color: white; margin-bottom: 15px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: linear-gradient(135deg, #667eea, #764ba2); color: white; padding: 12px; text-align: center; font-weight: 600; }}
        td {{ padding: 10px; text-align: center; color: white; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .footer {{ background: rgba(255,255,255,0.05); border-radius: 15px; padding: 20px; text-align: center; color: rgba(255,255,255,0.5); font-size: 0.85em; }}
        .periodo-msg {{ background: rgba(102,126,234,0.3); padding: 10px 15px; border-radius: 10px; margin-bottom: 15px; text-align: center; color: white; display: none; animation: fadeIn 0.3s ease; }}
        @keyframes fadeIn {{ from {{ opacity: 0; transform: translateY(-4px); }} to {{ opacity: 1; transform: translateY(0); }} }}
        @media (max-width: 768px) {{ .charts-grid {{ grid-template-columns: 1fr; }} .stats-grid {{ grid-template-columns: 1fr; }} .header h1 {{ font-size: 1.5em; }} .filter-group {{ display: block; margin-bottom: 15px; }} }}
        .badge-red {{ background: rgba(248,113,113,0.2); color: #f87171; padding: 3px 8px; border-radius: 50px; font-size: 0.78rem; font-weight: 600; }}
        .badge-green {{ background: rgba(52,211,153,0.2); color: #48c774; padding: 3px 8px; border-radius: 50px; font-size: 0.78rem; font-weight: 600; }}
    </style>
</head>
<body>
<div class="dashboard">
    <div class="header">
        <h1><i class="fas fa-chart-line"></i> Violência Contra Mulheres</h1>
        <div class="subtitle">Dashboard Interativo com Filtros Avançados | São Leopoldo - RS</div>
        <div class="update-info">
            <div class="update-time"><i class="fas fa-clock"></i><span>Última atualização: {data_hora}</span></div>
            <div>
                <button class="refresh-btn" onclick="location.reload()"><i class="fas fa-sync-alt"></i> Atualizar</button>
                <button class="btn-export" onclick="exportarCSV()"><i class="fas fa-file-csv"></i> Exportar CSV</button>
            </div>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card"><div class="icon"><i class="fas fa-gavel"></i></div><h3>⚖️ FEMINICÍDIO CONSUMADO</h3><div class="value" id="totalFem">{total_fem}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-exclamation-triangle"></i></div><h3>⚠️ FEMINICÍDIO TENTADO</h3><div class="value" id="totalFemTent">{total_tent}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-comment-dots"></i></div><h3>💬 AMEAÇAS</h3><div class="value" id="totalAmeaca">{total_ame:,}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-shield-alt"></i></div><h3>🔞 ESTUPROS</h3><div class="value" id="totalEstupro">{total_est}</div></div>
        <div class="stat-card"><div class="icon"><i class="fas fa-heart-broken"></i></div><h3>💔 LESÕES CORPORAIS</h3><div class="value" id="totalLesao">{total_les:,}</div></div>
    </div>

    <div class="insights-grid">
        <div class="insight-card"><h4><i class="fas fa-chart-simple"></i> Média Anual</h4><div class="insight-value" id="mediaAnual">{media_anual_fmt}</div><div class="insight-label">Feminicídios por ano</div></div>
        <div class="insight-card"><h4><i class="fas fa-trend-up"></i> Tendência</h4><div class="insight-value" id="tendencia">{tendencia_display}</div><div class="insight-label" id="tendenciaLabel">{tendencia_label}</div></div>
        <div class="insight-card"><h4><i class="fas fa-calendar"></i> Projeção 2026</h4><div class="insight-value" id="proj2026">{proj2026_display}</div><div class="insight-label">Feminicídios estimados</div></div>
        <div class="insight-card"><h4><i class="fas fa-chart-pie"></i> Total Geral</h4><div class="insight-value" id="totalGeral">{total_geral:,}</div><div class="insight-label">Casos registrados (2022-2026)</div></div>
    </div>

    <div class="filters-section">
        <div class="filters-title"><i class="fas fa-sliders-h"></i> Filtros Avançados</div>

        <div class="filter-group">
            <label>📅 Período de Anos</label>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <select id="anoInicio" onchange="aplicarFiltroAnual()">
                    <option value="2022">2022</option><option value="2023">2023</option>
                    <option value="2024">2024</option><option value="2025">2025</option>
                    <option value="2022" selected>2022</option>
                </select>
                <span style="color:white;">até</span>
                <select id="anoFim" onchange="aplicarFiltroAnual()">
                    <option value="2022">2022</option><option value="2023">2023</option>
                    <option value="2024">2024</option><option value="2025">2025</option>
                    <option value="2026" selected>2026</option>
                </select>
                <button onclick="aplicarFiltroAnual()">Aplicar Anual</button>
            </div>
        </div>

        <div class="filter-group">
            <label>📆 Comparação por Mês/Ano</label>
            <div style="display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
                <select id="mesInicio">
                    <option value="1">Jan</option><option value="2">Fev</option><option value="3">Mar</option>
                    <option value="4">Abr</option><option value="5">Mai</option><option value="6">Jun</option>
                    <option value="7">Jul</option><option value="8">Ago</option><option value="9">Set</option>
                    <option value="10">Out</option><option value="11">Nov</option><option value="12">Dez</option>
                </select>
                <select id="anoInicioMes">
                    <option value="2022">2022</option><option value="2023">2023</option>
                    <option value="2024">2024</option><option value="2025">2025</option>
                    <option value="2022" selected>2022</option>
                </select>
                <span style="color:white;">até</span>
                <select id="mesFim">
                    <option value="1">Jan</option><option value="2">Fev</option><option value="3">Mar</option>
                    <option value="4">Abr</option><option value="5">Mai</option><option value="6">Jun</option>
                    <option value="7">Jul</option><option value="8">Ago</option><option value="9">Set</option>
                    <option value="10">Out</option><option value="11">Nov</option><option value="12" selected>Dez</option>
                </select>
                <select id="anoFimMes">
                    <option value="2022">2022</option><option value="2023">2023</option>
                    <option value="2024">2024</option><option value="2025">2025</option>
                    <option value="2026" selected>2026</option>
                </select>
                <button onclick="aplicarFiltroMensal()">Aplicar Mensal</button>
            </div>
            <div style="font-size: 0.7em; color: rgba(255,255,255,0.5); margin-top: 5px;">
                💡 Compara o acumulado de JAN até o mês selecionado em cada ano
            </div>
        </div>

        <div class="filter-group">
            <label>📊 Categorias Visíveis</label>
            <div class="categories-filter">
                <button class="cat-toggle active" data-cat="feminicidio" onclick="toggleCategoria(this)">Feminicídio</button>
                <button class="cat-toggle active" data-cat="tentado" onclick="toggleCategoria(this)">Fem. Tentado</button>
                <button class="cat-toggle active" data-cat="ameaca" onclick="toggleCategoria(this)">Ameaça</button>
                <button class="cat-toggle active" data-cat="estupro" onclick="toggleCategoria(this)">Estupro</button>
                <button class="cat-toggle active" data-cat="lesao" onclick="toggleCategoria(this)">Lesão Corporal</button>
            </div>
        </div>

        <div class="filter-group">
            <label>📊 Tipo de Gráfico</label>
            <div class="chart-type-toggle">
                <button class="type-btn active" onclick="setChartType('line', this)">Linha</button>
                <button class="type-btn" onclick="setChartType('bar', this)">Barras</button>
            </div>
        </div>

        <div class="filter-group">
            <label>🔄 Ações</label>
            <div>
                <button onclick="limparFiltros()" style="background: rgba(255,255,255,0.2);">Limpar Filtros</button>
            </div>
        </div>
    </div>

    <div id="periodoMsg" class="periodo-msg"></div>

    <div class="charts-grid">
        <div class="chart-card">
            <h3><i class="fas fa-chart-line"></i> Evolução Temporal dos Indicadores
                <span style="font-size:0.7rem; font-weight:normal;">Clique nas categorias acima</span>
            </h3>
            <div class="chart-container"><canvas id="evolutionChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3><i class="fas fa-chart-pie"></i> Distribuição por Tipo de Violência</h3>
            <div class="chart-container"><canvas id="distributionChart"></canvas></div>
        </div>
    </div>

    <div class="charts-grid">
        <div class="chart-card">
            <h3><i class="fas fa-percent"></i> Variação Percentual Anual</h3>
            <div class="chart-container"><canvas id="variationChart"></canvas></div>
        </div>
        <div class="chart-card">
            <h3><i class="fas fa-chart-line"></i> Projeção para Próximos Anos (Feminicídio)</h3>
            <div class="chart-container"><canvas id="projectionChart"></canvas></div>
        </div>
    </div>

    <div class="table-container">
        <h3><i class="fas fa-table"></i> Dados Detalhados por Ano</h3>
        <table>
            <thead>
                <tr><th>Ano</th><th>Feminicídio Consumado</th><th>Feminicídio Tentado</th><th>Ameaça</th><th>Estupro</th><th>Lesão Corporal</th><th>Total</th><th>Variação %</th></tr>
            </thead>
            <tbody id="tableBody">
                {tabela_rows}
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p><i class="fas fa-database"></i> Fonte: Secretaria de Segurança Pública do Rio Grande do Sul (SSP/RS)</p>
        <p><i class="fas fa-chart-line"></i> Dashboard Interativo | São Leopoldo - RS</p>
    </div>
</div>

<script>
const dadosIniciais = {dados_json_str};
const mesMaxDados = {mes_max_dados_js};

let dados = [...dadosIniciais];
let dadosOriginais = [...dadosIniciais];
let evolutionChart, distributionChart, variationChart, projectionChart;
let currentChartType = 'line';
let visibleCats = {{feminicidio: true, tentado: true, ameaca: true, estupro: true, lesao: true}};

const COLORS = {{
    feminicidio: {{line: '#f87171', bg: 'rgba(248,113,113,0.2)'}},
    tentado: {{line: '#fb923c', bg: 'rgba(251,146,60,0.2)'}},
    ameaca: {{line: '#facc15', bg: 'rgba(250,204,21,0.2)'}},
    estupro: {{line: '#60a5fa', bg: 'rgba(96,165,250,0.2)'}},
    lesao: {{line: '#a78bfa', bg: 'rgba(167,139,250,0.2)'}}
}};

function fmtNum(n) {{ return n.toLocaleString('pt-BR'); }}

function initCharts() {{
    criarGraficoEvolucao();
    criarGraficoDistribuicao();
    criarGraficoVariacao();
    criarGraficoProjecao();
    renderTable();
    updateStats();
}}

function criarGraficoEvolucao() {{
    const ctx = document.getElementById('evolutionChart').getContext('2d');
    if(evolutionChart) evolutionChart.destroy();

    const anos = dados.map(d => d.ano);
    const datasets = [];

    if(visibleCats.feminicidio) {{
        datasets.push({{label: 'Feminicídio Consumado', data: dados.map(d => d.feminicidio_consumado), borderColor: COLORS.feminicidio.line, backgroundColor: COLORS.feminicidio.bg, borderWidth: 3, fill: currentChartType === 'line', tension: 0.4, pointRadius: 5}});
    }}
    if(visibleCats.tentado) {{
        datasets.push({{label: 'Feminicídio Tentado', data: dados.map(d => d.feminicidio_tentado), borderColor: COLORS.tentado.line, backgroundColor: COLORS.tentado.bg, borderWidth: 3, fill: currentChartType === 'line', tension: 0.4, pointRadius: 5}});
    }}
    if(visibleCats.ameaca) {{
        datasets.push({{label: 'Ameaça', data: dados.map(d => d.ameaca), borderColor: COLORS.ameaca.line, backgroundColor: COLORS.ameaca.bg, borderWidth: 3, fill: currentChartType === 'line', tension: 0.4, pointRadius: 5, yAxisID: 'yRight'}});
    }}
    if(visibleCats.estupro) {{
        datasets.push({{label: 'Estupro', data: dados.map(d => d.estupro), borderColor: COLORS.estupro.line, backgroundColor: COLORS.estupro.bg, borderWidth: 3, fill: currentChartType === 'line', tension: 0.4, pointRadius: 5}});
    }}
    if(visibleCats.lesao) {{
        datasets.push({{label: 'Lesão Corporal', data: dados.map(d => d.lesao_corporal), borderColor: COLORS.lesao.line, backgroundColor: COLORS.lesao.bg, borderWidth: 3, fill: currentChartType === 'line', tension: 0.4, pointRadius: 5, yAxisID: 'yRight'}});
    }}

    evolutionChart = new Chart(ctx, {{
        type: currentChartType,
        data: {{labels: anos, datasets: datasets}},
        options: {{
            responsive: true, maintainAspectRatio: false,
            plugins: {{legend: {{labels: {{color: 'white', font: {{size: 11}}}}}}, tooltip: {{callbacks: {{label: ctx => ` ${{ctx.dataset.label}}: ${{fmtNum(ctx.raw)}}`}}}}}},
            scales: {{
                y: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}, title: {{display: true, text: 'Feminicídio / Estupro', color: 'rgba(255,255,255,0.5)'}}}},
                yRight: {{position: 'right', ticks: {{color: 'rgba(255,255,255,0.5)'}}, grid: {{drawOnChartArea: false}}, title: {{display: true, text: 'Ameaça / Lesão', color: 'rgba(255,255,255,0.5)'}}}},
                x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}
            }}
        }}
    }});
}}

function criarGraficoDistribuicao() {{
    const ctx = document.getElementById('distributionChart').getContext('2d');
    if(distributionChart) distributionChart.destroy();

    const totais = {{
        'Feminicídio': dados.reduce((s,d) => s + d.feminicidio_consumado + d.feminicidio_tentado, 0),
        'Ameaça': dados.reduce((s,d) => s + d.ameaca, 0),
        'Estupro': dados.reduce((s,d) => s + d.estupro, 0),
        'Lesão Corporal': dados.reduce((s,d) => s + d.lesao_corporal, 0)
    }};

    distributionChart = new Chart(ctx, {{
        type: 'doughnut',
        data: {{labels: Object.keys(totais), datasets: [{{data: Object.values(totais), backgroundColor: ['#f87171', '#facc15', '#60a5fa', '#a78bfa'], borderWidth: 0, hoverOffset: 15}}]}},
        options: {{responsive: true, maintainAspectRatio: false, plugins: {{legend: {{position: 'bottom', labels: {{color: 'white'}}}}}}}}
    }});
}}

function criarGraficoVariacao() {{
    const ctx = document.getElementById('variationChart').getContext('2d');
    if(variationChart) variationChart.destroy();

    const variacoes = [];
    for (let i = 1; i < dados.length; i++) {{
        const totalAtual = dados[i].feminicidio_consumado + dados[i].feminicidio_tentado + dados[i].ameaca + dados[i].estupro + dados[i].lesao_corporal;
        const totalAnterior = dados[i-1].feminicidio_consumado + dados[i-1].feminicidio_tentado + dados[i-1].ameaca + dados[i-1].estupro + dados[i-1].lesao_corporal;
        const variacao = totalAnterior > 0 ? ((totalAtual - totalAnterior) / totalAnterior * 100) : 0;
        variacoes.push({{ano: dados[i].ano, variacao: variacao}});
    }}

    variationChart = new Chart(ctx, {{
        type: 'bar',
        data: {{labels: variacoes.map(v => v.ano), datasets: [{{label: 'Variação %', data: variacoes.map(v => v.variacao), backgroundColor: variacoes.map(v => v.variacao >= 0 ? 'rgba(248,113,113,0.7)' : 'rgba(52,211,153,0.7)'), borderRadius: 8}}]}},
        options: {{responsive: true, maintainAspectRatio: false, plugins: {{tooltip: {{callbacks: {{label: ctx => ` Variação: ${{ctx.raw.toFixed(1)}}%`}}}}}}, scales: {{y: {{ticks: {{color: 'white', callback: v => v + '%'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}, x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}}}}}
    }});
}}

function criarGraficoProjecao() {{
    const ctx = document.getElementById('projectionChart').getContext('2d');
    if(projectionChart) projectionChart.destroy();

    const anos = dados.map(d => d.ano);
    const valores = dados.map(d => d.feminicidio_consumado);
    const last = valores[valores.length-1];

    const n = anos.length;
    const sumX = anos.reduce((a,b)=>a+b,0);
    const sumY = valores.reduce((a,b)=>a+b,0);
    const sumXY = anos.reduce((s,x,i)=>s+x*valores[i],0);
    const sumX2 = anos.reduce((s,x)=>s+x*x,0);
    const slope = (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX);
    const intercept = (sumY - slope*sumX)/n;
    const proj2026 = Math.max(0, Math.round(slope*2026+intercept));
    const proj2027 = Math.max(0, Math.round(slope*2027+intercept));

    document.getElementById('proj2026').textContent = proj2026;

    const projLabels = [...new Set([...anos, 2026, 2027])];
    const historico = projLabels.map(a => anos.includes(a) ? valores[anos.indexOf(a)] : null);
    const projecao = projLabels.map(a => {{
        if(a < anos[anos.length-1]) return null;
        if(a === anos[anos.length-1]) return last;
        if(a === 2026) return proj2026;
        if(a === 2027) return proj2027;
        return null;
    }});

    projectionChart = new Chart(ctx, {{
        type: 'line',
        data: {{labels: projLabels, datasets: [
            {{label: 'Histórico', data: historico, borderColor: '#60a5fa', backgroundColor: 'rgba(96,165,250,0.1)', borderWidth: 3, fill: true, pointRadius: 5}},
            {{label: 'Projeção', data: projecao, borderColor: '#facc15', borderWidth: 3, borderDash: [5, 5], fill: false, pointRadius: 6, pointStyle: 'triangle'}}
        ]}},
        options: {{responsive: true, maintainAspectRatio: false, plugins: {{legend: {{labels: {{color: 'white'}}}}}}, scales: {{y: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}, x: {{ticks: {{color: 'white'}}, grid: {{color: 'rgba(255,255,255,0.1)'}}}}}}}}
    }});
}}

function renderTable() {{
    let html = '';
    let anteriorTotal = null;
    for (const d of dados) {{
        const total = d.feminicidio_consumado + d.feminicidio_tentado + d.ameaca + d.estupro + d.lesao_corporal;
        let variacaoHtml = '-';
        if (anteriorTotal !== null && anteriorTotal > 0) {{
            const pct = ((total - anteriorTotal) / anteriorTotal * 100);
            const cls = pct > 0 ? 'badge-red' : 'badge-green';
            const sinal = pct > 0 ? '+' : '';
            variacaoHtml = `<span class="${{cls}}">${{sinal}}${{pct.toFixed(1)}}%</span>`;
        }}
        html += `<tr>
            <td><strong>${{d.ano}}</strong>${{d.ano === 2026 ? ' ⚠️' : ''}}</td>
            <td>${{d.feminicidio_consumado}}</td>
            <td>${{d.feminicidio_tentado}}</td>
            <td>${{fmtNum(d.ameaca)}}</td>
            <td>${{d.estupro}}</td>
            <td>${{fmtNum(d.lesao_corporal)}}</td>
            <td><strong>${{fmtNum(total)}}</strong></td>
            <td>${{variacaoHtml}}</td>
        </tr>`;
        anteriorTotal = total;
    }}
    document.getElementById('tableBody').innerHTML = html;
}}

function updateStats() {{
    const totalFem = dados.reduce((s,d) => s + d.feminicidio_consumado, 0);
    const totalFemTent = dados.reduce((s,d) => s + d.feminicidio_tentado, 0);
    const totalAmeaca = dados.reduce((s,d) => s + d.ameaca, 0);
    const totalEstupro = dados.reduce((s,d) => s + d.estupro, 0);
    const totalLesao = dados.reduce((s,d) => s + d.lesao_corporal, 0);
    const totalGeral = totalFem + totalFemTent + totalAmeaca + totalEstupro + totalLesao;

    document.getElementById('totalFem').innerHTML = totalFem;
    document.getElementById('totalFemTent').innerHTML = totalFemTent;
    document.getElementById('totalAmeaca').innerHTML = fmtNum(totalAmeaca);
    document.getElementById('totalEstupro').innerHTML = totalEstupro;
    document.getElementById('totalLesao').innerHTML = fmtNum(totalLesao);
    document.getElementById('totalGeral').innerHTML = fmtNum(totalGeral);

    const mediaAnual = totalFem / dados.length;
    document.getElementById('mediaAnual').innerHTML = mediaAnual.toFixed(1);

    const totais = dados.map(d => d.feminicidio_consumado + d.feminicidio_tentado + d.ameaca + d.estupro + d.lesao_corporal);
    const first = totais[0], last = totais[totais.length-1];
    const tend = last < first ? 'DECRESCENTE' : last > first ? 'CRESCENTE' : 'ESTÁVEL';
    document.getElementById('tendencia').innerHTML = tend;
    document.getElementById('tendenciaLabel').innerHTML = tend === 'DECRESCENTE' ? '↓ Decrescente' : tend === 'CRESCENTE' ? '↑ Crescente' : '→ Estável';
}}

function redrawAll() {{
    criarGraficoEvolucao();
    criarGraficoDistribuicao();
    criarGraficoVariacao();
    criarGraficoProjecao();
    renderTable();
    updateStats();
}}

function aplicarFiltroAnual() {{
    const anoInicio = parseInt(document.getElementById('anoInicio').value);
    const anoFim = parseInt(document.getElementById('anoFim').value);
    if(anoInicio > anoFim) {{ alert("Ano inicial não pode ser maior que o final!"); return; }}
    dados = dadosOriginais.filter(d => d.ano >= anoInicio && d.ano <= anoFim);
    redrawAll();
    showMsg(`📅 Período: ${{anoInicio}} até ${{anoFim}} (anos completos)`);
}}

function aplicarFiltroMensal() {{
    const mesInicio = parseInt(document.getElementById('mesInicio').value);
    const anoInicio = parseInt(document.getElementById('anoInicioMes').value);
    const mesFim = parseInt(document.getElementById('mesFim').value);
    const anoFim = parseInt(document.getElementById('anoFimMes').value);
    if(anoInicio > anoFim || (anoInicio === anoFim && mesInicio > mesFim)) {{
        alert("Período inválido!"); return;
    }}

    const base = dadosOriginais.filter(d => d.ano >= anoInicio && d.ano <= anoFim);
    const meses = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];

    dados = base.map(d => {{
        const maxReal = mesMaxDados[d.ano] || 12;
        if(d.ano > anoInicio && d.ano < anoFim) return {{...d}};
        const mIni = d.ano === anoInicio ? mesInicio : 1;
        const mFimReq = d.ano === anoFim ? mesFim : maxReal;
        const mFimEff = Math.min(mFimReq, maxReal);
        const fator = Math.max(0, mFimEff - mIni + 1) / maxReal;
        return {{
            ano: d.ano,
            feminicidio_consumado: Math.round(d.feminicidio_consumado * fator),
            feminicidio_tentado: Math.round(d.feminicidio_tentado * fator),
            ameaca: Math.round(d.ameaca * fator),
            estupro: Math.round(d.estupro * fator),
            lesao_corporal: Math.round(d.lesao_corporal * fator)
        }};
    }});
    redrawAll();
    showMsg(`📆 ${{meses[mesInicio-1]}}/${{anoInicio}} até ${{meses[mesFim-1]}}/${{anoFim}} (acumulado)`);
}}

function limparFiltros() {{
    dados = [...dadosOriginais];
    document.getElementById('anoInicio').value = '2022';
    document.getElementById('anoFim').value = '2026';
    document.getElementById('anoInicioMes').value = '2022';
    document.getElementById('anoFimMes').value = '2026';
    document.getElementById('mesInicio').value = '1';
    document.getElementById('mesFim').value = '12';
    redrawAll();
}}

function toggleCategoria(btn) {{
    const cat = btn.dataset.cat;
    visibleCats[cat] = !visibleCats[cat];
    btn.classList.toggle('active', visibleCats[cat]);
    criarGraficoEvolucao();
}}

function setChartType(type, btn) {{
    currentChartType = type;
    document.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    criarGraficoEvolucao();
}}

function showMsg(txt) {{
    const el = document.getElementById('periodoMsg');
    el.textContent = txt;
    el.style.display = 'block';
    if(window.msgTimeout) clearTimeout(window.msgTimeout);
    window.msgTimeout = setTimeout(() => {{ el.style.display = 'none'; }}, 3500);
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
                print("\n📊 Gerando dados mensais para filtros precisos...")
                df_mensal = self.processar_dados_mensais()
                if df_mensal is not None:
                    print("✅ Dados mensais salvos em dados/indicadores_mensais.json")
                else:
                    print("⚠️ Não foi possível extrair dados mensais dos arquivos")
        else:
            json_path = PASTA_DADOS / 'indicadores_sao_leopoldo.json'
            if json_path.exists():
                print("📁 Carregando dados existentes...")
                with open(json_path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                df = pd.DataFrame(dados)
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
        return jsonify({'status': 'online', 'last_update': str(dash.last_check_time)})
    
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
    print("Versão: 6.0 (Anual + Comparativo Mensal)")
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
    print("\n📊 Criando dashboards iniciais...")
    dash.executar_atualizacao_completa()
    
    print(f"\n✨ Dashboards disponíveis:")
    print(f"   - Anual: {Path.cwd() / 'index.html'}")
    print(f"   - Comparativo Mensal: {Path.cwd() / 'dashboard_comparativo.html'}")
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
            
            cfg = dash.config['schedule']
            if cfg['interval_type'] == 'minutes':
                print(f"⏰ Frequência: A cada {cfg['interval_minutes']} minutos")
            elif cfg['interval_type'] == 'hourly':
                print(f"⏰ Frequência: A cada {cfg['interval_hours']} hora(s)")
            elif cfg['interval_type'] == 'daily':
                print(f"⏰ Horário: {cfg['time']}")
            elif cfg['interval_type'] == 'monthly':
                print(f"⏰ Mensal: Dia {cfg['day_of_month']} às {cfg['time']}")
            
            print("\n✨ Dashboards atualizados automaticamente")
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
            print(f"\n📁 Dashboards:")
            print(f"   - Anual: {Path.cwd() / 'index.html'}")
            print(f"   - Comparativo: {Path.cwd() / 'dashboard_comparativo.html'}")
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
