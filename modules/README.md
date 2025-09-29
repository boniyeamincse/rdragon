# ReconDragon Modules

This directory contains production-ready reconnaissance modules for ReconDragon.

## Available Modules

### masscan
**Purpose**: Fast TCP/UDP port scanning using masscan.

**Enable/Disable**: Always available if masscan is installed.

**Config Options**:
- `ports`: Port range to scan (default: "1-65535")
- `rate`: Packets per second (default: 100000)

**Safe Defaults**: Conservative rate limiting, full port scan.

**Installation**: `sudo apt install masscan`

---

### nmap
**Purpose**: Comprehensive port scanning with service and OS detection.

**Enable/Disable**: Always available if nmap is installed.

**Config Options**:
- `vulners`: Enable vulnerability scanning (default: False)

**Safe Defaults**: No vulnerability scanning by default, standard timing.

**Installation**: `sudo apt install nmap`

---

### httpx_probe
**Purpose**: Async HTTP probing with optional screenshot capture.

**Enable/Disable**: Always available (uses httpx library).

**Config Options**:
- `screenshots`: Enable screenshot capture (default: False)

**Safe Defaults**: No screenshots by default, reasonable concurrency limits.

**Installation**: Included in requirements.txt (httpx, playwright)

---

### nuclei
**Purpose**: Vulnerability scanning using nuclei templates.

**Enable/Disable**: Always available if nuclei is installed.

**Config Options**:
- `severity`: Vulnerability severity filter (default: "info,low,medium,high,critical")
- `tags`: Template tags to include (default: "misc,generic")
- `templates`: Path to nuclei templates (default: "/opt/nuclei-templates")

**Safe Defaults**: All severities included, conservative rate limiting.

**Installation**: `sudo apt install nuclei`

---

### shodan_enrich
**Purpose**: Enrich IP/host data using Shodan API.

**Enable/Disable**: Requires SHODAN_API_KEY environment variable.

**Config Options**: None

**Safe Defaults**: Results cached for 24 hours, API rate limiting respected.

**Installation**:
1. Sign up for Shodan account
2. Get API key from https://account.shodan.io/
3. Set environment variable: `export SHODAN_API_KEY=your_key_here`

## General Configuration

All modules support:
- `execute=False`: Dry-run mode (default) - no external commands executed
- `execute=True`: Live execution mode

## Security Considerations

- All external binaries are executed with `subprocess.run(..., check=True, timeout=...)`
- No use of `shell=True` to prevent command injection
- API keys stored in environment variables only
- Results cached where appropriate to reduce API usage
- All network requests have reasonable timeouts

## Module Contract

All modules return a standardized JSON structure:
```json
{
  "module": "module_name",
  "version": "1.0.0",
  "target": "scan_target",
  "start_time": 1234567890.123,
  "end_time": 1234567890.456,
  "success": true,
  "summary": {...},
  "artifacts": ["path/to/file.json"],
  "raw": "raw_output_if_any"
}
```

## Testing

Run tests with: `pytest tests/test_*.py`

Tests mock external dependencies for safe CI/CD execution.