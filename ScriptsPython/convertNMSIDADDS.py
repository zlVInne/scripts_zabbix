#!/usr/bin/env python3
import re
import sys
import json

def parse_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    blocks = []
    current_block = {}
    service_data = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detecta novo bloco
        if line.startswith("VECTURA") or line.startswith("VSI BRISANET"):
            if current_block:
                current_block["SERVICOS"] = service_data
                blocks.append(current_block)
                current_block = {}
                service_data = []

        # Captura PRO
        elif line.startswith("IDADDS:"):
            match = re.search(r"PRO=(\d+)", line)
            if match:
                current_block["PRO"] = int(match.group(1))

        # Captura linhas de serviço
        elif any(svc in line for svc in [
            "TRANSLAC","LOG_CHAM","CASE","PORTAB",
            "B_PORTAB","B_MULTF","DSEL_A","ENCAM_AB","TRAD_NUM"
        ]):
            parts = re.split(r"\s{2,}", line)
            if len(parts) >= 6:
                service_name = parts[0]
                try:
                    values = list(map(int, parts[1:6]))
                except ValueError:
                    continue

                # Converte para objeto com PERIODO1...5
                service_obj = {"SERVICO": service_name}
                for i, v in enumerate(values, start=1):
                    service_obj[f"PERIODO{i}"] = v
                service_data.append(service_obj)

    # Último bloco
    if current_block:
        current_block["SERVICOS"] = service_data
        blocks.append(current_block)

    return blocks

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python script.py <caminho_do_arquivo>")
        sys.exit(1)

    filepath = sys.argv[1]
    result = parse_file(filepath)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))

