import re
import json
import pexpect
import sys
import os

# Senha hardcoded conforme solicitado
SENHA_ROOT = "wqIrbA0ZF6Q5nM"

def baixar_arquivo_dbclient(ip, password, caminho_remoto, caminho_local):
    """
    Automatiza o dbclient para baixar o arquivo.
    """
    comando = f'dbclient root@{ip} "cat {caminho_remoto}" > {caminho_local}'
    print(f"[*] Iniciando download do arquivo {caminho_local}...")

    child = pexpect.spawn(f'/bin/bash -c \'{comando}\'', encoding='utf-8', timeout=30)

    try:
        child.expect(['(?i)password:'])
        child.sendline(password)
        child.expect(pexpect.EOF)
        print(f"[+] Download arquivo {caminho_local} concluido!")
    except pexpect.TIMEOUT:
        print(f"[-] Timeout ao tentar baixar {caminho_local}. Verifique a conexao com {ip}.")
        sys.exit(1)
    except Exception as e:
        print(f"[-] Erro ao baixar {caminho_local}: {e}")
        sys.exit(1)

def extrair_capacidade(arquivo_icapea):
    capacidade_map = {}
    with open(arquivo_icapea, 'r', encoding='utf-8') as f:
        linhas = f.readlines()

    for linha in linhas:
        partes = linha.split()
        if len(partes) >= 4 and partes[0].isdigit():
            igr = partes[0]
            cap = partes[-1]
            capacidade_map[igr] = int(cap)

    print(f"[+] Parse arquivo {arquivo_icapea} concluido!")
    return capacidade_map

def extrair_nomes_igr(arquivo_rcc):
    """
    Lê o arquivo .RCC e mapeia o número do IGR para o seu respectivo nome (INM).
    """
    nomes_map = {}
    if not os.path.exists(arquivo_rcc):
        print(f"[-] Arquivo de nomes {arquivo_rcc} nao encontrado. Os IGRs ficarao sem nome.")
        return nomes_map

    with open(arquivo_rcc, 'r', encoding='utf-8', errors='ignore') as f:
        conteudo = f.read()

    # Expressão regular para capturar "IGR = <numero>" e "INM = <nome>"
    # Trata espaços extras que possam existir no arquivo
    padrao = re.compile(r'IGR\s*=\s*(\d+)\s+INM\s*=\s*([a-zA-Z0-9_-]+)')
    matches = padrao.findall(conteudo)

    for igr, inm in matches:
        nomes_map[int(igr)] = inm

    print(f"[+] Parse arquivo de nomes {arquivo_rcc} concluido! {len(nomes_map)} nomes mapeados.")
    return nomes_map

def processar_dados_sip(arquivo_itrase, capacidade_map, nomes_map, ip_servidor):
    with open(arquivo_itrase, 'r', encoding='utf-8') as f:
        conteudo = f.read()

    blocos = conteudo.split("PRO =")

    # ---------------------------------------------------------
    # 0. MAPEAR APENAS O PICO MÁXIMO POR (IGR, PRO)
    # Evita duplicações causadas por múltiplos períodos no arquivo
    # ---------------------------------------------------------
    dados_maximos = {}

    for bloco in blocos[1:]:
        linhas = bloco.strip().split('\n')
        linha_cabecalho = lines[0] if 'lines' in locals() else linhas[0]

        match_cabecalho = re.search(r'(\d+)\s+IGR\s*=\s*(\d+)', linha_cabecalho)
        if not match_cabecalho:
            continue

        pro, igr = match_cabecalho.groups()
        pro = int(pro)
        igr = int(igr)

        match_max = re.search(r'MAX ATINGIDO\s+(\d+)\s+(\d+)', bloco)
        if not match_max:
            continue

        _, max_simultaneas = match_max.groups()
        max_simultaneas = int(max_simultaneas)

        chave = (igr, pro)
        if chave not in dados_maximos:
            dados_maximos[chave] = max_simultaneas
        else:
            dados_maximos[chave] = max(dados_maximos[chave], max_simultaneas)

    # ---------------------------------------------------------
    # 1 & 2. PREPARAR DADOS DETALHADOS E SUMARIZADOS SIMULTANEAMENTE
    # ---------------------------------------------------------
    lista_detalhada = []
    agrupamento_igr = {}

    for (igr, pro), max_simultaneas in dados_maximos.items():
        cap_por_pro = capacidade_map.get(str(igr), 0)
        nome_igr = nomes_map.get(igr, "Desconhecido") # Busca o nome ou define Desconhecido

        # Lógica para o JSON Detalhado
        utilizacao_det = (max_simultaneas / cap_por_pro * 100) if cap_por_pro > 0 else 0
        sessoes_excedentes_det = max_simultaneas - cap_por_pro if max_simultaneas > cap_por_pro else 0

        if utilizacao_det > 50:
            risco_det = "🔴 Critico"
        elif utilizacao_det >= 45:
            risco_det = "🟡 Atencao"
        else:
            risco_det = "🟢 Normal"

        lista_detalhada.append({
            "Servidor": ip_servidor,
            "IGR": igr,
            "Nome_IGR": nome_igr, # Nova chave inserida aqui
            "PRO": pro,
            "Capacidade_Por_COSIP": cap_por_pro,
            "Max_Sessoes_Simultaneas": max_simultaneas,
            "Utilizacao_Porcentagem": round(utilizacao_det, 2),
            "Sessoes_Excedentes": sessoes_excedentes_det,
            "Nivel_Risco": risco_det
        })

        if igr not in agrupamento_igr:
            agrupamento_igr[igr] = {}
        agrupamento_igr[igr][pro] = max_simultaneas

    # ---------------------------------------------------------
    # 3. CONSOLIDAR ARQUIVO SUMARIZADO
    # ---------------------------------------------------------
    lista_sumarizada = []

    qtd_critico = 0
    qtd_atencao = 0
    qtd_normal = 0

    for igr, pros in agrupamento_igr.items():
        cap_por_pro = capacidade_map.get(str(igr), 0)
        qtd_processadores = len(pros)
        nome_igr = nomes_map.get(igr, "Desconhecido") # Busca o nome para o resumido também

        soma_capacidade = cap_por_pro * qtd_processadores
        soma_pico = sum(pros.values())
        soma_excedentes = soma_pico - soma_capacidade if soma_pico > soma_capacidade else 0

        utilizacao_sum = (soma_pico / soma_capacidade * 100) if soma_capacidade > 0 else 0

        if utilizacao_sum >= 50:
            status_sum = "🔴 Critico"
            qtd_critico += 1
        elif utilizacao_sum >= 45:
            status_sum = "🟡 Atencao"
            qtd_atencao += 1
        else:
            status_sum = "🟢 Normal"
            qtd_normal += 1

        lista_sumarizada.append({
            "Servidor": ip_servidor,
            "IGR": igr,
            "Nome_IGR": nome_igr, # Nova chave inserida aqui
            "Qtd_Processadores": qtd_processadores,
            "Capacidade_Total": soma_capacidade,
            "Pico_Total": soma_pico,
            "Excedentes_Total": soma_excedentes,
            "Utilizacao_Porcentagem": round(utilizacao_sum, 2),
            "Status": status_sum
        })

    # ---------------------------------------------------------
    # 4. CRIAR O ARQUIVO DE CONTAGEM DE STATUS
    # ---------------------------------------------------------
    resumo_status = {
        "Servidor": ip_servidor,
        "Total_IGRs": len(lista_sumarizada),
        "Status_Contagem": {
            "🔴 Critico": qtd_critico,
            "🟡 Atencao": qtd_atencao,
            "🟢 Normal": qtd_normal
        }
    }

    print("[+] Parse, Sumarizacao e Contagem de Status concluidos!")

    lista_detalhada = sorted(lista_detalhada, key=lambda x: (x['IGR'], x['PRO']))
    lista_sumarizada = sorted(lista_sumarizada, key=lambda x: x['IGR'])

    return (
        json.dumps(lista_detalhada, indent=4),
        json.dumps(lista_sumarizada, indent=4),
        json.dumps(resumo_status, indent=4)
    )

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python3 parser_sip.py <IP_SERVIDOR>")
        sys.exit(1)

    ip_alvo = sys.argv[1]

    # Define os caminhos exatos
    DIR_SCRIPTS = "/etc/zabbix/scripts/"
    DIR_TXT = "/etc/zabbix/scripts/sip_data/"
    DIR_JSON = "/var/www/html/"

    # Novo arquivo mapeado dinamicamente com base no IP informado na execução
    arq_nomes_rcc = f'{DIR_SCRIPTS}IGRUEA_{ip_alvo}.RCC'

    arq_icapea = f'{DIR_TXT}icapea_{ip_alvo}.txt'
    arq_itrase = f'{DIR_TXT}itrase_pro_{ip_alvo}.txt'

    arq_json_detalhado = f'{DIR_JSON}resultado_sip_detalhado_{ip_alvo}.json'
    arq_json_sumarizado = f'{DIR_JSON}resultado_sip_sumarizado_{ip_alvo}.json'
    arq_json_status = f'{DIR_JSON}resultado_sip_status_{ip_alvo}.json'

    print(f"=== Iniciando Extracao de Dados SIP: {ip_alvo} ===")

    # 1. Download nos diretórios do zabbix
    baixar_arquivo_dbclient(ip_alvo, SENHA_ROOT, "/mat/ftp/icapea.txt", arq_icapea)
    baixar_arquivo_dbclient(ip_alvo, SENHA_ROOT, "/mat/ftp/itrase_pro.txt", arq_itrase)

    # 2. Parse e processamento dos dados
    mapa_capacidade = extrair_capacidade(arq_icapea)
    mapa_nomes = extrair_nomes_igr(arq_nomes_rcc) # Executa o parse do novo arquivo .RCC
    
    json_detalhado, json_sumarizado, json_status = processar_dados_sip(arq_itrase, mapa_capacidade, mapa_nomes, ip_alvo)

    # 3. Salvar os JSONs na pasta web
    with open(arq_json_detalhado, 'w', encoding='utf-8') as f:
        f.write(json_detalhado)
    print(f"[+] Arquivo JSON detalhado salvo: {arq_json_detalhado}")

    with open(arq_json_sumarizado, 'w', encoding='utf-8') as f:
        f.write(json_sumarizado)
    print(f"[+] Arquivo JSON sumarizado salvo: {arq_json_sumarizado}")

    with open(arq_json_status, 'w', encoding='utf-8') as f:
        f.write(json_status)
    print(f"[+] Arquivo JSON status salvo: {arq_json_status}")

    print("=== Execucao Finalizada ===")
