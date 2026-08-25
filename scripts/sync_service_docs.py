#!/usr/bin/env python3
"""Sync service documentation for chaijunkin-home-ops.

Non-destructive documentation pipeline:

1. README audit/fill  - creates missing `kubernetes/apps/<ns>/<app>/README.md`
   files and upgrades stale ones (placeholder descriptions or generic
   github.com/search links). Custom, curated READMEs are NEVER touched.
2. Services inventory - regenerates `docs/services-list.md` from the LIVE
   cluster (HTTPRoute + TLSRoute + LoadBalancer Services), deduplicated.
   Unlike scripts/httproute-csv.sh this includes TLSRoutes (nas/pve/ap).
3. Vault emission     - writes a generated inventory page into the Obsidian
   golden-source vault (TECH/Cloudjur/home-ops).

Usage:
    python3 scripts/sync_service_docs.py [--all] [--readmes] [--inventory]
                                          [--vault-dir DIR] [--check]

`task repository:sync-docs` runs the full sync. `--check` exits 1 on drift
(CI-friendly) without writing anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.parse
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "kubernetes" / "apps"
SERVICES_MD = REPO_ROOT / "docs" / "services-list.md"
DEFAULT_VAULT_DIR = Path(
    "/Users/jkchai/Documents/DefaultVault/pages/TECH/Cloudjur/home-ops"
)

# Namespaces whose PRR docs live under cloud-native (infra) vs application.
CLOUD_NATIVE_NS = {
    "actions-runner-system", "cert-manager", "external-secrets", "flux-system",
    "jobs", "kube-system", "network", "observability", "renovate", "security",
    "storage", "system-upgrade", "volsync-system",
}

# Curated upstream knowledge: app -> (repo_url, docs_url, description).
# Apps absent from this map fall back to a GitHub search link and are
# reported in the audit so they can be added here over time.
APP_KNOWLEDGE: dict[str, tuple[str, str, str]] = {
    # --- ai ---
    "memini": ("", "", "Memory service storing and retrieving AI agent context."),
    "ollama": ("https://github.com/ollama/ollama", "https://github.com/ollama/ollama#readme",
               "Local LLM runtime (Intel iGPU via ipex-llm Vulkan/XPU build)."),
    "open-webui": ("https://github.com/open-webui/open-webui", "https://docs.openwebui.com",
                   "Self-hosted web UI for LLM inference backends."),
    "openclaw": ("", "", "Personal AI assistant gateway with dispatch/chat/memory sidecars."),
    "toolhive": ("https://github.com/stacklok/toolhive", "https://docs.stacklok.com/toolhive",
                 "Operator deploying and securing MCP servers."),
    # --- database ---
    "dragonfly-operator": ("https://github.com/dragonflydb/dragonfly-operator", "",
                           "Operator running Dragonfly (Redis-compatible) in-memory stores."),
    "mosquitto": ("https://github.com/eclipse/mosquitto", "https://mosquitto.org",
                  "Eclipse Mosquitto MQTT broker for home automation messaging."),
    # --- default ---
    "atuin": ("https://github.com/atuinsh/atuin", "https://docs.atuin.sh",
              "Synced, searchable shell history server."),
    "changedetection": ("https://github.com/dgtlmoon/changedetection.io", "",
                        "Website change detection and notifications (with browserless Chrome)."),
    "convertx": ("https://github.com/c4illin/ConvertX", "",
                 "Self-hosted web file converter (1000+ formats)."),
    "cyberchef": ("https://github.com/gchq/CyberChef", "",
                  "Cyber Swiss Army Knife for encoding, decoding and analysis."),
    "freshrss": ("https://github.com/FreshRSS/FreshRSS", "https://freshrss.org",
                 "Self-hosted RSS feed aggregator."),
    "glance": ("https://github.com/glanceapp/glance", "",
               "Self-hosted dashboard aggregating feeds and service widgets."),
    "homepage": ("https://github.com/gethomepage/homepage", "https://gethomepage.dev",
                 "Cluster landing dashboard with annotation-based service discovery."),
    "it-tools": ("https://github.com/CorentinTh/it-tools", "",
                 "Collection of handy developer web tools."),
    "karakeep": ("https://github.com/karakeep-app/karakeep", "",
                 "Bookmark-everything app (links, notes, images) with search."),
    "n8n": ("https://github.com/n8n-io/n8n", "https://docs.n8n.io",
            "Workflow automation platform (webhooks, integrations, cron)."),
    "pdf-tool": ("https://github.com/Stirling-Tools/Stirling-PDF", "",
                 "Self-hosted PDF toolbox (merge, split, OCR, convert)."),
    "rustdesk": ("https://github.com/rustdesk/rustdesk-server", "",
                 "Self-hosted remote desktop relay/signaling server."),
    "searxng": ("https://github.com/searxng/searxng", "https://docs.searxng.org",
                "Privacy-respecting metasearch engine."),
    "sure": ("https://github.com/we-promise/sure", "",
             "Self-hosted personal finance manager."),
    "thelounge": ("https://github.com/thelounge/thelounge", "",
                  "Modern self-hosted web IRC client (always connected)."),
    "tika": ("https://github.com/apache/tika", "",
             "Apache Tika text extraction server (Paperless companion)."),
    "trek": ("", "", "Trip itinerary planning application."),
    # --- dev ---
    "forgejo": ("https://codeberg.org/forgejo/forgejo", "https://forgejo.org/docs",
                "Git software forge with Actions runners for CI."),
    # --- downloads ---
    "autobangumi": ("https://github.com/EstrellaXD/Auto_Bangumi", "",
                    "Automated anime RSS downloading pipeline."),
    "autobrr": ("https://github.com/autobrr/autobrr", "https://autobrr.com",
                "IRC-announce download automation for trackers."),
    "bazarr": ("https://github.com/morpheus65535/bazarr", "",
               "Companion managing subtitles for Sonarr/Radarr."),
    "flaresolverr": ("https://github.com/FlareSolverr/FlareSolverr", "",
                     "Proxy solving Cloudflare challenges for *arr indexers."),
    "lidarr": ("https://github.com/Lidarr/Lidarr", "",
               "Music collection manager for Usenet/Bittorrent."),
    "metube": ("https://github.com/alexta69/metube", "",
               "Web GUI for yt-dlp video downloads."),
    "profilarr": ("https://github.com/Dictionarry-Hub/profilarr", "",
                  "Quality-profile and custom-format management for *arr apps."),
    "prowlarr": ("https://github.com/Prowlarr/Prowlarr", "",
                 "Indexer manager/proxy feeding the *arr stack."),
    "qui": ("https://github.com/autobrr/qui", "",
            "Modern multi-instance qBittorrent web interface."),
    "recyclarr": ("https://github.com/recyclarr/recyclarr", "",
                  "Syncs TRaSH Guides settings into Sonarr/Radarr."),
    "sabnzbd": ("https://github.com/sabnzbd/sabnzbd", "",
                "Usenet binary downloader (NZB)."),
    "shelfmark": ("https://github.com/calibrain/shelfmark", "",
                  "Automated ebook sourcing feeding Calibre-Web."),
    "webhook": ("https://github.com/home-operations/webhook", "",
                "Webhook receiver for automation triggers."),
    "ytdl-sub": ("https://github.com/jmbannon/ytdl-sub", "",
                 "Automates YouTube downloads into media-library layout."),
    # --- external-secrets ---
    "bitwarden-sdk-server": ("https://github.com/external-secrets/bitwarden-sdk-server", "",
                             "Bitwarden Secrets Manager backend for External Secrets."),
    # --- flux-system ---
    "flux-instance": ("https://github.com/controlplaneio-fluxcd/flux-operator", "",
                      "Declarative Flux CD installation managed by flux-operator."),
    "flux-operator": ("https://github.com/controlplaneio-fluxcd/flux-operator", "",
                      "Operator managing the lifecycle of Flux distributions."),
    "headlamp": ("https://github.com/headlamp-k8s/headlamp", "",
                 "User-friendly Kubernetes web UI."),
    "konflate": ("", "", "Configuration assembly from multiple sources."),
    "kubernetes-schemas": ("", "",
                           "Publishes CRD JSON schemas for validation/editing."),
    "tofu-controller": ("https://github.com/flux-iac/tofu-controller", "",
                        "Weaves GitOps Toolkit controller running OpenTofu in-cluster."),
    # --- jobs ---
    "remediation": ("", "", "Scheduled remediation jobs using a custom utility image."),
    # --- kube-system ---
    "coredns": ("https://github.com/coredns/coredns", "https://coredns.io",
                "Cluster DNS server (.svc resolution)."),
    "csi-driver-nfs": ("https://github.com/kubernetes-csi/csi-driver-nfs", "",
                       "CSI driver provisioning NFS-backed volumes."),
    "descheduler": ("https://github.com/kubernetes-sigs/descheduler", "",
                    "Evicts pods to rebalance scheduling across nodes."),
    "intel-device-plugin": ("https://github.com/intel/intel-device-plugins-for-kubernetes", "",
                            "Exposes Intel GPU devices to workloads (QuickSync)."),
    "metrics-server": ("https://github.com/kubernetes-sigs/metrics-server", "",
                       "Cluster-wide resource metrics source (kubectl top)."),
    "node-feature-discovery": ("https://github.com/kubernetes-sigs/node-feature-discovery", "",
                               "Detects hardware features and labels nodes."),
    "reloader": ("https://github.com/stakater/Reloader", "",
                 "Rolls pods when ConfigMaps/Secrets change."),
    "snapshot-controller": ("https://github.com/kubernetes-csi/external-snapshotter", "",
                            "Volume snapshot CRDs and controller."),
    "spegel": ("https://github.com/spegel-org/spegel", "",
               "Stateless peer-to-peer container registry mirror."),
    # --- media ---
    "calibre-web-automated": ("https://github.com/crocodilestick/Calibre-Web-Automated", "",
                              "Calibre-Web fork with automated ingest and conversion."),
    "filebrowser": ("https://github.com/filebrowser/filebrowser", "",
                    "Web-based file manager over storage paths."),
    "jellyfin": ("https://github.com/jellyfin/jellyfin", "https://jellyfin.org/docs",
                 "The Free Software Media System."),
    "kavita": ("https://github.com/Kareadita/Kavita", "",
               "Self-hosted library server for comics, books and manga."),
    "komga": ("https://github.com/gotson/komga", "",
              "Media server for comics, manga and magazines."),
    "maintainerr": ("https://github.com/jorenn92/Maintainerr", "",
                    "Automated media cleanup rules for Plex/*arr."),
    "neko": ("https://github.com/m1k1o/neko", "",
             "Shared virtual browser (watch together) with Firefox."),
    "romm": ("https://github.com/rommapp/romm", "",
             "Emulation ROM library manager with metadata."),
    "seerr": ("https://github.com/seerr-team/seerr", "",
              "Media request and discovery manager."),
    "slskd": ("https://github.com/slskd/slskd", "",
              "Soulseek client with modern web UI."),
    "tautulli": ("https://github.com/Tautulli/Tautulli", "",
                 "Plex usage monitoring and statistics."),
    "watchstate": ("https://github.com/arabcoders/watchstate", "",
                   "Syncs watch state between Plex/Jellyfin backends."),
    # --- network ---
    "certificates": ("https://github.com/cert-manager/cert-manager", "",
                     "TLS certificate issuance/import-export via cert-manager."),
    "echo-server": ("https://github.com/mendhak/http-https-echo", "",
                    "Echo endpoints returning request details (connectivity tests)."),
    "envoy-gateway": ("https://github.com/envoyproxy/gateway", "https://gateway.envoyproxy.io",
                      "Envoy implementation of Kubernetes Gateway API (internal/external)."),
    "external-services": ("", "",
                          "Proxy layer exposing physical appliances through Envoy Gateway."),
    "multus": ("https://github.com/k8snetworkplumbingwg/multus-cni", "",
               "Multi-network CNI attaching pods to VLAN interfaces."),
    # --- observability ---
    "exporters": ("", "", "Umbrella for metric exporters (blackbox, nut, speedtest, opnsense)."),
    "external-access": ("", "", "External access path for observability tooling (disabled WIP)."),
    "gatus": ("https://github.com/TwiN/gatus", "",
              "Health monitoring and status page driven by annotations."),
    "k8s-monitoring": ("https://github.com/grafana/k8s-monitoring-helm", "",
                       "Alloy-based telemetry pipeline shipping metrics/logs/traces."),
    "kromgo": ("https://github.com/kashalls/kromgo", "",
               "Prometheus query-to-badge image service for dashboards."),
    "loki": ("https://github.com/grafana/loki", "",
             "Horizontally scalable log aggregation system."),
    "pyroscope": ("https://github.com/grafana/pyroscope", "",
                  "Continuous profiling backend (currently disabled)."),
    "silence-operator": ("https://github.com/giantswarm/silence-operator", "",
                         "Manages Alertmanager silences declaratively."),
    "tempo": ("https://github.com/grafana/tempo", "",
              "Distributed tracing backend."),
    "webhook": ("", "", "Alertmanager webhook receiver driving remediation jobs."),
    # --- renovate ---
    "renovate-operator": ("https://github.com/mirceanton/renovate-operator", "",
                          "Kubernetes operator scheduling Renovate dependency updates."),
    # --- security ---
    "kyverno-policies": ("https://kyverno.io/policies", "",
                         "Kyverno best-practice cluster policy bundle."),
    "policy-reporter": ("https://github.com/kyverno/policy-reporter", "",
                        "Reports PolicyReport violations and sends alerts."),
    "tetragon": ("https://github.com/cilium/tetragon", "",
                 "eBPF-based security observability and runtime enforcement."),
    "trivy-operator-polr-adapter": ("https://github.com/fjogeleit/trivy-operator-polr-adapter", "",
                                    "Converts Trivy scan reports into PolicyReport resources."),
    # --- storage ---
    "democratic-csi": ("https://github.com/democratic-csi/democratic-csi", "",
                       "CSI driver bridging NAS storage (zfs-generic-nfs)."),
    "garage": ("https://github.com/deuxfleurs-org/garage", "https://garagehq.deuxfleurs.fr",
               "S3-compatible object storage for self-hosting."),
    "kopia": ("https://github.com/kopia/kopia", "",
              "Fast incremental encrypted backup engine."),
    "kopiur": ("", "", "VolSync backup orchestrator injected via reusable components."),
    "openebs": ("https://github.com/openebs/openebs", "",
                "Local PV storage provisioner for the cluster."),
    "rclone": ("https://github.com/rclone/rclone", "",
               "Cloud-storage sync/copy jobs."),
    # --- system-upgrade ---
    "tuppr": ("https://github.com/home-operations/tuppr", "",
              "Automated Talos and Kubernetes upgrade provider for Flux."),
    # --- volsync-system ---
    "volsync": ("https://github.com/backube/volsync", "",
                "Asynchronous volume replication and backups."),
    # --- workadventure ---
    "coturn": ("https://github.com/coturn/coturn", "",
               "TURN/STUN relay for WebRTC connectivity."),
    "synapse": ("https://github.com/element-hq/synapse", "",
                "Matrix homeserver implementation."),
    "workadventure": ("https://github.com/workadventure/workadventure", "",
                      "Virtual office/social space rendered as a game."),
}


def titleize(name: str) -> str:
    return name.title()


def prr_url(ns: str, app: str) -> str:
    folder = "cloud-native" if ns in CLOUD_NATIVE_NS else "application"
    return f"https://wiki.cloudjur.com/pages/tech/cloudjur/{folder}/{app.lower()}"


def render_readme(ns: str, app: str) -> str:
    repo_url, docs_url, desc = APP_KNOWLEDGE.get(
        app,
        (f"https://github.com/search?q={urllib.parse.quote(app)}", "", ""),
    )
    repo_label = f"{titleize(app)} Source Code"
    docs_line = (
        f"- [Documentation]({docs_url})" if docs_url else "- [Documentation]() <!-- Add link to upstream docs -->"
    )
    return f"""# {titleize(app)}

**Description:** {desc}
**Category:** {ns}

---

## Resources
- **Project Repository:** [{repo_label}]({repo_url})
- **Helm/Manifest Source:** `Unknown`

---

## Related Links
{docs_line}
- [Application PRR Document]({prr_url(ns, app)})

## Notes
- *Add operational notes, gotchas, or specific configurations here.*
"""


def is_stale(text: str) -> bool:
    return "To be filled" in text or "github.com/search?q=" in text


def sync_readmes(check: bool) -> int:
    """Returns count of READMEs that would be created/upgraded."""
    changed = 0
    unknown_stale: list[str] = []
    for ns_dir in sorted(APPS_DIR.iterdir()):
        if not ns_dir.is_dir():
            continue
        for app_dir in sorted(ns_dir.iterdir()):
            if not app_dir.is_dir() or app_dir.name in {"app", "config"}:
                continue
            readme = app_dir / "README.md"
            app = app_dir.name
            ns = ns_dir.name
            known = app in APP_KNOWLEDGE
            if not readme.exists():
                changed += 1
                if not check:
                    readme.write_text(render_readme(ns, app), encoding="utf-8")
                print(f"[create] {readme.relative_to(REPO_ROOT)}")
            elif is_stale(readme.read_text(encoding="utf-8")):
                if known:
                    changed += 1
                    if not check:
                        readme.write_text(render_readme(ns, app), encoding="utf-8")
                    print(f"[update] {readme.relative_to(REPO_ROOT)}")
                else:
                    unknown_stale.append(str(readme.relative_to(REPO_ROOT)))
    if unknown_stale:
        print(f"\nStale but no upstream knowledge (add to APP_KNOWLEDGE):")
        for p in unknown_stale:
            print(f"  - {p}")
    return changed


# ---------------------------------------------------------------------------
# Live services inventory
# ---------------------------------------------------------------------------


def kubectl_json(args: list[str]) -> dict:
    try:
        out = subprocess.run(
            ["kubectl"] + args, capture_output=True, text=True, timeout=30, check=True
        )
        return json.loads(out.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return {"items": []}


def collect_services() -> list[dict]:
    rows: dict[tuple[str, str, str], dict] = {}

    def homepage_meta(meta: dict) -> tuple[bool, str]:
        ann = meta.get("annotations") or {}
        enabled = ann.get("gethomepage.dev/enabled") == "true"
        group = ann.get("gethomepage.dev/group", "None")
        return enabled, group

    for kind in ("httproute", "tlsroute"):
        items = kubectl_json(["get", kind, "-A", "-o", "json"]).get("items", [])
        for r in items:
            meta = r.get("metadata", {})
            spec = r.get("spec", {})
            enabled, group = homepage_meta(meta)
            parent = ((spec.get("parentRefs") or [{}])[0]).get("name", "")
            for host in spec.get("hostnames", []) or [""]:
                key = (meta.get("namespace", "default"), meta.get("name", ""), host)
                rows[key] = {
                    "namespace": key[0], "app": key[1], "url": host,
                    "group": group, "kind": kind.upper(),
                    "gateway": "external" if "external" in parent else "internal",
                    "enabled": enabled,
                }

    # LoadBalancer services without an HTTP/TLS route hostname
    routes_backends = set()
    for kind in ("httproute", "tlsroute"):
        for r in kubectl_json(["get", kind, "-A", "-o", "json"]).get("items", []):
            ns = r.get("metadata", {}).get("namespace", "default")
            for rule in r.get("spec", {}).get("rules", []) or []:
                for ref in rule.get("backendRefs", []) or []:
                    routes_backends.add((ns, ref.get("name", "")))

    for svc in kubectl_json(["get", "svc", "-A", "-o", "json"]).get("items", []):
        meta, spec = svc.get("metadata", {}), svc.get("spec", {})
        if spec.get("type") != "LoadBalancer":
            continue
        key = (meta.get("namespace", "default"), meta.get("name", ""))
        if key in routes_backends:
            continue
        ann = meta.get("annotations") or {}
        host = ann.get("external-dns.alpha.kubernetes.io/hostname", "")
        if not host:
            lb = ((spec.get("ports") or [{}])[0])
            ingress = svc.get("status", {}).get("loadBalancer", {}).get("ingress") or []
            ip = (ingress[0].get("ip") if ingress else None) or ""
            host = f"{ip}:{lb.get('port', '')}" if ip else "<unknown>"
        enabled, group = homepage_meta(meta)
        rows[(key[0], key[1], host)] = {
            "namespace": key[0], "app": key[1], "url": host, "group": group,
            "kind": "LoadBalancer", "gateway": "-", "enabled": enabled,
        }

    return sorted(rows.values(), key=lambda r: (r["namespace"], r["app"], r["url"]))


def render_services_md(rows: list[dict]) -> str:
    lines = [
        "# Services List",
        "",
        "<!-- Generated by scripts/sync_service_docs.py - DO NOT EDIT MANUALLY -->",
        f"<!-- Last generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} -->",
        "",
        "| Namespace | App | URL | Route | Gateway | Homepage Group |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['namespace']} | {r['app']} | {r['url']} | {r['kind']} "
            f"| {r['gateway']} | {r['group']} |"
        )
    # TLSRoutes cannot be discovered by homepage (RBAC watches httproutes/gateways
    # only) - they are expected to be managed via the homepage ConfigMap instead.
    missing = [
        r for r in rows
        if not r["enabled"] and r["kind"] != "TLSROUTE"
    ]
    manual_tls = [r for r in rows if r["kind"] == "TLSROUTE" and not r["enabled"]]
    if missing:
        lines += [
            "",
            "## Missing Homepage Integration",
            "",
            "Services without `gethomepage.dev/enabled: \"true\"`:",
            "",
        ]
        lines += [f"- `{r['namespace']}/{r['app']}` ({r['url']})" for r in missing]
    if manual_tls:
        lines += [
            "",
            "> TLS passthrough routes (below) cannot be auto-discovered by Homepage;",
            "> manage their dashboard entries in `kubernetes/apps/default/homepage/app/configmap.yaml`.",
            "",
        ]
        lines += [
            f"- `{r['namespace']}/{r['app']}` ({r['url']})" for r in manual_tls
        ]
    lines.append("")
    return "\n".join(lines)


def render_vault_md(rows: list[dict]) -> str:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r["enabled"] or r["group"] != "None":
            groups[r["group"]].append(r)
    body = [
        "---",
        "publish: true",
        "tags:",
        "  - network",
        "  - inventory",
        "---",
        "",
        "# Services Inventory",
        "",
        f"_Generated from the live cluster by `scripts/sync_service_docs.py` at "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Canonical source: "
        "[services-list.md](https://github.com/chaijunkin/home-ops/blob/main/docs/services-list.md)_",
        "",
    ]
    for group in sorted(groups):
        body.append(f"## {group}")
        body.append("")
        body.append("| App | URL | Namespace | Access |")
        body.append("| --- | --- | --- | --- |")
        for r in sorted(groups[group], key=lambda x: x["app"].lower()):
            access = "Public" if r["gateway"] == "external" else (
                "Lan" if r["gateway"] == "internal" else "-"
            )
            body.append(
                f"| {titleize(r['app'])} | https://{r['url']} | `{r['namespace']}` | {access} |"
            )
        body.append("")
    return "\n".join(body)


def _semantic(text: str) -> str:
    """Strip generation timestamps so --check compares real content."""
    return "\n".join(
        line for line in text.splitlines() if "Last generated" not in line
        and "Generated from the live cluster" not in line
    )


def sync_inventory(vault_dir: Path, check: bool) -> bool:
    rows = collect_services()
    new_md = render_services_md(rows)
    vault_page = vault_dir / "Services-Inventory.md"
    new_vault = render_vault_md(rows)
    drifted_md = not SERVICES_MD.exists() or _semantic(
        SERVICES_MD.read_text(encoding="utf-8")
    ) != _semantic(new_md)
    drifted_vault = not vault_page.exists() or _semantic(
        vault_page.read_text(encoding="utf-8")
    ) != _semantic(new_vault)
    drifted = drifted_md or drifted_vault
    if drifted_md:
        print(f"[drift ] {SERVICES_MD.relative_to(REPO_ROOT)} ({len(rows)} services)")
        if not check:
            SERVICES_MD.write_text(new_md, encoding="utf-8")
    if drifted_vault:
        print(f"[vault ] {vault_page}")
        if not check:
            vault_page.parent.mkdir(parents=True, exist_ok=True)
            vault_page.write_text(new_vault, encoding="utf-8")
    if not drifted:
        print("[ok    ] services inventory up-to-date")
    return drifted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readmes", action="store_true", help="sync app READMEs only")
    parser.add_argument("--inventory", action="store_true", help="regenerate services list only")
    parser.add_argument("--all", action="store_true", help="run everything (default)")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("--vault-dir", type=Path, default=DEFAULT_VAULT_DIR)
    args = parser.parse_args()

    do_all = not (args.readmes or args.inventory)
    rc = 0
    if do_all or args.inventory:
        if sync_inventory(args.vault_dir, check=args.check):
            rc = 1 if args.check else rc
    if do_all or args.readmes:
        n = sync_readmes(check=args.check)
        verb = "would change" if args.check else "changed"
        print(f"\nREADMEs {verb}: {n}")
        if args.check and n:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
