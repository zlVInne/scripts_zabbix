#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PMI SBC Collector — Auto Role Version

Consulta dados lentos no PostgreSQL do Zabbix e materializa snapshots no banco pmi_analytics.

Novidade desta versão:
- Detecta automaticamente ACTIVE/STANDBY via apSysRedundancy.
- Usa o host ACTIVE para consultas mais específicas de SIP/Agents/Realms.
- Usa ambos os hosts para HA, latência e recursos.
- Grava pmi.sbc_role_snapshot com o papel atual de cada SBC.

Estratégia de atomicidade:
1) Busca todos os dados no Zabbix primeiro.
2) Se alguma consulta falhar, nada é alterado no banco PMI.
3) Se todas as consultas funcionarem, abre UMA transação no banco PMI.
4) Faz DELETE + INSERT nas tabelas snapshot dentro da mesma transação.
5) COMMIT único. O Grafana nunca enxerga tabela parcialmente atualizada.
"""

import os
import sys
import time
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Sequence

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values


# ============================================================
# CONFIGURAÇÃO
# ============================================================

ZABBIX_DB = {
    "host": os.getenv("ZABBIX_DB_HOST", "localhost"),
    "port": int(os.getenv("ZABBIX_DB_PORT", "5432")),
    "dbname": os.getenv("ZABBIX_DB_NAME", "zabbix"),
    "user": os.getenv("ZABBIX_DB_USER", "zabbix"),
    "password": os.getenv("ZABBIX_DB_PASSWORD", "brisanet"),
}

PMI_DB = {
    "host": os.getenv("PMI_DB_HOST", "localhost"),
    "port": int(os.getenv("PMI_DB_PORT", "5432")),
    "dbname": os.getenv("PMI_DB_NAME", "pmi_analytics"),
    "user": os.getenv("PMI_DB_USER", "pmi_user"),
    "password": os.getenv("PMI_DB_PASSWORD", "pmi_user"),
}

HOSTS_SBC = tuple(
    h.strip()
    for h in os.getenv("PMI_SBC_HOSTS", "SBC_172.26.40.175,SBC_172.26.40.75").split(",")
    if h.strip()
)

# Fallbacks. Só serão usados se não for possível detectar via apSysRedundancy.
HOST_PRINCIPAL_FALLBACK = os.getenv("PMI_SBC_HOST_PRINCIPAL", "SBC_172.26.40.175")
HOST_STANDBY_FALLBACK = os.getenv("PMI_SBC_HOST_STANDBY", "SBC_172.26.40.75")

LOG_LEVEL = os.getenv("PMI_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


# ============================================================
# CONEXÃO
# ============================================================

@contextmanager
def db_conn(cfg: Dict[str, Any], readonly: bool = False):
    conn = psycopg2.connect(**cfg)
    try:
        conn.autocommit = False
        if readonly:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_all(conn, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def replace_table(conn, table: str, columns: Sequence[str], rows: List[Dict[str, Any]]) -> int:
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM {table};")

        if not rows:
            logging.warning("Tabela %s recebeu 0 linhas. Snapshot ficará vazio após commit.", table)
            return 0

        values = [[row.get(col) for col in columns] for row in rows]
        execute_values(
            cur,
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s",
            values,
            page_size=1000,
        )
        return len(rows)


# ============================================================
# DETECÇÃO ACTIVE/STANDBY
# ============================================================

def redundancy_label(code):
    mapping = {
        0: "UNKNOWN",
        1: "INITIAL",
        2: "ACTIVE",
        3: "STANDBY",
        4: "OUT_OF_SERVICE",
        5: "UNASSIGNED",
        6: "ACTIVE_PENDING",
        7: "STANDBY_PENDING",
        8: "OUT_OF_SERVICE_PENDING",
        9: "RECOVERY",
    }
    return mapping.get(int(code) if code is not None else -1, "UNKNOWN")


def detect_active_standby(conn) -> Dict[str, Any]:
    sql = """
    WITH ultimos AS (
        SELECT DISTINCT ON (h.host)
            h.host,
            hu.value::int AS redundancy_code,
            hu.clock
        FROM hosts h
        JOIN items i ON i.hostid = h.hostid
        JOIN history_uint hu ON hu.itemid = i.itemid
        WHERE h.host = ANY(%s)
          AND i.key_ = 'apSysRedundancy'
        ORDER BY h.host, hu.clock DESC
    )
    SELECT
        host,
        redundancy_code,
        CASE redundancy_code
            WHEN 2 THEN 'ACTIVE'
            WHEN 3 THEN 'STANDBY'
            WHEN 0 THEN 'UNKNOWN'
            WHEN 1 THEN 'INITIAL'
            WHEN 4 THEN 'OUT_OF_SERVICE'
            WHEN 5 THEN 'UNASSIGNED'
            WHEN 6 THEN 'ACTIVE_PENDING'
            WHEN 7 THEN 'STANDBY_PENDING'
            WHEN 8 THEN 'OUT_OF_SERVICE_PENDING'
            WHEN 9 THEN 'RECOVERY'
            ELSE 'UNKNOWN'
        END AS role_detected,
        to_timestamp(clock)::timestamp AS last_collection,
        now()::timestamp AS updated_at
    FROM ultimos
    ORDER BY host;
    """

    rows = fetch_all(conn, sql, (list(HOSTS_SBC),))

    active = next((r["host"] for r in rows if r["role_detected"] == "ACTIVE"), None)
    standby = next((r["host"] for r in rows if r["role_detected"] == "STANDBY"), None)

    if not active:
        active = HOST_PRINCIPAL_FALLBACK
        logging.warning("Não foi possível detectar ACTIVE. Usando fallback: %s", active)

    if not standby:
        standby = HOST_STANDBY_FALLBACK
        logging.warning("Não foi possível detectar STANDBY. Usando fallback: %s", standby)

    logging.info("Role detectado: ACTIVE=%s | STANDBY=%s", active, standby)

    return {
        "active": active,
        "standby": standby,
        "roles": rows,
    }


# ============================================================
# COLETORES
# ============================================================

def collect_ha_snapshot(conn) -> List[Dict[str, Any]]:
    sql = """
    WITH ultimos AS (
        SELECT DISTINCT ON (h.host, i.key_)
            h.host,
            i.key_,
            hu.value::numeric AS value,
            hu.clock
        FROM hosts h
        JOIN items i ON i.hostid = h.hostid
        JOIN history_uint hu ON hu.itemid = i.itemid
        WHERE h.host = ANY(%s)
          AND i.key_ IN (
              'apSysGlobalCPS',
              'apSysGlobalConSess',
              'apSysLicenseCapacity',
              'apSysNATCapacity',
              'apSysARPCapacity',
              'apSysRedundancy'
          )
        ORDER BY h.host, i.key_, hu.clock DESC
    )
    SELECT
        host,
        MAX(value) FILTER (WHERE key_ = 'apSysGlobalCPS') AS cps,
        MAX(value) FILTER (WHERE key_ = 'apSysGlobalConSess') AS sessoes,
        MAX(value) FILTER (WHERE key_ = 'apSysLicenseCapacity') AS licencas_pct,
        MAX(value) FILTER (WHERE key_ = 'apSysNATCapacity') AS nat_pct,
        MAX(value) FILTER (WHERE key_ = 'apSysARPCapacity') AS arp_pct,
        MAX(value) FILTER (WHERE key_ = 'apSysRedundancy') AS redundancy_code,
        CASE MAX(value) FILTER (WHERE key_ = 'apSysRedundancy')
            WHEN 2 THEN 'ACTIVE'
            WHEN 3 THEN 'STANDBY'
            WHEN 0 THEN 'UNKNOWN'
            WHEN 1 THEN 'INITIAL'
            WHEN 4 THEN 'OUT_OF_SERVICE'
            WHEN 5 THEN 'UNASSIGNED'
            WHEN 6 THEN 'ACTIVE_PENDING'
            WHEN 7 THEN 'STANDBY_PENDING'
            WHEN 8 THEN 'OUT_OF_SERVICE_PENDING'
            WHEN 9 THEN 'RECOVERY'
            ELSE 'UNKNOWN'
        END AS estado_ha,
        now()::timestamp AS updated_at
    FROM ultimos
    GROUP BY host
    ORDER BY host;
    """
    return fetch_all(conn, sql, (list(HOSTS_SBC),))


def collect_realm_error_snapshot(conn, host_active: str) -> List[Dict[str, Any]]:
    sql = """
    WITH itens AS (
        SELECT h.host, i.itemid, i.name
        FROM items i
        JOIN hosts h ON h.hostid = i.hostid
        WHERE h.host = %s
          AND (
                i.name ILIKE '%%erro%%'
             OR i.name ILIKE '%%error%%'
             OR i.name ILIKE '%%fail%%'
          )
    ),
    ultimos AS (
        SELECT DISTINCT ON (it.itemid)
            it.host,
            it.name,
            hu.value::numeric AS value,
            hu.clock
        FROM itens it
        JOIN history_uint hu ON hu.itemid = it.itemid
        ORDER BY it.itemid, hu.clock DESC
    )
    SELECT
        host,
        COALESCE(NULLIF(regexp_replace(name, '^Taxa de Erro - ', ''), ''), name) AS realm_erro,
        value,
        now()::timestamp AS updated_at
    FROM ultimos
    ORDER BY value DESC NULLS LAST
    LIMIT 200;
    """
    return fetch_all(conn, sql, (host_active,))


def collect_latency_snapshot(conn) -> List[Dict[str, Any]]:
    sql = """
    WITH itens AS (
        SELECT h.host, i.itemid, i.name, i.value_type
        FROM items i
        JOIN hosts h ON h.hostid = i.hostid
        WHERE h.host = ANY(%s)
          AND (
                i.name ILIKE '%%lat%%'
             OR i.name ILIKE '%%latt%%'
             OR i.name ILIKE '%%delay%%'
             OR i.name ILIKE '%%response%%'
          )
    ),
    dados_float AS (
        SELECT DISTINCT ON (it.itemid)
            it.host, it.name, hf.value::numeric AS value, hf.clock
        FROM itens it
        JOIN history hf ON hf.itemid = it.itemid
        WHERE it.value_type = 0
        ORDER BY it.itemid, hf.clock DESC
    ),
    dados_uint AS (
        SELECT DISTINCT ON (it.itemid)
            it.host, it.name, hu.value::numeric AS value, hu.clock
        FROM itens it
        JOIN history_uint hu ON hu.itemid = it.itemid
        WHERE it.value_type = 3
        ORDER BY it.itemid, hu.clock DESC
    )
    SELECT host, name AS metrica, value, now()::timestamp AS updated_at
    FROM (
        SELECT * FROM dados_float
        UNION ALL
        SELECT * FROM dados_uint
    ) x
    ORDER BY value DESC NULLS LAST
    LIMIT 200;
    """
    return fetch_all(conn, sql, (list(HOSTS_SBC),))


def collect_traffic_distribution_snapshot(conn, host_active: str) -> List[Dict[str, Any]]:
    sql = """
    WITH itens AS (
        SELECT h.host, i.itemid, i.name
        FROM items i
        JOIN hosts h ON h.hostid = i.hostid
        WHERE h.host = %s
          AND (
                i.name ILIKE '%%session%%'
             OR i.name ILIKE '%%call%%'
             OR i.name ILIKE '%%cps%%'
          )
    ),
    ultimos AS (
        SELECT DISTINCT ON (it.itemid)
            it.host,
            it.name,
            hu.value::numeric AS value,
            hu.clock
        FROM itens it
        JOIN history_uint hu ON hu.itemid = it.itemid
        ORDER BY it.itemid, hu.clock DESC
    )
    SELECT host, name AS metrica, value, now()::timestamp AS updated_at
    FROM ultimos
    ORDER BY value DESC NULLS LAST
    LIMIT 300;
    """
    return fetch_all(conn, sql, (host_active,))


def collect_agent_status_snapshot(conn, host_active: str) -> List[Dict[str, Any]]:
    sql = """
    WITH ultimos AS (
        SELECT DISTINCT ON (i.itemid)
            h.host,
            i.name,
            i.key_,
            hu.value::numeric AS value,
            hu.clock
        FROM hosts h
        JOIN items i ON i.hostid = h.hostid
        JOIN history_uint hu ON hu.itemid = i.itemid
        WHERE h.host = %s
          AND i.key_ LIKE 'SIPSessionAgentStatsEntry.%%'
        ORDER BY i.itemid, hu.clock DESC
    )
    SELECT
        host,
        regexp_replace(name, '^Agent (.*) status$', '\\1') AS agent,
        value AS status_code,
        CASE
            WHEN value IN (1,2) THEN 'ONLINE'
            WHEN value IN (3,4) THEN 'WARNING'
            WHEN value = 0 THEN 'OFFLINE'
            ELSE 'UNKNOWN'
        END AS status_interpretado,
        now()::timestamp AS updated_at
    FROM ultimos
    ORDER BY agent;
    """
    return fetch_all(conn, sql, (host_active,))


def collect_system_resources_snapshot(conn) -> List[Dict[str, Any]]:
    sql = """
    WITH itens AS (
        SELECT h.host, i.itemid, i.name, i.value_type
        FROM items i
        JOIN hosts h ON h.hostid = i.hostid
        WHERE h.host = ANY(%s)
          AND (
                i.name ILIKE '%%cpu%%'
             OR i.name ILIKE '%%memory%%'
             OR i.name ILIKE '%%mem%%'
             OR i.name ILIKE '%%disk%%'
             OR i.name ILIKE '%%filesystem%%'
             OR i.name ILIKE '%%health%%'
             OR i.name ILIKE '%%utilization%%'
             OR i.name ILIKE '%%space%%'
          )
    ),
    dados_float AS (
        SELECT DISTINCT ON (it.itemid)
            it.host, it.name, hf.value::numeric AS value, hf.clock
        FROM itens it
        JOIN history hf ON hf.itemid = it.itemid
        WHERE it.value_type = 0
        ORDER BY it.itemid, hf.clock DESC
    ),
    dados_uint AS (
        SELECT DISTINCT ON (it.itemid)
            it.host, it.name, hu.value::numeric AS value, hu.clock
        FROM itens it
        JOIN history_uint hu ON hu.itemid = it.itemid
        WHERE it.value_type = 3
        ORDER BY it.itemid, hu.clock DESC
    )
    SELECT
        host,
        name AS metrica,
        value,
        to_timestamp(clock)::timestamp AS ultima_coleta,
        now()::timestamp AS updated_at
    FROM (
        SELECT * FROM dados_float
        UNION ALL
        SELECT * FROM dados_uint
    ) x
    ORDER BY host, metrica;
    """
    return fetch_all(conn, sql, (list(HOSTS_SBC),))


# ============================================================
# FLUXO PRINCIPAL
# ============================================================

def collect_all() -> Dict[str, List[Dict[str, Any]]]:
    logging.info("Coletando dados do Zabbix: %s", ZABBIX_DB["dbname"])

    with db_conn(ZABBIX_DB, readonly=True) as zbx:
        role_info = detect_active_standby(zbx)
        active_host = role_info["active"]

        data = {
            "sbc_role_snapshot": role_info["roles"],
            "sbc_ha_snapshot": collect_ha_snapshot(zbx),
            "sbc_realm_error_snapshot": collect_realm_error_snapshot(zbx, active_host),
            "sbc_latency_snapshot": collect_latency_snapshot(zbx),
            "sbc_traffic_distribution_snapshot": collect_traffic_distribution_snapshot(zbx, active_host),
            "sbc_agent_status_snapshot": collect_agent_status_snapshot(zbx, active_host),
            "sbc_system_resources_snapshot": collect_system_resources_snapshot(zbx),
        }

    for table, rows in data.items():
        logging.info("%s: %d linhas coletadas", table, len(rows))

    return data


def load_all(data: Dict[str, List[Dict[str, Any]]]) -> None:
    logging.info("Atualizando banco PMI: %s", PMI_DB["dbname"])

    table_columns = {
        "sbc_role_snapshot": [
            "host", "redundancy_code", "role_detected", "last_collection", "updated_at"
        ],
        "sbc_ha_snapshot": [
            "host", "cps", "sessoes", "licencas_pct", "nat_pct",
            "arp_pct", "redundancy_code", "estado_ha", "updated_at"
        ],
        "sbc_realm_error_snapshot": [
            "host", "realm_erro", "value", "updated_at"
        ],
        "sbc_latency_snapshot": [
            "host", "metrica", "value", "updated_at"
        ],
        "sbc_traffic_distribution_snapshot": [
            "host", "metrica", "value", "updated_at"
        ],
        "sbc_agent_status_snapshot": [
            "host", "agent", "status_code", "status_interpretado", "updated_at"
        ],
        "sbc_system_resources_snapshot": [
            "host", "metrica", "value", "ultima_coleta", "updated_at"
        ],
    }

    with db_conn(PMI_DB, readonly=False) as pmi:
        with pmi.cursor() as cur:
            cur.execute("SET LOCAL lock_timeout = '10s';")
            cur.execute("SET LOCAL statement_timeout = '60s';")

        total = 0
        for table, columns in table_columns.items():
            qtd = replace_table(pmi, table, columns, data.get(table, []))
            logging.info("%s: %d linhas gravadas", table, qtd)
            total += qtd

    logging.info("Carga concluída com sucesso. Total de linhas gravadas: %d", total)


def run_once() -> None:
    start = time.time()
    data = collect_all()
    load_all(data)
    elapsed = time.time() - start
    logging.info("Ciclo finalizado em %.2fs", elapsed)


def main():
    try:
        run_once()
    except Exception as exc:
        logging.exception("Falha no ciclo do coletor: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()

