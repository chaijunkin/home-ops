UPS sizing guide — step-by-step

Goal: size a UPS (VA/Wh/battery capacity) for the homelab to provide clean power and a target runtime during an outage.

Inputs you'll need:
- Total IT load (W) — sum of typical or peak wattage for devices you want to protect.
- Power factor (PF) — many consumer UPS use PF ≈ 0.6–0.9; assume 0.8 if unknown.
- UPS efficiency (η) — battery + inverter losses; assume ~0.9 (90%).
- Desired runtime (minutes or hours) at the chosen load.
- Battery bank nominal voltage (Vbat) — e.g., 12V, 24V, or 48V depending on UPS.

Summary of repo assumptions used in examples below:
- Typical IT load (P_it): 235 W
- UPS efficiency (η): 0.9
- Power factor (PF): 0.8

Steps (brief)
1) Decide what to protect (server + core switch only, or everything including PoE cameras). Smaller protected set → longer runtime for same battery.
2) Compute mains draw: P_mains = P_it / η
3) Convert to VA: VA_required = P_mains / PF
4) Add 20–30% headroom for growth and spikes
5) Compute battery energy required for desired runtime: Wh_needed = P_it × hours / η
6) If needed, convert Wh → Ah for your battery voltage: Ah = Wh_needed / Vbat and account for DoD

Exact runtime targets (computed)
Using P_it = 235 W and η = 0.9 (change these values if you have measurements):

- 30 minutes (0.5 h)
   - Wh_needed = 235 × 0.5 / 0.9 ≈ 131 Wh
   - Ah @ 48 V ≈ 131 / 48 ≈ 2.7 Ah (usable)

- 60 minutes (1.0 h)
   - Wh_needed ≈ 235 × 1 / 0.9 ≈ 261 Wh
   - Ah @ 48 V ≈ 261 / 48 ≈ 5.4 Ah (usable)

- 120 minutes (2.0 h)
   - Wh_needed ≈ 522 Wh → Ah @ 48 V ≈ 10.9 Ah

- 180 minutes (3.0 h)
   - Wh_needed ≈ 783 Wh → Ah @ 48 V ≈ 16.3 Ah

VA / UPS sizing guidance
- P_mains = P_it / η ≈ 235 / 0.9 ≈ 261 W
- VA_required = P_mains / PF ≈ 261 / 0.8 ≈ 326 VA
- Add ~25% headroom → recommended VA ≈ 408 VA → pick common commercial sizes: 600 VA, 1000 VA, 1500 VA depending on runtime/headroom needs

Practical mapping (typical consumer UPS usable watts vary by model):
- 600 VA consumer UPS often supplies ~360 W usable — may just cover typical loads but could be borderline for peaks
- 1000 VA (pure-sine or PF-corrected) often supplies ~600 W usable — recommended sweet spot for your ~235 W typical load and 30–60m runtime
- 1500 VA / 2200 VA provides more internal battery capacity and runtime or ability to run additional devices

Model recommendations — Malaysia, budget‑sensitive
Notes: availability/prices in Malaysia vary across Lazada, Shopee, local IT resellers. Aim for a pure‑sine or high quality line‑interactive unit if you have Active‑PFC PSUs (Corsair AX760) and virtualization.

- Budget / lowest cost (acceptable if you can tolerate simulated sine):
   - APC Back‑UPS BX / BR series (look for BR models with higher internal battery)
   - CyberPower CP1000 / CP1500 AVRLCD (cheaper line‑interactive variants)

- Best value for compatibility (recommended):
   - CyberPower CP1000PFCLCD (1000 VA, pure sine / PFC compatible) — good balance: handles spikes and gives reasonable runtime for 30–60m at ~235 W
   - CyberPower CP1500PFCLCD (1500 VA) — more runtime/headroom
   - APC Back‑UPS Pro / BR1500GI (where available) — higher quality than BX/entry models

- Higher capacity / longer runtime (if you want single‑box solutions):
   - APC BX2200MI‑MS / other 2200 VA APC models — will comfortably handle the load and give longer runtime but cost is higher. Verify runtime table before purchase.

Choosing between simulated vs pure sine
- Pure sine is safer for Active‑PFC PSUs, ESXi hosts, and sensitive electronics. It costs more but reduces strange behaviour on battery.
- If budget is the main constraint and you can reboot gracefully on battery or avoid running VMs on battery, a cheaper line‑interactive unit may be acceptable.

Shopping checklist (what to verify on the product page/datasheet)
1) Usable watt rating (W) — not just VA. Ensure W >= expected peak (recommend W >= 431 W if you want peak coverage).
2) Runtime table — find minutes of runtime at 25%, 50%, 75% load to verify your target (30m/60m)
3) Output waveform / topology — pure sine preferred for Active‑PFC
4) Battery type and replaceability — check vendor replacement battery cost and availability locally
5) PoE considerations — if you need cameras and APs on during outage, ensure the PoE switch is protected by the UPS and your PoE budget is within the UPS runtime envelope
6) Local availability and warranty/service support in Malaysia

Example runtime check using BX2200MI‑MS (hypothetical)
- The BX2200MI‑MS is 2200 VA and may specify ~1200 W usable on vendor pages. That comfortably covers both typical (261 W mains draw) and peak (~431 W). The remaining question is internal battery Wh and runtime at your load — check the runtime chart. If the internal battery is small, consider external battery packs or a smaller pure‑sine 1500 VA with external battery options.

Recommended immediate action
- If your goal is >30 minutes runtime for the core server+switch: buy a 1000–1500 VA pure‑sine UPS (CyberPower CP1000PFCLCD or CP1500PFCLCD if available) — these typically deliver ~30–60 minutes at ~200–300 W and are cost-effective in many markets.
- If you prefer APC brand and see a BX2200MI‑MS at a good price and local support, verify the runtime table; it will also work but may be pricier.

Want me to fetch live prices in Malaysia?
- I can search Lazada / Shopee / local resellers for the above model names and return cheapest 2–3 options (tell me if you prefer new only, warranty, or specific sellers).

Appendix — quick formulas
- P_mains = P_it / η
- VA_required = P_mains / PF
- Wh_needed = P_it × hours / η
- Ah @ Vbat = Wh_needed / Vbat
