import json
import subprocess


def test_no_known_cve_vulnerabilities():
    """Check all installed packages for known CVE vulnerabilities using pip-audit.

    - runs pip-audit against the local environment
    - parses JSON output for any reported vulnerabilities
    - prints a detailed report and actionable summary
    - fails if any CVEs are found
    """
    result = subprocess.run(
        ["pip-audit", "-f", "json", "-l", "--progress-spinner", "off"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    audit = json.loads(result.stdout)
    dependencies = audit.get("dependencies", [])

    # Collect vulnerabilities grouped by package
    affected_packages: dict[str, dict] = {}
    total_cves = 0
    for dep in dependencies:
        vulns = dep.get("vulns", [])
        if not vulns:
            continue
        name = dep["name"]
        version = dep["version"]
        if name not in affected_packages:
            affected_packages[name] = {"version": version, "vulns": [], "fix_versions": set()}
        for vuln in vulns:
            affected_packages[name]["vulns"].append(vuln)
            affected_packages[name]["fix_versions"].update(vuln.get("fix_versions", []))
            total_cves += 1

    if not affected_packages:
        return

    # Build the report
    lines = [f"Found {total_cves} known CVE(s) in {len(affected_packages)} package(s).", ""]

    # Detailed report per package
    lines.append("REPORT")
    lines.append("-" * 60)
    for name, info in sorted(affected_packages.items()):
        lines.append(f"  {name}=={info['version']}  ({len(info['vulns'])} CVE(s))")
        for vuln in info["vulns"]:
            fix = ", ".join(vuln.get("fix_versions", [])) or "no fix available"
            desc = vuln.get("description", "")
            summary = desc.split("\n")[0][:120] if desc else "no description"
            cve_url = f"https://nvd.nist.gov/vuln/detail/{vuln['id']}"
            lines.append(f"    - {vuln['id']}  fix: {fix}")
            lines.append(f"      {cve_url}")
            lines.append(f"      {summary}")
        lines.append("")

    # Actionable summary
    lines.append("ACTION REQUIRED")
    lines.append("-" * 60)
    for name, info in sorted(affected_packages.items()):
        fix_versions = sorted(info["fix_versions"])
        if fix_versions:
            lines.append(f"  pip install --upgrade {name}>={fix_versions[-1]}")
        else:
            lines.append(f"  {name}=={info['version']}: no fix available — consider replacing this dependency")

    report = "\n".join(lines)
    assert not affected_packages, report
