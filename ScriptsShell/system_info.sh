#!/bin/bash

# Função para converter uptime para timestamp Unix
get_boot_timestamp() {
    boot_timestamp=$(date -d "$(uptime -s)" +%s)

    echo "$boot_timestamp"
}

# Função para capturar informações de disco e converter para bytes
get_disk_info() {
    disk_info=$(df -hP | grep '^/dev/' | awk '
    function to_bytes(value,   num, unit) {
        num = substr(value, 1, length(value)-1)
        unit = substr(value, length(value), 1)
        if (unit == "G") return num * 1024 * 1024 * 1024
        else if (unit == "M") return num * 1024 * 1024
        else if (unit == "K") return num * 1024
        else if (unit == "T") return num * 1024 * 1024 * 1024 * 1024
        else return num  # assume bytes if no unit
    }
    {
        size_bytes = to_bytes($2)
        used_bytes = to_bytes($3)
        avail_bytes = to_bytes($4)
        print "{\"Device\":\""$1"\",\"Size\":"size_bytes",\"Used\":"used_bytes",\"Available\":"avail_bytes",\"Usage\":\""$5"\",\"Mounted_on\":\""$6"\"}"
    }' | tr '\n' ',' | sed 's/,$//')
    echo "[$disk_info]"
}

# Função para capturar informações de rede
get_network_info() {
    network_info="["
    while IFS= read -r line; do
        iface=$(echo "$line" | awk -F':' '{gsub(/ /, "", $1); print $1}')
        if [ -n "$iface" ]; then
            rx_bytes=$(echo "$line" | awk '{print $2}')
            tx_bytes=$(echo "$line" | awk '{print $10}')
            rx_packets=$(echo "$line" | awk '{print $3}')
            tx_packets=$(echo "$line" | awk '{print $11}')
            tx_errors=$(echo "$line" | awk '{print $12}')

            network_info="${network_info}{\"Interface\":\"$iface\",\"Errors/s\":\"$tx_errors\",\"InTraffic bps\":\"$rx_bytes\",\"OutTraffic bps\":\"$tx_bytes\",\"InTraffic pkps\":\"$rx_packets\",\"OutTraffic pkps\":\"$tx_packets\"},"
        fi
    done < <(tail -n +3 /proc/net/dev)

    network_info=$(echo "$network_info" | sed 's/,$//')
    network_info="$network_info]"

    echo "$network_info"
}

# Captura informações de CPU e memória
cpu_info=$(grep '^cpu ' /proc/stat)
cpu_times=($cpu_info)

user=${cpu_times[1]}
nice=${cpu_times[2]}
system=${cpu_times[3]}
idle=${cpu_times[4]}

total_time=$((user + nice + system + idle))
cpu_idle_utilization=$(awk "BEGIN {print (100 * $idle / $total_time)}")



num_cpus=$(grep -c '^processor' /proc/cpuinfo)
load_avg=$(cat /proc/loadavg)
load_avg_values=($load_avg)
interrupts=$(vmstat 1 2 | tail -1 | awk '{print $11}')







# Captura informações de memória usando o comando 'free'
mem_info=$(free -b)
total_mem=$(echo "$mem_info" | awk '/Mem:/ {print $2}')
available_mem=$(echo "$mem_info" | awk '/buffers\/cache:/ {print $4}')
mem_utilization=$(awk "BEGIN {print (100 * ($total_mem - $available_mem) / $total_mem)}")
total_swap=$(echo "$mem_info" | awk '/Swap:/ {print $2}')
free_swap=$(echo "$mem_info" | awk '/Swap:/ {print $4}')
free_swap_percent=$(awk "BEGIN {if ($total_swap > 0) print (100 * $free_swap / $total_swap); else print 0}")

# Informações do sistema
boot_timestamp=$(get_boot_timestamp)
system_description=$(uname -a)
system_local_time=$(date)
system_name=$(uname -n)
system_uptime=$(awk '{print int($1)}' /proc/uptime)

# Sensores Miscellaneous
context_switches_per_sec=$(grep ctxt /proc/stat | awk '{print $2}')
node_exporter_version=$(node_exporter --version 2>&1 | grep "version" | awk '{print $3}')
max_open_files=$(ulimit -n)
open_file_descriptors=$(lsof | wc -l)

# Sensores de Disco
disk_info=$(get_disk_info)

# Sensores de Rede
network_info=$(get_network_info)

# Informações sobre sockets
udp_stab=$(netstat -ua | grep 'UNCONN' | wc -l)
udp_close_wait=$(netstat -ua | grep 'CLOSE-WAIT' | wc -l)
tcp_stab=$(netstat -ta | grep 'ESTABLISHED' | wc -l)
tcp_close_wait=$(netstat -ta | grep 'CLOSE-WAIT' | wc -l)

# Criação do arquivo JSON manualmente
json_output=$(cat <<EOF
{
  "CPU Metrics": {
    "CPU Guest Nice Time": "${cpu_times[10]}",
    "CPU Guest Time": "${cpu_times[9]}",
    "CPU Idle Time": "${cpu_times[4]}",
    "CPU Interrupt Time": "${cpu_times[6]}",
    "CPU IOWait Time": "${cpu_times[5]}",
    "CPU Nice Time": "${cpu_times[2]}",
    "CPU SoftIRQ Time": "${cpu_times[8]}",
    "CPU Steal Time": "${cpu_times[7]}",
    "CPU System Time": "${cpu_times[3]}",
    "CPU User Time": "${cpu_times[1]}",
    "CPU Idle Time Utilization": "${cpu_idle_utilization}",
    "Number of CPUs": "$num_cpus",
    "Load Average 1m": "${load_avg_values[0]}",
    "Load Average 5m": "${load_avg_values[1]}",
    "Load Average 15m": "${load_avg_values[2]}",
    "Interrupts per Second": "$interrupts"
  },
  "Memory Metrics": {
    "Total Memory (Bytes)": "$total_mem",
    "Available Memory (Bytes)": "$available_mem",
    "Memory Utilization (%)": "$mem_utilization",
    "Total Swap Space (Bytes)": "$total_swap",
    "Free Swap Space (Bytes)": "$free_swap",
    "Free Swap Space (%)": "$free_swap_percent"
  },
  "System Info": {
    "System Boot Time": "$boot_time",
    "System Boot Time (Unix Timestamp)": "$boot_timestamp",
    "System Description": "$system_description",
    "System Local Time": "$system_local_time",
    "System Name": "$system_name",
    "System Uptime": "$system_uptime"
  },
  "Miscellaneous Sensors": {
    "Context Switches per Second": "$context_switches_per_sec",
    "Node Exporter Version": "$node_exporter_version",
    "Maximum Number of Open File Descriptors": "$max_open_files",
    "Number of Open File Descriptors": "$open_file_descriptors"
  },
  "DiskSensors": {
    "IOSTAT-Read/s": "$disk_read_ops",
    "IOSTAT-Write/s": "$disk_write_ops",
    "IOSTAT-TPS": "$disk_tps",
    "DiskInfo": $disk_info
  },
  "NetworkSensors": $network_info,
  "SocketInfo": {
    "SOCKET-UDP-STAB": "$udp_stab",
    "SOCKET-UDP-CLOSE-WAIT": "$udp_close_wait",
    "SOCKET-TCP-STAB": "$tcp_stab",
    "SOCKET-TCP-CLOSE-WAIT": "$tcp_close_wait"
  }
}
EOF
)

# Salva o output JSON em um arquivo
echo "$json_output" > /tmp/system_info.json

echo "Dados capturados e salvos no arquivo system_info.json"

