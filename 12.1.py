import datetime
import getpass
import json
import os
import platform
import socket
import sys

try:
    import psutil
except ImportError:
    sys.exit('Не установлен модуль psutil. Установите: pip install psutil')

OUTPUT_FILE = 'system_info.json'

VPN_PREFIXES = ('tun', 'tap', 'wg', 'ppp', 'utun', 'ipsec', 'vpn')

SUPPORTED = {'Windows': 'Windows', 'Linux': 'Linux', 'Darwin': 'macOS'}


def to_gb(value):
    return round(value / 1024 ** 3, 2)


def safe(func, default=None):
    try:
        return func()
    except Exception:
        return default


def get_os_info():
    system = platform.system()
    return {
        'system': system,
        'name': SUPPORTED.get(system, system),
        'release': platform.release(),
        'version': platform.version(),
        'platform': platform.platform(),
        'architecture': platform.machine(),
    }


def get_host_info():
    return {
        'hostname': socket.gethostname(),
        'username': safe(getpass.getuser),
        'home_dir': os.path.expanduser('~'),
        'python_version': platform.python_version(),
    }


def get_cpu_info():
    freq = safe(psutil.cpu_freq)
    return {
        'model': platform.processor() or 'unknown',
        'physical_cores': psutil.cpu_count(logical=False),
        'logical_cores': psutil.cpu_count(logical=True),
        'max_freq_mhz': round(freq.max, 1) if freq and freq.max else None,
        'usage_percent': psutil.cpu_percent(interval=0.5),
    }


def get_memory_info():
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        'total_gb': to_gb(mem.total),
        'available_gb': to_gb(mem.available),
        'used_percent': mem.percent,
        'swap_total_gb': to_gb(swap.total),
    }


def get_disks_info():
    disks = []
    for part in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        disks.append({
            'device': part.device,
            'mountpoint': part.mountpoint,
            'fstype': part.fstype,
            'total_gb': to_gb(usage.total),
            'free_gb': to_gb(usage.free),
            'used_percent': usage.percent,
        })
    return disks


def get_network_info():
    stats = psutil.net_if_stats()
    interfaces = []

    for name, addrs in psutil.net_if_addrs().items():
        ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
        ipv6 = [a.address.split('%')[0] for a in addrs
                if a.family == socket.AF_INET6]
        mac = [a.address for a in addrs
               if a.family == psutil.AF_LINK and a.address]

        if not ipv4 and not ipv6:
            continue

        st = stats.get(name)
        interfaces.append({
            'name': name,
            'is_up': st.isup if st else None,
            'mac': mac[0] if mac else None,
            'ipv4': ipv4,
            'ipv6': ipv6,
            'is_vpn': name.lower().startswith(VPN_PREFIXES),
        })


    main_ip = 'unknown'
    for iface in interfaces:
        if iface['is_up'] and not iface['is_vpn']:
            for ip in iface['ipv4']:
                if not ip.startswith('127.'):
                    main_ip = ip
                    break
        if main_ip != 'unknown':
            break

    vpn_ifaces = [i for i in interfaces if i['is_vpn'] and i['is_up']]

    return {
        'main_ip': main_ip,
        'vpn_active': bool(vpn_ifaces),
        'vpn_interfaces': [i['name'] for i in vpn_ifaces],
        'interfaces': interfaces,
    }


def get_boot_info():
    boot = datetime.datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.datetime.now() - boot
    return {
        'boot_time': boot.isoformat(timespec='seconds'),
        'uptime_hours': round(uptime.total_seconds() / 3600, 2),
    }


def main():
    system = platform.system()
    print('Операционная система:', SUPPORTED.get(system, system))

    data = {
        'os': get_os_info(),
        'host': get_host_info(),
        'cpu': safe(get_cpu_info, {}),
        'memory': safe(get_memory_info, {}),
        'disks': safe(get_disks_info, []),
        'network': safe(get_network_info, {}),
        'boot': safe(get_boot_info, {}),
        'collected_at': datetime.datetime.now().isoformat(timespec='seconds'),
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(json.dumps(data, indent=4, ensure_ascii=False))
    print(f'\nИнформация сохранена в {OUTPUT_FILE}')


if __name__ == '__main__':
    main()