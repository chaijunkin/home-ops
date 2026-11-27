#!/usr/bin/env python3
"""Shared formatter for the step-013 probes: prints Prometheus instant/range JSON readably.

Usage:  ... | python3 lib-fmt.py instant|range
Adaptive precision matters here: gateway RTT is compared at both 900 (Mbps) and 0.006 (s).
"""
import json, sys, time

KEYS = ('device', 'instance', 'job', 'target', 'ip', 'name')

def lbl(m):
    keep = {k: v for k, v in m.items() if k in KEYS and k != '__name__'}
    s = ','.join(f'{k}={v}' for k, v in sorted(keep.items()))
    return (s or m.get('__name__', '?'))[:66]

def num(v):
    v = float(v)
    a = abs(v)
    if a == 0:    return '0'
    if a >= 100:  return f'{v:.0f}'
    if a >= 1:    return f'{v:.1f}'
    if a >= 0.01: return f'{v:.3f}'
    return f'{v:.4f}'

def main(mode):
    d = json.load(sys.stdin)
    if d.get('status') != 'success':
        print('     ERROR:', str(d.get('error'))[:120])
        return
    rs = d['data']['result']
    if not rs:
        print('     (no series)')
        return
    for r in rs[:12]:
        if mode == 'instant':
            print('     %-66s %s' % (lbl(r['metric']), num(r['value'][1])))
        else:
            vals = [(int(float(t)), float(v)) for t, v in r['values']]
            print('   %s  [n=%d]' % (lbl(r['metric']), len(vals)))
            print('     ', ' '.join(f'{time.strftime("%d/%H", time.gmtime(t))}:{num(v)}' for t, v in vals))

main(sys.argv[1] if len(sys.argv) > 1 else 'instant')
