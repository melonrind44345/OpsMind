# Ansible Integration Guide

**OpsMind v0.1.0**

## Overview

OpsMind uses Ansible as its primary discovery engine, leveraging the `ansible.builtin.setup` module and custom playbooks to collect comprehensive system facts from target hosts.

## Integration Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  OpsMind CLI    │────▶│  Ansible Engine  │────▶│  Target Hosts   │
│  (discover cmd) │     │  (ansible-runner)│     │  (via SSH/local)│
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Fact Adapter    │
                        │  (JSON → Model)  │
                        └─────────────────┘
```

## Requirements

### Control Node (where OpsMind runs)
```bash
# Ansible Core 2.15+
ansible-core>=2.15.0

# Recommended collections
ansible-galaxy collection install community.general
ansible-galaxy collection install community.docker

# Python package (optional, for Runner API)
pip install ansible-runner
```

### Target Nodes
- Python 2.7+ (for Ansible module execution)
- SSH server (for remote discovery)
- No agent installation required

## Discovery Playbooks

### 1. Main Discovery (`ansible/playbooks/discovery.yml`)

Comprehensive system fact collection:
- `ansible.builtin.setup`: Core system facts
- `ansible.builtin.package_facts`: Software inventory
- `ansible.builtin.service_facts`: Service status
- Custom port/service discovery

### 2. Software Inventory (`ansible/playbooks/software_inventory.yml`)

Detailed software stack detection:
- Container runtimes (Docker, Podman, containerd)
- Language runtimes (Python, Java, Node.js)
- Detailed package manifests

### 3. Security Scan (`ansible/playbooks/security_scan.yml`)

Security baseline assessment:
- Firewall configuration
- SELinux status
- SSH hardening
- Available security updates

## Configuration

### OpsMind Ansible Config (`ansible.cfg`)

```ini
[defaults]
host_key_checking = False    # No SSH host key prompts
timeout = 10                 # Connection timeout
forks = 10                   # Parallel hosts
gathering = smart            # Fact caching
pipelining = True            # SSH optimization

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
```

### Inventory Files

Standard Ansible inventory formats supported:

```yaml
# Static inventory (YAML)
all:
  hosts:
    web-01:
      ansible_host: 192.168.1.10
    db-01:
      ansible_host: 192.168.1.20

# Dynamic inventory (script-based)
# Any executable returning JSON inventory
```

Built-in inventories in `ansible/inventories/`:
- `local.yml`: Localhost discovery
- `production.yml`: Production server groups
- `staging.yml`: Staging environment

## Error Handling

| Scenario | Behavior | Error Message |
|----------|----------|---------------|
| Ansible not installed | Fallback to native/mock | "Ansible not available" |
| SSH unreachable | Retry (configurable) | "SSH connection failed" |
| Timeout | Retry with backoff | "Connection timed out" |
| Auth failure | Fail immediately | "Authentication failed" |
| Python missing on target | Fail with hints | "Python not found" |

## Performance Optimization

**For large-scale discovery (>10 hosts):**

1. **SSH Multiplexing**: Enabled by default in `ansible.cfg`
2. **Fact Caching**: `gathering = smart` avoids re-collection
3. **Parallel Execution**: `forks = 10` (configurable)
4. **Pipelining**: Reduces SSH round-trips
5. **ControlPersist**: Reuses SSH connections

## Troubleshooting

### Common Issues

**Issue**: `UNREACHABLE` error
**Solution**: Check SSH connectivity and credentials
```bash
ssh -i <key> user@host
```

**Issue**: Missing Python on target
**Solution**: Ensure Python 2.7+ is installed
```bash
ssh user@host 'which python || which python3 || which python2'
```

**Issue**: Slow discovery
**Solution**: Enable pipelining and increase forks
```bash
# In ansible.cfg
pipelining = True
forks = 20
```

### Debug Mode

```bash
# Enable Ansible verbose output
export ANSIBLE_VERBOSITY=3
opsmind discover localhost --method ansible

# Check Ansible connectivity
ansible all -i inventory.yml -m ping
```

## Extending with Custom Playbooks

OpsMind supports custom Ansible playbooks for specialized discovery needs:

```bash
# Run custom playbook
ansible-playbook -i inventory.yml custom_discovery.yml
```

The results can be loaded into OpsMind's adapter for standardized assessment.
