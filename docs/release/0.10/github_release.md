![Prosper or Perish 0.10](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/overview.jpg)

Prosper or Perish 0.10 Land and Larder

This release is compatible with EU5 1.4.5 and works with or without the Across the Pillars DLC.

This is a major update and is not save compatible, so I recommend starting a new campaign.

If you want to keep playing an older release, download it from the [releases page](https://github.com/JanB1989/prosper-or-perish-constructor/releases), unzip it, and copy the folder `Prosper or Perish (Population Growth & Food Rework)` into your EU5 mod folder, usually here:
`C:\Users\YourUserName\Documents\Paradox Interactive\Europa Universalis V\mod`

- Discord: https://discord.gg/HgFd69Sv83
- The Europedia as a website: https://janb1989.github.io/prosper-or-perish-constructor/examples/europedia.html
- Documentation of buildings, production methods and goods: https://janb1989.github.io/prosper-or-perish-constructor/

## Highlights

- **Food stays in the province.** The food market is gone: every province lives off its own store of Province Food, and the store decides whether its farms feed the province or sell to the market.
- **Months in store drive growth.** From slow decline when the store is empty to the fastest growth at two years.
- **New food buildings.** Tavern, Cookshop, Public Kitchen and Grange, a reworked Victualling Yard and Granary. Victuals are the only food that travels between provinces.
- **Arable Land.** Population capacity is the land that feeds people, drawn from a new real-world geography. Land improvements win land, farms take it, townsfolk bring their own.
- **A new map underneath.** New climates, vegetation, topographies, soils and fertility, redrawn rivers, and great rivers that fleets can sail.
- **A deeper economy.** Eight crop farms with four tiers each, Manual Labor as a good, manufacturing tiers with town rights and Old Ways recipes. Logistics now costs or wins market access.
- **Smarter AI.** It builds by prices and shortages, takes connected land in peace deals, lets go of land it cannot govern, colonizes more sensibly and fights more.

## Food

![Food](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/food.jpg)

- Food no longer exists on the market: provinces keep all their food, markets hold none, and the food slider costs next to nothing. The Cheap Food and Expensive Food modifiers no longer do anything.
- New good Province Food: the food in a province's store, made by subsistence farming and food buildings. It never leaves its province.
- Victuals are packed rations traded between markets. They become food again only where a building serves them.
- One list of staple foods (wheat, rice, millet, maize, potato, legumes, livestock, fish, wild game, wool, camels, fruit, olives). On the goods market they feed nobody until a building turns them into Province Food.
- Every building that makes a staple food also cooks part of its own crop for its province.
- The province store steers every staple producer: a low store means more Province Food and fewer goods for the market, a full store the reverse.
- Stored Food is one modifier per month in store, up to two years: an empty store slowly shrinks the province, rural settlements and then towns start growing as it fills, and growth is fastest at a full two years.
- A well-stocked province defends better, a nearly empty one worse.
- New Tavern in every province capital: it buys victuals and serves them to the province, above all when the store runs low. It replaces the Victuals Market.
- Cookshop and its upgrade Public Kitchen replace the Cookery: they cook staples into food for their own province. They stand at the province capital, get more levels the more staple farms and Victualling Yards the province has, and serve many regional dishes.
- New Grange: at province capitals the landowners pack what a full store can spare into victuals, more of it the dearer victuals are.
- The Victualling Yard is the market packer: in harbours and market centres merchants buy staples and pack them into victuals without touching the province store.
- Removed: Cookery, Victuals Market and the Food Revenue good.
- Food storage room rides on population: about a year of food fits without help, a two-year store takes Granaries. The Granary stands at province capitals, holds much more and keeps stored food from spoiling.
- Stored food spoils more slowly, the food advances cut spoilage further, and each new age brings food relief.
- Food needs retuned: every pop type but the peasants eats less than in 0.9, and prosperity raises every pop type's consumption.
- Free land: settlers live partly off what they gather, so peasants eat less the emptier the land. Overused land makes them eat more, but no longer raises unrest.
- Tribesmen live outside the food system: they eat nothing from the store and grow only while land is free.
- Laws, privileges and advances that made market food cheaper now give storage room, victuals output or lower peasant consumption.
- The game start is planned from the land and food model: farms first in hungry provinces, Granaries where a province starts in deficit.

## Arable Land

![Arable Land](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/arable_land.jpg)

- Population capacity is now Arable Land: the people a location's land can feed, from its climate, topography, vegetation, soil, fertility, rivers, coasts and lakes.
- Development no longer adds population capacity; towns and cities add a flat amount by rank.
- Land improvements win new land. New: Land Clearance, Drainage Ditches, Irrigated Fields, Qanats, Paddy Water Control and Marled, Ley and Four-Course Fields. Reworked: Irrigation, Terraces, Polders, Bund, Baray, Incamisana and the Jiangnan works.
- Every improvement level is worth the same land, how far an improvement goes depends on geography and grows with development, and the field improvements have no upkeep.
- Farms take land: every farm level takes a share of Arable Land, and a farm's limit counts the land other farms are already building on.
- Townsfolk bring their own land; only peasants without work live off the land. A growing town does not crowd its land, idle peasants do.
- Buildings no longer add or take capacity by themselves; only farms take land. The Royal Forest and the Elephant Hunting Grounds take land like farms.
- The land states are Abundant, Available and Overused Arable Land; empty land gives the strongest bonus, which fades as people arrive.
- Percentage capacity bonuses are gone: capitals and colonial nations get none, the food advances cut peasant food consumption instead, the Public Health advances give disease resistance, and Ville Franche rights give flat land.

## The World

![Navigable Rivers](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/navigable_rivers.jpg)

- New geography across the whole map: new climates (monsoon, savanna, semi-arid, subpolar and more), vegetation (coniferous, mixed and dry forest, marsh, swamp, savanna, scrubland, thicket, tundra), topographies (deltas, floodplains, rolling terrain, valleys), soil types and fertility, each with its own effects.
- What each location produces well follows its climate, soil, fertility and terrain; the raw-material bonus of its RGO comes on top, and each has its own flavour.
- Rivers are redrawn on the vanilla river lines, with almost all gaps closed.
- Navigable Rivers: the great rivers are waterways that fleets sail far inland. Their banks count as coast and can hold ports and shipyards. Reaches are Navigable River, Difficult Waterway or Falls, and countries discover the rivers along their own land.
- The new terrain has its own ground look, and the navigable channels are cut into the 3D terrain.
- Capitals on deltas, floodplains, rolling terrain, valleys and waterways get their own "Capital in ..." modifiers; lakeside locations get a little migration attraction and defence.
- Hostile armies move more slowly through rough terrain (mountains, jungle, swamps, forests and more) and a little more slowly everywhere.

![Variable Harvests](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/harvest.jpg)

- Variable Harvests swing a third as hard as in 0.9, and herds, flocks, fish and game are spared. You can switch them off in the game rules at any time, even in a running game.

## Buildings and Production

![Labor](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/labor.jpg)

- Eight crop farms with four tiers each replace the Farming Village line: Wheat, Rice, Millet, Maize, Potato, Legume, Olive and Cattle. Rice, maize, potato and olives need their native region or an advance. Later tiers make part of their food as Province Food and lose fewer workers in bad years.
- Mixed farming: herds manure the field crops and legumes feed the herds; beekeeping moved to the fruit orchards. Cash-crop farms produce four times as much per level and take plantation-sized land.
- New Camel Herders and Camel Stud for the EU5 1.4 camels good.
- New good Manual Labor: idle peasants supply it to their market, every production method pays part of its cost in it, and it never leaves its market. New labour buildings for scarce hands: Porters' Hall, Hiring Fair and Slave Gang Barracks.
- Manufacturing tiers: the first workshop tier turns out less and slows as it stacks, each later tier much more per level.
- Town rights for one good (cloth, tools, weaponry and many more): a Charter first, then Rights once the Printing Press advance is researched.
- Old Ways: an upgraded workshop keeps the recipes of the buildings it replaced, at lower output.
- Most producing buildings end in a Market slot, so they are extended where their good is dear. Tools are a smaller share of most recipes.
- RGO output is halved for every country, colonial nations excepted.
- Fewer workers per building level, and estates may build farms. Buildings hire and lay off workers three times as fast.
- Buildings without goods output (temples, libraries and the like) can no longer be closed.
- Upgrading a building costs 40% less than building it new. First-age guilds and crafts cost more, farms less per level. Idle peasants and devastation no longer make construction cheaper.
- Mines and quarries get more output per level the higher their tier, and a smaller growth penalty.
- Recipe fixes: alum in the dye and paper lines, gem cutting for jewelers, a stronger steel mill, retuned horse breeders.
- EU5 1.4 buildings fitted in: the Silk Production Guild replaces the Lucca guild, and the Seat of the Itinerant Court pays jewelry instead of gold.
- Removed: the road maintenance buildings (Road Wardens' Yard, Paviors' Yard, Macadam Works, Permanent Way Depot). Roads cost more gold to build.

## Markets and Logistics

![Logistics](https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/logistics.jpg)

- Building past a location's supported levels lowers its market access, level by level, instead of making construction slower and dearer.
- Logistics buildings win market access back and produce the Logistics good; part of their access always stays, they are staffed first, and a location builds one level at a time.
- New regional carriers: Caravanserai, Oasis Caravan Station, Yam Station, Banjara Tanda and Llama Caravan Post.
- Supported building levels are recalculated from terrain, rank, development and infrastructure; foreign buildings and land improvements bring their own support.
- Higher base market access, and market centres add more. Rivers and seas carry market access much further than land, navigable rivers best of all.
- Which market a location joins depends on development and market buildings, not on every building level.
- Exports and imports count fully in a market's prices, so shortages lift prices where the goods come from and specialist markets appear.
- Finished crafts and staple foods are cheaper to ship; victuals cost a third as much to ship.
- Pop demand retuned: less for staple foods, horses, salt, tea and cocoa; silk is an upper-class luxury and fur a court luxury in cool climates. Outward-looking societies want and grow more cash crops.
- Colonial nations become raw-material economies.
- The Printing Press advance makes merchants a little cheaper.
- The bookkeeping goods (Logistics, Manual Labor, Offset, Surplus Sales) cannot be traded and are hidden from the market views.

## AI, War and Peace

- The AI extends a building where its main good is dear and answers shortages and missing pop needs with new production.
- The AI builds food where a province's store runs low, raises crop farms where the crop pays, and stops piling up Taverns in full provinces.
- The AI builds Libraries and Universities where idle peasants could fill the jobs, skips roads that gain nothing, and builds logistics for profit like everything else.
- Peace deals: the AI takes only land connected to its own, or to land in the same deal, so far less border gore.
- AI nations let go of land they can never govern: pieces cut off from their capital with no hope of control become subjects or join a nearby subject, never during a war.
- The AI plans more wars against weaker neighbours, and worn-out civil wars end when one side is exhausted.
- Colonial charters: only colonial subjects, large realms and nations with many open-sea ports at home plan them. Explorations keep moving when the exploration budget is cut, and exploring costs less.
- Christian Iberian countries can research the New World advances without the institution; colonizers sail down the African coast.
- Historical aims for several AI nations: England, France, Castile, Portugal, Brandenburg, Muscovy and the Ottomans in the first century; Kiev west, Hungary east, Serbia and Bulgaria north. Castile and Portugal never fight each other.
- Starting gold: more for the Ottomans and Muscovy, less for Byzantium.
- New Sea Raid casus belli for nations that may hire privateers, with the Open Harbours and Sack the Market treaties and a Coastal Raid toggle for fleets.
- Ship upkeep equals the value of the ship's maintenance goods. Fleets sail 50% faster, and every non-levy ship blockades ten times as much.
- Sieges of unfortified locations take twice as long. Raised levies cost less output.
- Subjects that outweigh their overlord, and members of independence movements, lose more loyalty.

## Government and Research

- Average control no longer changes research speed.
- Becoming a kingdom or an empire needs less prestige.
- Tribes: tribesmen carry far more political power, each tribal privilege slows research, and Tribal Strongholds strengthen the tribes.
- Back to vanilla: how much goods prices move pop satisfaction.
- Maritime laws push societies towards naval, and the board of admirals brings more sailors.

## Interface

- The Europedia is rewritten as illustrated cards: Overview, Food, Food Production, Food Consumption, New Trade Goods, Logistics, Navigable Rivers, Rural Capacities, Labor, Variable Harvests, Arable Land, Population Growth and Other Changes. Every icon links to the real game object.
- The welcome situation and the Variable Harvests situation have their own panels.
- Location view: chips for stored food, land, harvest, soil, fertility and the raw material, and two bars, Land Usage against Land Capacity.
- Build panel: wider goods rows, a payback column and a payback sort order. Max-level tooltips show one row per source, including the land each farm and improvement uses.
- New map modes: Navigable Rivers, Fertility, Soil Type, Victuals Price, Manual Labor Price, Province Food Growth and six Pop Delta views. Market Food Price and Population Capacity are gone; Farming Capacity shows how full the land is.
- New icons for every mod building and town right, and new pictures for victuals and Province Food.
- Players of every other game language see the English text instead of raw keys.
- The mod has a stable id (`prosperorperish`), so other mods can declare it as a dependency.

## Fixes and Performance

- Location tooltips and the land bars cost far less per frame; the build panel's payback order no longer lags.
- The mod download is about half the size.
- The pop demand changes now load (a load error had dropped them).
- Conquest no longer removes Granaries, Taverns and Granges.
- Many error-log floods and script errors fixed.

Thank you to everyone who helped out, gave feedback and tested things.
