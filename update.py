from main import AutomatedDashboard
from datetime import datetime, timezone, timedelta

# Horário de Brasília
class BrasiliaTime:
    @staticmethod
    def now():
        return datetime.now(timezone(timedelta(hours=-3)))

print(f"🕐 Executando em: {BrasiliaTime.now().strftime('%d/%m/%Y %H:%M:%S')} (Horário de Brasília)")

dash = AutomatedDashboard()
dash.executar_atualizacao_completa(forcar_scraping=True)  # <-- FORÇA SCRAPING!s
