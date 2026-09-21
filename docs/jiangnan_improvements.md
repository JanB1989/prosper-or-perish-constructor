# Jiangnan land and water improvements

Two regional improvements model work already established by the 1337 start. They are available immediately in eligible locations, independently of the owner's country.

| Building | Shared family | Strength | Displayed capacity per level | Absolute family ceiling | Starting distribution |
| --- | --- | --- | --- | --- | --- |
| Jiangnan Canal Network | Irrigated Fields | 2.5× | 5,560 people | 160 levels | 23 locations; 1,587 levels; 32–119 per location |
| Jiangnan Hill Terraces | Field Management | 3× | 7,700 people | 60 levels | 17 locations; 277 levels; 1–31 per location |

The minimum is zero. The actual maximum is the existing family's terrain, attributes and development equation, floored and clamped to its ceiling, minus the levels of the other family members. At the current start, canal locations have family caps of 69–120 and terrace locations 27–31. Neither variant adds a second allowance for the same land. Capacity uses the handover's unrounded family value times the configured strength, then the game's usual two-decimal capacity conversion.

Both buildings cost 75 gold before location modifiers and employ 75 peasants per level. Their maintenance method consumes 0.1 manual labour and 0.025 lumber per level. Capacity represents lasting physical land improvement, using the same raw-modifier convention as the other improvement buildings.

## Scope

The dominant local culture must be Wu, Yue Wu, Wuzhou, Xuanzhou or Jixi. This local Chinese culture lock combines with province and physical gates; ownership by a Chinese country alone grants no access.

- **Canals:** Suzhou, Songjiang, Jiaxing, Huzhou, Hangzhou, Changzhou and Zhenjiang provinces; subtropical or subtropical-monsoon climate; delta, wetland or floodplain terrain; a river, lake adjacency or coast.
- **Terraces:** Ningguo, Huizhou, Hangzhou, Huzhou, Jinhua, Chuzhou, Shaoxing, Ningbo and Taizhou provinces; the same climates; hills, mountains, plateau or rolling terrain.

The configuration is in `constructor.toml`. Its structured gates generate both in-game location triggers and starting-placement eligibility. The start planner aggregates all population types to determine dominant culture, substitutes the strongest eligible regional variant for the general family, then fills improvement levels toward population demand within the existing caps. Existing opaque country/advance locks on other niche buildings are not evaluated or bypassed.

## Current-start effect

Capacity here is the starting-placement model, before commercial farms consume subsistence land, consistent with the prior World Builder comparison.

| Location | Previous capacity | New capacity |
| --- | ---: | ---: |
| Jiaxing | 535,640 | 914,840 |
| Changshu | 376,410 | 606,180 |
| Huating | 491,340 | 641,480 |
| Nanhui | 481,170 | 604,620 |
| Ningguo | 276,200 | 430,100 |
| Lin'an | 281,930 | 435,830 |
| Anji | 366,010 | 468,840 |
| Dongyang | 382,940 | 476,320 |

Compared with the start before regional improvements, owned locations above capacity fall from 168 to 158; excess population falls from 7,342,411 to 5,739,334. Compared with the initial 1.5× variants, this is 163 to 158 locations and 6,512,549 to 5,739,334 excess people. All capacity changes are confined to the 40 regional placements. Bijnot and Cairo are unchanged. Jiaxing, Huating, Nanhui, Anji and Dongyang now fit their starting population; Changshu, Ningguo and Lin'an still exceed capacity. Starting levels have been recalculated toward population demand, retaining the existing family caps.

`artifacts/data/worldbuilder/jiangnan_distribution.csv` records every placement, its starting level, minimum, maximum at starting development, other family levels, province and culture. The normal `uv run ppc worldbuilder apply` regenerates the actual setup distribution; `uv run ppc build --refresh-assets` renders the blueprints and icons. `uv run ppc worldbuilder check` includes niche capacity when reading the resulting setup.

## Historical and art references

- [ICID: Lougang Irrigation and Drainage System of Taihu Lake Basin](https://icid-ciid.org/award/his_details/53): the connected canals, gates, embankments and polders provided drainage, irrigation and transport, supporting the region's Yuan-period agriculture.
- [Zhejiang: Yunhe, beyond the terraces](https://www.ezhejiang.gov.cn/lishui/2022-01/07/c_696838.htm): the terrace tradition dates to the Tang and expanded during the Yuan and Ming. This supports terraces as a period-appropriate regional technique; it does not establish exact county-level construction counts. Strengths and levels are gameplay modelling choices.

Both icons were generated with the built-in imagegen tool. Full prompts are retained in their accepted building blueprints. The source PNGs have real alpha and were resized to 512×512 before conversion through `eu5_building_pipeline.write_icon_asset`. Readability was checked at 48, 64, 96 and 128 pixels.
