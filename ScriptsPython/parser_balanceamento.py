import json
import sys
import os

def calcular_balanceamento(ip1, ip2):
    caminho_base = "/var/www/html/"
    arquivo_ip1 = f"{caminho_base}resultado_sip_sumarizado_{ip1}.json"
    arquivo_ip2 = f"{caminho_base}resultado_sip_sumarizado_{ip2}.json"

    def obter_pico_total(arquivo):
        if not os.path.exists(arquivo):
            print(f"[-] Arquivo não encontrado: {arquivo}")
            return 0
        try:
            with open(arquivo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                return sum(item.get("Pico_Total", 0) for item in dados)
        except Exception as e:
            print(f"[-] Erro ao ler {arquivo}: {e}")
            return 0

    # 1. Coleta o uso (Pico Total) de cada servidor
    uso_ip1 = obter_pico_total(arquivo_ip1)
    uso_ip2 = obter_pico_total(arquivo_ip2)
    
    total_uso = uso_ip1 + uso_ip2

    # 2. Calcula as porcentagens
    if total_uso > 0:
        perc_ip1 = round((uso_ip1 / total_uso) * 100, 2)
        perc_ip2 = round((uso_ip2 / total_uso) * 100, 2)
    else:
        perc_ip1 = perc_ip2 = 0

    # 3. Define o status de saúde do balanceamento (margem de tolerância de 40% a 60%)
    if 40 <= perc_ip1 <= 60:
        status = "🟢 Balanceado"
    else:
        status = "🔴 Desbalanceado"

    # 4. Prepara o JSON de saída
    resultado = {
        "Indicador": "Balanceamento de Trafego VSI",
        "Total_Tráfego_Combinado": total_uso,
        "Status": status,
        "Servidores": [
            {
                "IP": ip1,
                "IGRs_Em_Uso": uso_ip1,
                "Porcentagem_Carga": perc_ip1
            },
            {
                "IP": ip2,
                "IGRs_Em_Uso": uso_ip2,
                "Porcentagem_Carga": perc_ip2
            }
        ]
    }

    # 5. Salva o resultado para o Grafana/Zabbix consumir
    arquivo_saida = f"{caminho_base}resultado_balanceamento_sip.json"
    with open(arquivo_saida, 'w', encoding='utf-8') as f:
        json.dump(resultado, f, indent=4)
        
    print(f"[+] Balanceamento calculado! IP1: {perc_ip1}% | IP2: {perc_ip2}%")
    print(f"[+] Arquivo gerado: {arquivo_saida}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 parser_balanceamento.py <IP_1> <IP_2>")
        sys.exit(1)

    ip1 = sys.argv[1]
    ip2 = sys.argv[2]
    
    calcular_balanceamento(ip1, ip2)
