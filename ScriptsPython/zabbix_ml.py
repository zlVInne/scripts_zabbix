import requests
import urllib3
import time
import pandas as pd
from sklearn.ensemble import IsolationForest
import warnings

# Silencia avisos de SSL e Pandas
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings('ignore')

# ==========================================
# 1. CONFIGURAÇÕES E AUTENTICAÇÃO
# ==========================================
ZABBIX_URL = 'https://172.23.104.62/zabbix/api_jsonrpc.php'
USUARIO = 'ml.api'
SENHA = 'Tropico123'
ID_SBC = "10707" # SBC Ativo

print(">>> [1/6] Conectando ao Zabbix...")
resp_login = requests.post(ZABBIX_URL, json={"jsonrpc": "2.0", "method": "user.login", "params": {"username": USUARIO, "password": SENHA}, "id": 1}, verify=False)
auth_token = resp_login.json().get('result')
headers = {'Content-Type': 'application/json-rpc', 'Authorization': f"Bearer {auth_token}"}

# ==========================================
# 2. DESCOBERTA E CATEGORIZAÇÃO (LLD Dinâmico)
# ==========================================
print(">>> [2/6] Mapeando todos os sensores do equipamento...")
req_items = requests.post(ZABBIX_URL, headers=headers, json={"jsonrpc": "2.0", "method": "item.get", "params": {"hostids": [ID_SBC], "output": ["itemid", "name", "key_", "value_type"]}, "id": 2}, verify=False).json()

itens = req_items.get('result', [])
categorias = {'capacidade': [], 'realms_agents': [], 'regras_ssl_status': []}
mapa_nomes = {}

# Classifica os itens baseando-se no nome que o Zabbix retornou
for item in itens:
    nome = item['name'].lower()
    mapa_nomes[item['itemid']] = item['name']
    
    # Motor Especialista (Regras)
    if 'time left' in nome or 'redundancy' in nome or 'system state' in nome:
        categorias['regras_ssl_status'].append(item)
    # Motor LLD (Realms e Agentes)
    elif 'erro' in nome or 'lattency' in nome or 'completamento' in nome:
        categorias['realms_agents'].append(item)
    # Motor Multivariável (Capacidade)
    elif 'session' in nome or 'nat' in nome or 'arp' in nome or 'cpu' in nome or 'memory' in nome or 'health' in nome or 'cps' in nome:
        categorias['capacidade'].append(item)

# ==========================================
# 3. EXTRAÇÃO DE HISTÓRICO (Últimas 3 horas)
# ==========================================
print(">>> [3/6] Extraindo série temporal para treinamento da IA (com proteção de lotes)...")
agora = int(time.time())
tres_horas_atras = agora - 10800

def buscar_historico(lista_itens):
    dados = []
    # O Zabbix separa os dados em tabelas diferentes (0 = Float/Decimal, 3 = Inteiro)
    for tipo in [0, 3]: 
        ids = [i['itemid'] for i in lista_itens if int(i['value_type']) == tipo]
        if ids:
            # Dividindo a lista de IDs em lotes de 50 para não derrubar a API do Zabbix
            tamanho_lote = 50
            for i in range(0, len(ids), tamanho_lote):
                lote_ids = ids[i:i + tamanho_lote]
                
                resposta = requests.post(
                    ZABBIX_URL, 
                    headers=headers, 
                    json={
                        "jsonrpc": "2.0", 
                        "method": "history.get", 
                        "params": {
                            "output": "extend", 
                            "history": tipo, 
                            "itemids": lote_ids, 
                            "time_from": tres_horas_atras, 
                            "time_till": agora
                        }, 
                        "id": 3
                    }, 
                    verify=False
                )
                
                # Prevenção de quebra caso o Zabbix retorne erro HTTP (como 502 Bad Gateway)
                if resposta.status_code != 200:
                    print(f"    [!] Erro de conexão com a API: HTTP {resposta.status_code}")
                    continue
                
                try:
                    hist = resposta.json()
                    if 'result' in hist:
                        dados.extend(hist['result'])
                    elif 'error' in hist:
                        print(f"    [!] Zabbix retornou erro na consulta: {hist['error'].get('data')}")
                except ValueError:
                    print("    [!] A resposta da API não foi um JSON válido (Provável estouro de memória no Zabbix).")
                    
    return pd.DataFrame(dados)

df_cap_bruto = buscar_historico(categorias['capacidade'])
df_realm_bruto = buscar_historico(categorias['realms_agents'])
df_regras_bruto = buscar_historico(categorias['regras_ssl_status'])

recomendacoes = []

# ==========================================
# 4. MOTOR MULTIVARIÁVEL (CAPACIDADE GLOBAL)
# ==========================================
print(">>> [4/6] Treinando Motor de Capacidade (Multivariável)...")
if not df_cap_bruto.empty:
    df_cap_bruto['clock'] = pd.to_datetime(pd.to_numeric(df_cap_bruto['clock']), unit='s').dt.floor('min')
    df_cap_bruto['value'] = pd.to_numeric(df_cap_bruto['value'])
    df_cap_bruto['metric'] = df_cap_bruto['itemid'].map(mapa_nomes)
    
    # Pivotando a tabela para ter métricas como colunas
    df_cap = df_cap_bruto.pivot_table(index='clock', columns='metric', values='value', aggfunc='mean').fillna(method='ffill').dropna()
    
    if not df_cap.empty:
        features_ia = list(df_cap.columns)
        for col in list(df_cap.columns):
            df_cap[f'delta_{col}'] = df_cap[col].diff().fillna(0)
            features_ia.append(f'delta_{col}')
            
        modelo_cap = IsolationForest(contamination=0.05, random_state=42)
        df_cap['score'] = modelo_cap.fit_predict(df_cap[features_ia])
        
        ultima_leitura_cap = df_cap.iloc[-1]
        
        if ultima_leitura_cap['score'] == -1:
            recomendacoes.append(f"🚨 [CAPACIDADE] Comportamento Global Anômalo! A IA detectou uma quebra de padrão no hardware do SBC.")
            for col in df_cap.columns:
                if 'delta_' in col and ultima_leitura_cap[col] > df_cap[col].mean() * 3:
                    nome_metrica = col.replace('delta_', '')
                    recomendacoes.append(f"   ↳ Possível Causa: Salto repentino violento na métrica '{nome_metrica}'.")

# ==========================================
# 5. MOTOR UNIVARIÁVEL LLD (REALMS E AGENTES)
# ==========================================
print(">>> [5/6] Treinando Motores Distribuídos (Realms/Agents)...")
if not df_realm_bruto.empty:
    df_realm_bruto['clock'] = pd.to_datetime(pd.to_numeric(df_realm_bruto['clock']), unit='s').dt.floor('min')
    df_realm_bruto['value'] = pd.to_numeric(df_realm_bruto['value'])
    df_realm_bruto['metric'] = df_realm_bruto['itemid'].map(mapa_nomes)
    
    metricas_unicas = df_realm_bruto['metric'].unique()
    for metrica in metricas_unicas:
        df_individual = df_realm_bruto[df_realm_bruto['metric'] == metrica].copy()
        if len(df_individual) > 10:
            df_individual['delta'] = df_individual['value'].diff().fillna(0)
            modelo_realm = IsolationForest(contamination=0.03, random_state=42)
            df_individual['score'] = modelo_realm.fit_predict(df_individual[['value', 'delta']])
            
            ultimo_status = df_individual.iloc[-1]
            if ultimo_status['score'] == -1:
                if ultimo_status['delta'] > 0 and 'erro' in metrica.lower():
                    recomendacoes.append(f"⚠️ [ROTEAMENTO] Anomalia no '{metrica}'. Taxa de erro subiu de forma atípica comparado ao padrão deste agente.")

# ==========================================
# 6. MOTOR ESPECIALISTA (REGRAS E STATUS)
# ==========================================
print(">>> [6/6] Executando Validação de Regras e Compliance...")
if not df_regras_bruto.empty:
    df_regras_bruto['clock'] = pd.to_numeric(df_regras_bruto['clock'])
    ultimos_valores = df_regras_bruto.loc[df_regras_bruto.groupby('itemid')['clock'].idxmax()]
    
    for _, linha in ultimos_valores.iterrows():
        nome = mapa_nomes[linha['itemid']].lower()
        valor = float(linha['value'])
        
        if 'time left' in nome:
            if valor < 15:
                recomendacoes.append(f"🔥 [SEGURANÇA CRÍTICA] Certificado SSL '{mapa_nomes[linha['itemid']]}' expira em {valor} dias. Renovar imediatamente.")
            elif valor < 30:
                recomendacoes.append(f"⚠️ [SEGURANÇA] Certificado SSL '{mapa_nomes[linha['itemid']]}' expira em {valor} dias. Planejar renovação.")
        
        elif 'redundancy' in nome:
            if valor not in [2, 3]:
                recomendacoes.append(f"🔥 [HA] Status de redundância do equipamento está fora do padrão Active/Standby (Código atual: {valor}). Verificar estado do cluster.")

# ==========================================
# 7. RELATÓRIO FINAL AIOps
# ==========================================
print("\n=======================================================")
print("             PMI ORACLE SBC — AI REPORT                ")
print("=======================================================")
if not recomendacoes:
    print("✅ Operação Saudável. Nenhuma anomalia comportamental ou quebra de regra detectada nas últimas medições.")
else:
    for rec in recomendacoes:
        print(rec)
print("=======================================================\n")
