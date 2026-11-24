# 004 — The tunnel is NOT down

This is the finding that redirects the fix away from Proton and onto the firewall.

## WireGuard + gateway monitoring

```
opnsense_wireguard_interfaces_status
  {device: wg1, device_name: Home_Wireguard}            = 1
  {device: wg2, device_name: ProtonVPN-ExitSingapore}   = 1

opnsense_wireguard_peer_status
  {wg1, peer_name: Home_JK}                      = 0
  {wg1, peer_name: Home_Wireguard_Family_Shared} = 0
  {wg2, peer_name: ProtonVPN_Singapore}          = 1     <- up

time() - opnsense_wireguard_peer_last_handshake_seconds
  {wg2, ProtonVPN_Singapore} = 67.46 s                  <- handshake 67s ago, healthy
  {wg1, ...}                 = <epoch>                  <- counter zero, never handed shake
```

OPNsense's own gateway monitoring (`dpinger`) agrees the exit path is healthy:

```
opnsense_gateways_status          {address: 10.2.0.1, name: WAN_ProtonVPNSingapore} = 1
opnsense_gateways_loss_percentage {address: 10.2.0.1, name: WAN_ProtonVPNSingapore} = 0
opnsense_gateways_rtt_milliseconds{address: 10.2.0.1, name: WAN_ProtonVPNSingapore} = 14.1
opnsense_gateways_info  {WAN_PPPOE/pppoe0}=1  {Wireguaurd/wg1}=0  {WAN_ProtonVPNSingapore/wg2}=1
opnsense_services_status {Gateway monitor (WAN_ProtonVPNSingapore)/dpinger}=1
```

**0% loss, 14.1ms RTT.** The Proton tunnel is up and being actively probed.

## CARP/HA ruled out

A dead CARP virtual IP would explain an unresponsive `10.10.31.1`, but:

```
opnsense_carp_allowed        = 1
opnsense_carp_demotion       = 0
opnsense_carp_maintenance_mode = 0
```

## The VLAN interface map

`10.10.31.0/24` is `vlan0.31.1`, named **`VPN_SERVICES_LAN`**:

```
{device: vlan0.30.2,  interface: INFRA_LAN}
{device: vlan0.31.1,  interface: VPN_SERVICES_LAN}     <- the broken one
{device: wg2,         interface: WAN_ProtonVPNSingapore}
{device: igc3,        interface: WAN_GATEWAY_SOURCE}
{device: igc3_vlan500, interface: WAN_GATEWAY_VPN_SOURCE}
```

## Traffic on VLAN 31 collapsed exactly when the probes died

`rate(node_network_transmit_bytes_total{device="vlan0.31.1"}[10m])`, B/s:

```
  07:30=    6088  07:45=    5940  08:00=    5919  08:15=    6005  08:30=    4574
  10:15=      79  10:30=      22  10:45=      12  11:00=      12
```

And `wg2` fell to keepalive-only even though the tunnel stayed up:

```
  07:30=     854  07:45=     820  08:00=     821  08:15=     825  08:30=     611
  10:15=     511  10:30=     169  10:45=     137  11:00=     136
```

Note the metric-name trap: it is `node_network_receive_bytes_total`, **not** `..._received_...`
(the latter silently returns no data).

**Conclusion:** traffic dies *before* it reaches the tunnel. The exit is healthy and idle.
