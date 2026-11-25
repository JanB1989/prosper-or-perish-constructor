# Starting technology ladder

Since 2026-11-25 (Jan), countries no longer all start with the same first-age advances. Every country in the 1337
setup has a starting group from 1 to 9. Every general first-age advance has a level. A country starts with an advance
only when the advance's level is at most the country's group. Group 9 starts with what every advanced country started
with before.

The design is in `config/starting_technology.toml`. Each country's group is in
`config/starting_technology_countries.csv`. The pass is `src/prosper_or_perish_constructor/start_technology.py`. It
runs as `uv run ppc start-tech apply|check` and in the finalize step of `ppc build` / `ppc sync`.

## How the game grants advances at the start

- An Age of Traditions advance is granted at game start when three things hold. Its level is at most the country's
  level, where an advance without a level counts as 0. Its `allow` and `potential` pass. At least one parent
  (`requires`) is granted.
- A withheld advance withholds its whole subtree, whatever levels the children carry.
- Levels are compared as plain numbers, so 1 to 10 work like 1 to 4 did in vanilla.
- Institution and region conditions still apply on top. A group 5 country outside Europe without feudalism gets no
  Feudalism, as before.

## The ladder

Years = the research points of the block at research 1.0, counted once the Age of Traditions is past: 17 x (1 +
`research_cost`) per advance, one point a month. They add up from group to group.

| group | name | advances gained | years for the block | years from group 1 |
| --- | --- | --- | --- | --- |
| 1 | Foraging bands | none | 0.0 | 0.0 |
| 2 | Village societies | Agriculture, Ranching, Horse Riding, Mining, Metallurgy, Iron Working, Local Smelters, Footmen, Archers; the law advances Mining Law, Distribution of Power, Cultural Traditions | 31.2 | 31.2 |
| 3 | Chiefdoms | Taxation, Bronze Working, Fine Metals Mining, Shipbuilding, Horsemen | 19.8 | 51.0 |
| 4 | Paramount chiefdoms and confederacies | Subject Nations, Trade, Faster Levy Recruitment | 9.9 | 60.9 |
| 5 | Oral kingdoms | City Building, Feudalism, Feudal Levy, Castle, Royal Court | 12.8 | 73.7 |
| 6 | Scribal kingdoms | Written Alphabet, Scriptorium, Cultural Acceptance, Mapmaking, Colonies, Road Building, Traditional Galley, Advanced Mining, Fort Limit, Meritocracy | 28.3 | 102.0 |
| 7 | Charter kingdoms | Codified Laws, Chancery, Weapon Guild, Windmills, Heavy Plough, Cog, Legalism, Medieval Administration, Pest House, Republican Assembly, Abacus, Educated Bureaucrats, Sanctioned Celebrations | 24.1 | 126.1 |
| 8 | Bureaucratic realms | Alchemy, Apothecary, Library, Paper Guild and its fibre pulp method, Hospital, Double-Checked Ledgers, Power Projection, Talented Traders, Silk Guild, Efficient Bureaucracy, Efficient Logistics, Province Governors, Right to Rule, Smooth Administration, Temporary Appointments, Non-Inheritable Offices | 29.8 | 155.8 |
| 9 | Commercial heartlands | More Merchants, Industrial Patronage | 9.9 | 165.7 |
| 10 | nobody starts with it | Improved Religious Organization and everything below it (Guilds, Scholasticism, Peasant Connections, ...) | | |

The table lists the config keys' names in short. The config is the source: `[levels]` names every advance with its
level.

Three changes to the tree go with the ladder (`[requires]`). Ranching hangs under Agriculture instead of Windmills.
Taxation becomes a root. Subject Nations hangs under Taxation instead of Codified Laws. Vanilla had put them under
branches a low group never holds.

The ladder does not gate laws a country starts with. Every country's setup block sets the mining law, the
distribution of power law and the cultural traditions law, and monarchies, republics and tribes set a few more. The
engine keeps a start law whether or not the country holds its advance and only logs a line for each (3,290 lines in
the first test). So the advances that do nothing but unlock such a law sit in group 2 or hang under Taxation
(group 3): Mining Law, Distribution of Power, Cultural Traditions, Royal Court Customs, the feudal de jure law, the
republican foundation law and the tribal religious values law. The immigration law stays with Mapmaking (group 6),
because Mapmaking also carries exploring; 536 countries below group 6 log that one line at game start.
Mali's Kouroukan Fouga hangs under Subject Nations: it is an oral charter, and under Distribution of Power's old
place Mali lost its start reform.

`[requires]` may also move a country, culture, religion or government advance of the first age. That is the only
section that may name one. The advance is replaced with its new parents. It gets no level unless vanilla gave it one,
and then it gets the remapped level. Mali's Kouroukan Fouga hangs under Subject Nations instead of Distribution of
Power, so Mali keeps its start reform Manden Kurufa.

The gate advances cost more (`[research_cost]`), and the AI adds a weight to Taxation, Subject Nations, City Building,
Written Alphabet and Codified Laws (`[ai_weight]`). The AI ignores research cost when it picks, so the weight is what
makes a country climb the ladder before it picks later-age advances.

## Research speed sits on the writing branch

Jan, 2026-11-25: "we disperse this research speed on them ... the AI researches these first and our other nations
have a head start". Vanilla gives every country 1 research a month. Here a country without writing gets 0.4, and five
advances add the rest (`[research_speed]`): Written Alphabet 0.2, Scriptorium 0.1, Chancery 0.1, Library 0.1, Paper
Guild 0.1. They add up to 1, so groups 8 and 9 research exactly as before and nobody gains. Societies of pops keep
vanilla's 0.1.

| group | research a month at the start |
| --- | --- |
| 1 to 5 | 0.4 |
| 6 Scribal kingdoms | 0.7 |
| 7 Charter kingdoms | 0.8 |
| 8 and 9 | 1.0 |

- The base is written by replacing vanilla's four auto modifiers that give `research_speed = 1` (countries with land,
  building, army and navy countries) in `in_game/common/auto_modifiers/pp_research_base.txt`; the pass copies them
  from vanilla on every build and changes that one number.
- The AI puts no value on flat research, so the five advances carry the highest AI weights of the ladder (300 to
  200); Codified Laws weighs 150 because the Chancery hangs under it. A country behind takes writing first, then the
  Scriptorium, then Library, Paper Guild or the law branch in any order, then the other gates.
- The same day the four big gates (Subject Nations, City Building, Written Alphabet, Codified Laws) went from
  `research_cost` 5.0 to 3.0 (Jan: "150 years, that's too long. For the worst nations probably 100").
- Catch-up, simulated (`pp_workspace/techstart/speed/`): a country that researches nothing else and has no literacy
  bonus holds every first-age advance that needs no institution after 99 years from group 2, 80 from group 3, 72 from
  group 4, 66 from group 5, 37 from group 6, 24 from group 7, 10 from group 8. Full research speed after 32 years
  (groups 2 to 5), 16 (group 6) and 7 (group 7). If the AI ignored the weights and took the five advances last,
  group 2 would need about 150 years.
- Why not a bonus per advance researched (asked the same day): the game can count them (`num_of_advances_researched`
  in an auto modifier), but it would be a growing global buff and widen gaps for good. Left out (Jan).

Advances with a country, culture, religion or government condition keep no level of their own unless vanilla gave
them one. Those levels are remapped: 1 to 2, 2 to 6, 3 to 8, 4 to 10 (`[specific_remap]`). The others are granted
with their parents. Advances of later ages are not touched.

## Countries

- `config/starting_technology_countries.csv` has one row per country block of the setup's `10_countries.txt`, landless
  societies and formable tags included. The columns are tag, group, confidence, basis and note.
- To change a country's group, edit its row and rebuild. The pass fails with the tags named when a setup country has no
  row, a row names a tag the setup does not have, or a group is outside 1 to 9.
- The rows were researched on 2026-11-25, region by region, against one decision rule (the nine groups and the
  checklist are in the hub folder `pp_workspace/techstart/history/groups.md`; each region's rules and hardest calls
  in `pp_workspace/techstart/assign/P*.md`). `basis` names the deciding evidence; 635 rows are marked low
  confidence, mostly small or obscure polities. `tools/start_technology_placeholder.py` can still write a
  placeholder from the vanilla levels for a fresh checkout that has no table.
- Floors (`[floors]`). A country that is the overlord of any subject in the setup's diplomacy starts at group 4 or
  higher, because a subject relation at game start is invalid when the overlord lacks Subject Nations. The report
  lists every country a floor raised.
- Caps (`[caps]`). A landless society of pops (`type = pop` in its setup block) is written at level 1 whatever its
  group, so it holds nothing, as in the unmodded game. With their group's advances these societies held Taxation
  without a capital (script errors in the coin laws) and three of the four advances the game asks for before a
  society may settle. Their group stays in the table.
- The levels go into `main_menu/setup/1337/28_pp_start_technology.txt`. Each country gets a partial block with only its
  level. A later setup file's partial block merges into the country and its level wins. Land, government and ruler stay
  as they are. Only `10_countries.txt` sets levels, and the pass's file is read after it.

## Start buildings

A country keeps a start building only when its group holds the advance that unlocks the building. The level alone
decides. Vanilla's institution and region conditions are left as they were, and so are older mismatches such as bunds
and polders.

- The building list is `config/starting_technology_buildings.csv`: each building unlocked only by ladder advances, the
  advance and its level. The pass writes it from the advances.
- The World Builder start stage reads that table. It drops every setup row of such a building in a location whose owner
  is below the level, and the start placement never places one there.
- The setup files are rebuilt from vanilla and the start plan on every stage run, so the drop is reversible. Raise a
  group in the CSV, rebuild, and the buildings come back. The CSV is a World Builder input, so the rebuild reruns the
  start setup.
- The stage reads the table rather than the advance files, so an advance edit does not rerun the start setup.
  `ppc build` and `ppc sync` refresh the table before the stage. A table that changes in the finalize step (an advance
  file the render writes) is picked up on the next build, and the test below catches it until then.
- An upgraded building is dropped, never downgraded to its predecessor.
- Start buildings only in a vanilla or DLC setup file the mod does not ship stay untouched. Today that is Granada's
  watchtowers and forts in the Across the Pillars file, which no ladder advance unlocks.

## Reports

`artifacts/data/start_technology/`:

- `countries.csv`: tag, vanilla level, the CSV group, confidence, basis, the floor and why, and the final level.
- `removed_start_buildings.csv`: tag, building, location, levels, unlocking advance, its level and the country's
  group. Source "setup" is a removed setup row. Source "placement" is a level the start plan wanted but did not place.
- `setup_requirements.csv`: subject types, laws, policies, government reforms, estate privileges and parliament types
  that the start countries set and that need a ladder advance. A thing needs one when the advance unlocks it, switches
  it on (council parliament, subjects), or is named in its definition's `has_advance`. Each row counts the countries
  below the advance, per group, and with vanilla's levels for comparison. These are not fixed automatically.
- `withheld_specific_advances.csv`: for every country on the map, the country-specific first-age advances it would
  start with under vanilla's levels but not under the ladder. Each row names the blocking ancestor, its level, the
  country's group and what the advance unlocks. Only advances whose own or an ancestor's `potential` names tags
  (`has_or_had_tag`, `tag`) are judged, and only by the tag. Culture, religion, government and other conditions are not
  evaluated, so advances gated only by them (about 250) are left out. This is the report that shows a lost start reform
  or unit, as Mali's was.

## Tests

`tests/test_start_technology.py` fails when:

- a setup country has no row in the country table, or a row has no setup country;
- a general first-age advance has no level, or `[levels]` names one that does not exist or is not general;
- a child starts below its parents, or the remap lowers a level or misses one. A specific advance moved by
  `[requires]` without a level is fine under any parent;
- a replaced block differs from the effective game block other than in the configured keys, which is what a game
  update to that advance looks like;
- the setup file misses a country, carries a level outside 1 to 9 or skips a floor, or another setup file that sets
  levels sorts after it;
- the advance file does not sort last;
- a start building in the compiled setup needs a ladder advance above its owner's group;
- group 9 does not hold exactly the general advances a vanilla level-3 country holds;
- `check` is not current after `apply`.

## After a game update

Run `uv run ppc start-tech check` and the test file. A new or renamed country needs a row. A new general first-age
advance needs a level in `[levels]`. A changed replaced advance is carried by `uv run ppc start-tech apply`. Then run
`uv run ppc vanilla-pins record`, because the pass's REPLACE blocks are pinned like every other vanilla copy.
