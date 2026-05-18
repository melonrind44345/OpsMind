# Discovery Methods Guide

**OpsMind v0.1.0**

OpsMind supports three discovery methods with automatic fallback for maximum reliability.

## Method Comparison

| Feature | Ansible | Native | Mock |
|---------|---------|--------|------|
| **Requires** | `ansible` CLI | `psutil` Python lib | Nothing |
| **Remote hosts** | ✅ SSH | ❌ Local only | ✅ Simulated |
| **Localhost** | ✅ | ✅ | ✅ |
| **Data depth** | High (200+ facts) | Medium (50+ facts) | Customizable |
| **Speed** | Medium (~5s) | Fast (~1s) | Instant |
| **Confidence** | HIGH | HIGH | LOW (marked) |
| **Demo friendly** | ❌ Needs Ansible | ❌ Needs host | ✅ Always works |

## Method Selection

### 1. Ansible Discovery (`--method ansible`)

Primary discovery method. Uses `ansible.builtin.setup` module to collect comprehensive system facts.

**Requirements:**
- Ansible Core 2.15+ installed on the control node
- SSH access to remote targets (or local connection for localhost)
- Python 2.7+ on remote hosts (for Ansible module execution)

**Collected Data:**
- Hardware: CPU model, cores, threads, frequency, cache
- Memory: Total, free, swap (MB precision)
- Storage: All mount points, sizes, filesystem types, options
- Network: All interfaces, IPs, MACs, speed, status
- OS: Distribution, version, kernel, architecture
- Packages: Full inventory via package manager
- Services: All systemd/sysv services with status
- Security: SELinux, firewall status
- Virtualization: Type, vendor

**Example:**
```bash
# Local discovery
opsmind discover localhost --method ansible

# Remote discovery
opsmind discover 192.168.1.100 --method ansible --ssh-user ubuntu --ssh-key ~/.ssh/id_rsa

# Inventory group discovery
opsmind discover web-servers --method ansible --inventory ./inventory.yml

# Bulk discovery (comma-separated)
opsmind discover "192.168.1.100,192.168.1.101" --method ansible
```

### 2. Native Discovery (`--method native`)

Fallback method using Python's `psutil` library and system commands.

**Requirements:**
- Python 3.11+
- `psutil` package
- Local execution only (no SSH)

**Limitations:**
- No remote host support
- Limited package info (first 200 packages)
- No Ansible-specific facts (SELinux, virtualization)
- May miss some system details

**Example:**
```bash
opsmind discover localhost --method native
```

### 3. Mock Discovery (`--method mock`)

Demo and testing method with realistic simulated data.

**Built-in Profiles:**

| Profile | OS | CPU | Memory | Description |
|---------|-----|-----|--------|-------------|
| `legacy-centos` | CentOS 6.10 | 4C/8T | 16GB | EOL, 47 pending updates |
| `modern-ubuntu` | Ubuntu 22.04 | 8C/16T | 64GB | Modern, up-to-date |
| `windows-server` | Windows Server 2019 | 8C/16T | 32GB | Windows container candidate |

**Example:**
```bash
# Use profile name as target
opsmind discover legacy-centos --method mock
opsmind discover modern-ubuntu --method mock
opsmind discover windows-server --method mock

# Multiple profiles
opsmind discover "legacy-centos,modern-ubuntu" --method mock
```

### 4. Auto Selection (`--method auto` - Default)

Intelligently selects the best available method:

1. If target is `localhost`: Try Ansible → Fallback to Native
2. If target is remote IP/hostname: Try Ansible → Fallback to Mock (with warning)

## Data Confidence Levels

| Level | Meaning | Typical Use |
|-------|---------|-------------|
| **HIGH** | Direct measurement from real system | Ansible/Native discovery |
| **MEDIUM** | Validated measurement | Secondary sources |
| **LOW** | Inferred or simulated | Mock engine data |
| **ESTIMATED** | Best-guess heuristic | Missing data points |

## Performance Tips

- **Single host**: Use `--method ansible` for richest data
- **Multiple hosts**: Use Ansible inventory groups for parallel discovery
- **Quick demo**: Use `--method mock` for instant results
- **Limited resources**: Use `--method native` for lightweight collection
