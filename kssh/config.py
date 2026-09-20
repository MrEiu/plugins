"""
Kapsel kssh Plugin - Configuration & Host History Manager.
Manages persistent storage of 3-4 recently connected SSH hosts in ~/.kapsel/kssh/hosts.yaml.
All comments and docstrings are in English.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from kapsel.storage.config import get_kapsel_dir


def get_kssh_dir() -> Path:
    """Returns directory path for kssh configuration (~/.kapsel/kssh)."""
    d = get_kapsel_dir() / "kssh"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_hosts_file() -> Path:
    """Returns path to hosts.yaml configuration file."""
    return get_kssh_dir() / "hosts.yaml"


def load_hosts() -> List[Dict[str, Any]]:
    """
    Loads list of saved hosts from disk.
    Sorted by last_connected timestamp descending (most recent first).
    Guaranteed to return at most 4 hosts.
    """
    f = get_hosts_file()
    if not f.is_file():
        return []
    try:
        with open(f, "r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp)
        if isinstance(data, list):
            items = [item for item in data if isinstance(item, dict) and item.get("host")]
            items.sort(key=lambda x: str(x.get("last_connected", "")), reverse=True)
            return items[:4]
        elif isinstance(data, dict) and "hosts" in data and isinstance(data["hosts"], list):
            items = [item for item in data["hosts"] if isinstance(item, dict) and item.get("host")]
            items.sort(key=lambda x: str(x.get("last_connected", "")), reverse=True)
            return items[:4]
    except Exception:
        pass
    return []


def save_hosts(hosts: List[Dict[str, Any]]) -> None:
    """Saves list of hosts (capped at 4) to hosts.yaml."""
    f = get_hosts_file()
    capped = hosts[:4]
    with open(f, "w", encoding="utf-8") as fp:
        yaml.dump(capped, fp, allow_unicode=True, default_flow_style=False, sort_keys=False)


def record_connection(
    host: str,
    user: Optional[str] = None,
    port: int = 22,
    name: Optional[str] = None,
    key_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Records or updates a successful SSH connection in the host history.
    Limits total hosts to at most 4 entries.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    clean_host = (host or "").strip()
    clean_user = (user or "").strip() or "root"
    clean_name = (name or "").strip() or clean_host

    existing_hosts = load_hosts()
    updated = False
    entry: Dict[str, Any] = {
        "name": clean_name,
        "host": clean_host,
        "user": clean_user,
        "port": int(port) if port else 22,
        "last_connected": now_str,
    }
    if key_path:
        entry["key_path"] = key_path

    new_list: List[Dict[str, Any]] = []
    for h in existing_hosts:
        # Match by name or host+port
        if (clean_name and h.get("name") == clean_name) or (h.get("host") == clean_host and h.get("port", 22) == entry["port"]):
            # Preserve custom name if user didn't specify one
            if not name and h.get("name"):
                entry["name"] = h["name"]
            new_list.append(entry)
            updated = True
        else:
            new_list.append(h)

    if not updated:
        new_list.insert(0, entry)

    new_list.sort(key=lambda x: str(x.get("last_connected", "")), reverse=True)
    final_list = new_list[:4]
    save_hosts(final_list)
    return entry


def remove_host(identifier: str) -> bool:
    """Removes a host by 1-based index, name, or host string."""
    hosts = load_hosts()
    target_idx = -1

    clean_id = (identifier or "").strip().lower()
    if clean_id.isdigit():
        idx = int(clean_id) - 1
        if 0 <= idx < len(hosts):
            target_idx = idx
    else:
        for i, h in enumerate(hosts):
            if str(h.get("name", "")).lower() == clean_id or str(h.get("host", "")).lower() == clean_id:
                target_idx = i
                break

    if target_idx >= 0:
        hosts.pop(target_idx)
        save_hosts(hosts)
        return True
    return False


def find_host(identifier: str) -> Optional[Dict[str, Any]]:
    """Finds a host by 1-based index, name, or host address."""
    hosts = load_hosts()
    clean_id = (identifier or "").strip().lower()
    if not clean_id:
        return hosts[0] if hosts else None

    if clean_id.isdigit():
        idx = int(clean_id) - 1
        if 0 <= idx < len(hosts):
            return hosts[idx]

    for h in hosts:
        if str(h.get("name", "")).lower() == clean_id:
            return h
        if str(h.get("host", "")).lower() == clean_id:
            return h

    return None
