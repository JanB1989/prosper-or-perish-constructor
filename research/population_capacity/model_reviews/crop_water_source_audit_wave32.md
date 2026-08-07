# Underrepresented crop water-source audit — Wave 32

This audit closes the source-contract question for banana, cassava, and taro
without manufacturing labels.  It is deliberately a fail-closed audit: a
modern water-response file may be a same-geography physical fallback, but it
is never an observed 1337 yield or a population target.

## Acquired primary sources

| Crop | Source | Reproducible artifact | Result |
|---|---|---|---|
| Cassava | [FAO-endorsed AquaCrop v7.3 GUI release](https://github.com/KUL-RSDA/AquaCrop/releases/download/v7.3_typofix/GUI_AC7.3.zip) | `GUI_AC7.3.zip`, `cassava.CRO` | Official root/tuber `.CRO`; 360-day calendar and water-stress parameters parse successfully. `physical_fallback` only. |
| Taro | [Mabhaudhi et al. 2014](https://doi.org/10.1016/j.agrformet.2014.03.013), corroborated by the [WRC report](https://wrcwebsite.azurewebsites.net/wp-content/uploads/mdocs/2717%20Volume%202_web.pdf) and its [2024 parameter appendix](https://www.wrc.org.za/wp-content/uploads/mdocs/31241.pdf) | `wrc_taro.pdf`, `wrc_31241.pdf` | WRC Table 16-6 publicly reproduces 12 named AquaCrop parameter rows. The versioned `.CRO` is still stored off-server, so this is a source-backed fallback candidate requiring runtime reconstruction and tests; required physical label remains unresolved. |
| Banana | [FAO banana crop-water information](https://www.fao.org/land-water/databases-and-software/crop-information/banana/), [FAO crop-water chapter](https://www.fao.org/4/s2022e/s2022e02.htm) | URL evidence only | Static water envelope (1,200–2,200 mm/year, root depth 0.5–0.8 m, *K<sub>y</sub>* 1.2–1.35, *p* 0.35); no dynamic annual/perennial parameter file. Required physical label remains unresolved. |

The official [AquaCrop scope documentation](https://www.fao.org/4/i2800e/i2800e10.pdf)
also limits the engine's normal parameterisation to herbaceous crops and
points fruit trees/vines to separate guidelines.  Banana therefore cannot be
silently represented by a generic annual crop file.

## Closure result

* Required crop rows: **3**.
* Resolved physical fallback rows: **1** (cassava).
* Additional fallback candidates with public parameter evidence: **1** (taro, WRC Table 16-6; runtime reconstruction not yet accepted).
* Unresolved required rows: **2** (taro, banana).
* Training-target rows created: **0**.
* Acceptance state: **blocked**.

Cassava's release SHA-256 is
`e0b3dd2eae730b088588fdaf172d0ae0af6318b7d309a7d1be442f647bd2c5ce` and its
extracted `.CRO` SHA-256 is
`70b9086407e4b1e1de71300f9edcfa72bb0daa62d69a85e3fe5e9a408230600f`.
The WRC taro PDF SHA-256 is
`c0aab9566aa2bbe59f84b41bc0ac8409a0b7e7914e9f5174fe076988ecc73928`; the
parameter appendix `wrc_31241.pdf` SHA-256 is
`90ce734b34410046fda9c894131db94b9360d842ea84c0b0737b3bdbf1ceb492`.

## Strongest valid next steps

1. Reconstruct the taro `.CRO` from the public WRC Table 16-6, or obtain the
   original file directly from the authors/UKZN file server. Record the
   checksum and run the same semantic/unit audit before promoting it from
   candidate to fallback.
2. Implement a cited perennial-banana water-balance module from the FAO
   guideline equations, with explicit annual climate integration and broad
   uncertainty.  Until that implementation is independently tested, the FAO
   envelope remains validation-only.

No regional median, map-area, RGO, HYDE, trade, or starting-population fill is
allowed to close either gap.
