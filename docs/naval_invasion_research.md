# Naval invasion research: what a European AI needs to attack India or China (EU5 1.4, PP 0.10)

Branch `naval-invasion-testing`, 2026-10-12. Research only: no mod change on this branch.

Question (Jan): which casus belli, claims, cores and conquest desire do European naval/colonial AIs need to declare
war on a decently strong coastal state in India or China and actually take a location, and how many ships and
troops do they need in Europe for it.

Answer: with PP 0.10 as shipped it does not happen, and no number of ships or regiments in Europe makes it happen.

- Seven gates stop the AI before it picks an Asian target. Even with every gate opened by console it declares only
  while a large extra army is kept topped up; Spain declared on CMO by itself once.
- In the war the AI never sends an army from Europe (tested with up to 111 transports). Its armies weigh distance
  against task priority, and a task 4,000-6,000 map pixels away always loses to any task at home. With that weight
  cut tenfold a second, undecoded step still keeps them home.
- What does work is a foothold next to the target with an army standing in it. Brittany, with one location beside
  MDY (Visayas, no joined states) and 20 regiments against 21, took 4 locations on Panay within 8 months under PP's
  rules. Spain with 20 regiments beside CMO occupied 3 of CMO's 9 locations by itself. 20 regiments against 40-100
  did nothing or lost.
- Against a single state the peace gives the land connected to the foothold, PP's adjacency rule included. Against
  a coalition it does not. CMO led seven joined Chinese states, so Spain's overall war score stayed at 7-10 while it
  held 3 CMO towns. Without a conquest preference the peace gave nothing, under PP's peace define and vanilla's alike.
  With one it gave 7 scattered locations of the joined states, none of CMO's (PP's preference exception).

The details below say which gate does what and what it would take to open each one.

## Set-up

- Base save: run 112ad572 autosave of 1 April 1742 (Age of Revolutions), copied to `pp_nv_base_1742`. PP 0.10 live
  mod plus the inert test mod `PP Naval Invasion Test` (conquest preferences and a diplomatic-range modifier, used
  only by console run files; a vanilla peace-define variant copied in by hand for one launch).
- Pairs (attacker -> target, all coastal): Great Britain -> Bengal (rank 5, 393 locations), Portugal -> Korea
  (rank 14, 147), Spain -> Hangzhou (WUU, subject of a Chinese state), Brittany -> Sri Lanka (DBD, subject of
  Vijayanagar), Spain -> CMO (Shandong coast, 9 locations, independent), Brittany -> Kobirhat (Bengal coast,
  20 locations, independent), Two Sicilies -> Dai Viet (CB only, control), Denmark -> a Zhejiang state (CB only).
- Set-ups added by console: cores (`add_core`), conquest preferences (`add_area_preference`), conquer-province CBs
  (`add_casus_belli`), diplomatic range, regiments, warships, transports, diplomats, gold.
- Measured with an in-game trace (script values `conquer_desire`, `within_diplomatic_range`,
  `any_potential_expansion_target`, `country_strength`, `navy_size`, army positions, war score, ownership), the
  AI conquer-desire map and `potential_expansion_targets` from saves, and a probe on the AI's own target scoring
  and declaration check (private notes). Ten launches, about 12 game years in total.

## The chain the AI walks, and where Asia drops out

| Step | What the AI needs | Result for Europe -> India/China |
| --- | --- | --- |
| 1. Conquest desire on a location | Distance from the capital below an allowed reach of `100 + 50 x (age - 1) + 0.5 x owned locations` map pixels (defines `AI_CONQUER_DESIRE_DISTANCE_BASE`, `_PER_AGE`, `_PER_COUNTRY_SIZE`; beyond it the desire is 0, `CONQUER_DESIRE_DISTANCE_FLOOR = 0`). A floor of 0.25 applies only with a core **and** a conquest preference (> 1) on that area. | London-Bengal is 4,374 px (Western Europe to India 3,800-4,600, to China and Korea 5,400-6,200); Britain's reach in 1742 was 578 px (measured in the save, 579 predicted). No European country had any desire on any South, East or South-East Asian location in the 1742 and 1792 saves. Test: core + preference -> desire 100 (the maximum); core alone 0; preference alone 0 (every non-cored location of the preferred region stayed 0); CB alone 0; CB + preference 0. |
| 2. Diplomatic range | Target within the attacker's diplomatic range (base 1,000 + rank bonus, x advances and laws). | European ranges 2,025-2,400, the targets were all out of range. Without range the target passes the candidate filter but is never scored; with +20,000 range (test modifier, effective after the monthly refresh) it is scored. |
| 3. Top-20 candidates | Only the 20 candidates with the highest country-level desire are scored (`AI_NUM_EXPANSION_TARGETS`). | Britain's European candidates carry desire sums of 200-12,700. Bengal never entered Britain's list, not with one cored location and not three months after coring all 155 of its Bengal-region locations. Spain's 9-location CMO was scored in one session but not after a reload, when European desires were higher. |
| 4. One objective at a time | A country with an expansion objective keeps it while its score stays at 15 or more and looks for no new one. | Britain's objective on a European target waited for a CB every month (up to `MONTHS_TO_WAIT_FOR_CASUS_BELLI` = 24 months), so it never looked at Asia. |
| 5. Win estimate | A simulated war: whole-realm strength of each side, including every country that would join (weights 0.5-1), army = raised levies + 3 x regulars (x modifiers), total adds manpower x 0.5 and tax base x 0.05; estimate = the lower of the army and total sigmoids (`WAR_WIN_CHANCE_SENSITIVITY` 8). Must reach the country's `win_war_chance_threshold` (0.6 base, lower limit 0.5, personality modifiers). | European peacetime armies are tiny (Spain 2 regiments, Portugal 6, Britain 15). Spain vs CMO 0.10, Brittany vs Kobirhat 0.009, Portugal vs Korea 0.013. The threshold varies widely: Spain needed more than 0.59, Britain still scored European targets at an estimate of 0.07. |
| 6. Navy | For a target it does not border: navy share at least 0.5 against the defender side (sailors + ship strength + levy boats x 10 + tax base x 0.05), unless an ally or subject borders the target. | Spain 0.45 -> rejected; +15 galleons 0.58 -> accepted. Portugal vs Korea 0.41 until +30 galleons (0.51). |
| 7. Transports | The overseas branch also needs a navy that can carry troops. | With 15 transports CMO became Spain's target; once the AI scrapped them, CMO was dropped although it scored 62,000. |

Who joins the defence matters as much as the target: the 9-location CMO brought seven Chinese warlord states with
raised levies into the estimate (and into the real war); Kobirhat brought Nurpur (rank 15), its fiefdom Kandahar,
Dai Viet and others. Bengal and Korea brought only their own subjects. Subject targets bring their overlord
(Hangzhou -> its Chinese overlord, Sri Lanka -> Vijayanagar, rank 1), so they are never sensible targets.

## Declaration (after a target is chosen)

The objective is checked about once a month. It needs war exhaustion at most 5, a usable CB (otherwise it waits),
the declaration's own costs (a free diplomat), military readiness (stability not negative and a treasury of at
least half the estimated war cost), and the win estimate and navy share again on the simulated war.

- Spain -> CMO with everything in place returned "declare" twice (estimate 0.96-0.98, navy 0.60-0.64).
- Earlier checks failed on a missing diplomat (Spain sits at 1 diplomat each month; +5 fixed it) and on readiness
  (no war chest; +3,000 gold fixed it).
- Each time, the AI disbanded the regiments and scrapped the ships its maintenance budget could not carry within
  about a month, so the next check saw an estimate of 0.13-0.14 and the plan was dropped.
- When the console kept the extra army present (+45 regiments topped up every 5 days, plus galleons, 15 transports,
  diplomats and gold), the check returned "declare" three months in a row (estimate 0.77-0.80, navy 0.61-0.68) and
  **Spain declared war on CMO by itself** about three months after the first "declare" (the AI first raises its
  maintenance, `MONTHS_TO_WAIT_FOR_MAINTENANCE` = 3). That is the only AI-declared European war on an Asian target
  in these tests, and it needed every gate above opened by console.

## Forces needed in Europe (1742 save)

Strength boosts were console regiments (arquebusiers, 2,000 men each) and Iberian galleons added to the attacker's
own forces; estimate = the AI's own number before its threshold.

| Attacker -> target | Own forces | Win estimate as regiments are added | Navy share |
| --- | --- | --- | --- |
| Spain -> CMO (9 locations + 7 joiners) | 2 regiments, 20 ships | +10: 0.23, +30: 0.59, +45: 0.76, +70: 0.91 | 0.45 own; +15 galleons 0.58 |
| Portugal -> Korea (rank 14) | 6 regiments, 59 ships | 0.013 own, +50: 0.64, +150: 0.98, +350: 0.997 | 0.41 own; +30 galleons 0.51, +90 0.64 |
| Portugal -> Bengal (rank 5) | 6 regiments, 59 ships | +350 regiments: 0.97 (threshold not swept) | +90 galleons 0.56 |
| Brittany -> Kobirhat (20 locations + joiners) | 11 regiments, 52 ships | 0.009 own | 0.38 |

So a European crown needs a standing army of several dozen (small Chinese state) to a few hundred (Korea, Bengal)
regiments in peacetime, a navy at least as strong as the defender side's, transports, a free diplomat and a war
chest, all kept for the months the declaration takes. The AI's budget does not keep such an army.

## Execution: the armies never leave Europe

Wars declared by console and then run by the AI (Spain -> CMO, Brittany -> Kobirhat, 1744-1746): both raised levies
(Spain ~450 army size) and shipped nothing in 12 months with 11 transports each, nor in 5 more months after +60
transports each (71). Both wars ended after 17-18 months on the defenders' ticking war score with no land taken.
The war Spain declared by itself (1743) went the same way: 30 transports, 130-140 regiments in Europe, nothing
shipped in about 15 months, peace on ticking war score (-13) without land.

Why (AI war tasks, read from saves and measured with the probe):

- At war the AI splits its war goal into tasks: a siege task per enemy (the war target's land at priority 3, the
  joined states' at 1-2), chasing enemy armies (8), gathering its own levies (10), logistics (2). Spain had 19 siege
  tasks in China; none had a single army for 2-15 months. Its armies sat in gathering tasks at Madrid.
- Each army gets a score per task: 100 per priority point (`AI_MILITARY_ASSIGNMENT_PRIORITY_FACTOR`), doubled when
  the army is strong enough for the task (otherwise not scored), minus 1 per map pixel between the army and the
  target (`AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_FACTOR` -1; ships -0.1). Armies go to the best-scoring tasks.
- Spain's 36-regiment armies passed the strength check for China (0.98-1.0), but at ~5,600 px from Madrid the China
  tasks scored -3,900 (chasing CMO's army, priority 8) to -5,300 (a joined state's siege, priority 1), while
  Spain's tasks at home scored up to +15,900 in the same pass. A priority-10 task overseas still loses by 3,600.
- Transports do not enter the score: +100 brigs (111 transports, room for a whole 36-regiment army) changed
  nothing in 5 months (scores unchanged, nothing at sea).
- With the distance weight cut tenfold (test mod, `AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_FACTOR` -0.1) the China
  tasks scored positive (CMO siege +36 to +64, chasing CMO's army +1,030 to +1,060) and the tasks did want troops
  (CMO siege 1 army, the joiners' sieges 3-8). The assignment then put Spain's 36-regiment armies on the CMO siege
  now and then, but they never moved and were dropped again; no transport task was ever created and the 111
  transports stayed idle. Brittany (111 transports) the same. 8 months, nothing at sea. A second rule after the
  assignment (the army's request for a transport fleet) stops the move overseas; it was not decoded.

(The 1767 test of the trade-expedition branch, run 12, did see 13-16 regiments shipped to India with 20 and 78-79
transports; why those armies scored their Indian task above everything at home was not measured.)

## Foothold: an army standing next to the target does fight

Same console wars (war-start save, PP 0.10 defines), but each attacker first gets one location next to the target
and arquebusier regiments standing in it, topped up whenever the local army falls below half. Gaomi lies beside
CMO's Jiaoxi; Agartala beside the Kobirhat port. This stands in for a trade station or colony with a garrison.

| Launch | Attacker (local regiments) | Enemy regiments in the region | War | Peace (PP define) |
| --- | --- | --- | --- | --- |
| nv13 | Spain (20-26), North China conquest preference | 18-21 | occupied 3 of CMO's 9 locations in 8 months, war score +72 to +81 | after ~20 months: 7 locations of the joined states around Beijing, Datong and Shandong (the preference exception); none of CMO's |
| nv13 | Brittany (20), Bengal preference | 39-104 | never attacked, war score fell to -20 | after ~20 months, nothing |
| nv14 | Spain (20-25), preference removed | 18 | the same 3 CMO locations, war score +82 | after ~18 months, nothing |
| nv14 | Brittany (60), Bengal preference | 60-104 | took the target port once the defenders fell to about 60 | after ~18 months, nothing; Agartala returned |
| nv15 | as nv14 (Spain without preference, Brittany 60), vanilla peace define | 18 / 35-104 | Spain the same 3 CMO locations (+81); Brittany held the port for 3 months, then lost it (-21) | both after ~18 months, in the same month as nv14: nothing for either |

Targets without joiners (nv16, 1742 base save, console wars, PP defines, no conquest preference, a foothold next
to the target and 20 regiments):

| Attacker -> target | Enemy regiments in the region | Result |
| --- | --- | --- |
| Brittany -> MDY (Visayas, 7 locations, no joiners) | 21 | occupied 3 locations in ~4 months (war score +94); peace after ~8 months: Brittany took 4 locations on Panay (Araut, Aklan, Irong-Irong, Malandog), all connected to the foothold; MDY kept Negros |
| Spain -> MSN (Deccan, 9 locations) | 46-67 | Spain's 20 regiments lost within 6 months; peace gave the foothold back |
| nv17: Brittany -> MDY with 10 regiments (topped up once) | 22-27 | the same: target occupied in month 7, 4 Panay locations at the peace in month 8 |
| nv17: Spain -> MSN with 60-64 regiments | 6-34 | never attacked in 12 months (war score -15): MSN was joined by BND, a Deccan state of 323 locations |

A foothold does not make the AI choose such a target by itself: in these saves neither Brittany (after taking Panay)
nor Spain (beside MSN) had any conquest desire for the neighbouring locations, because the desire's distance is
measured from the capital.

- The local army is assigned and fights like any army at home: from the foothold, distance no longer counts against
  it.
- Force size: about as many regiments as the enemy has in the region (20 against 18 worked; 20 against 40-100 never
  attacked; 60 took the target port only when the defenders fell to about 60, and could not hold it).
- Spain's own ideal deal before both peaces listed 9 CMO towns beside the foothold (CMO led the defending side).
- All six foothold wars ended 17-20 months after the declaration; in nv14 and nv15 both wars ended in the same month.
  With vanilla's peace define the outcome was the same as with PP's, so the missing CMO land is not PP's adjacency
  rule.
- The reason is the coalition: Spain's +72 to +82 was its score against CMO alone. The war's overall score (read
  from the save) stayed at 7 (nv14, nv15) and 10 (nv13), because CMO led seven joined Chinese states and Spain fought
  only CMO. Spain's war goal (Jiaoxi and its two neighbours) was never fully held either. A peace with the war leader
  pays for towns out of the overall score, so the 3 occupied CMO towns were out of reach. The land in nv13 came only
  through the preference exception on the joined states' locations (7 locations at an overall score of 10).

## Peace after a full occupation (console)

Same war-start save without footholds, both targets fully occupied by console, +100 war score for the attacker,
then the AI decides:

| Peace define | Spain -> CMO (North-China preference) | Brittany -> Kobirhat (preference removed) |
| --- | --- | --- |
| PP 0.10 (`AI_CONQUER_TREATY_DESIRE_ADJECENT` 100001, `FROM_WORTH_MULT` 0.00025) | peace after ~13 months (still at war score 99 after 10); its ideal deal held 19 `pp_cede_preferred_location` terms; took 15 locations of the joined Chinese states across three areas of the preferred region (Dadu = Beijing and its prefectures, the Shandong peninsula from Penglai to Muping, one in Datong), none of CMO's own | peace after ~5 months, no land (its ideal deal held only gold, reparations and annulled treaties) |
| Vanilla (5 / 5) | took all 9 CMO locations within ~2 months | took 6 Kobirhat locations after ~5 months |

Under PP's rule a first foothold overseas needs a conquest preference. With one, the exception term
(`peace_treaties/pp_cede_preferred_location.txt`) accepts any location of any losing participant inside the preferred
areas that does not border the winner and is outside its capital region; here that was Beijing and a scattered
band of northern China, not the war goal, and the war took six times longer to close than under vanilla's define.
With vanilla's define the AI takes the war target's land at once. Worth a look independently of overseas wars: the
same term can pull scattered land from a coalition in any preferred region.

## What would have to change (levers, none built)

1. Desire: cores and a conquest preference on the target area, for example from the trade-expedition stations or a
   charter event. Cores alone or a CB alone do nothing at this distance.
2. Reach: diplomatic range of roughly 4,000-6,500 px for India and China (or targets inside range of an owned
   colony, untested).
3. Candidate list: enough cored locations to beat the European desire sums, or fewer European desires.
4. Forces: a peacetime army and navy the AI can afford, or a lower `win_war_chance_threshold` for colonizers.
   Lowering the threshold acts world-wide.
5. Execution: the AI does not send armies from Europe, whatever the transports (up to 111). Distance counts against
   every task (`AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_FACTOR` -1 per pixel against 100 per priority point); at -0.1
   the armies were assigned but still never sailed (an undecoded transport step). The working path is a foothold
   with a standing army: a station or colony next to the target and regiments kept there, about as many as the
   enemy has in that region. Keeping them there costs maintenance the AI would otherwise cut.
6. Peace: the adjacency define is global (no per-war setting). The preference exception does give overseas land but
   picks scattered locations of every losing participant (each is a recipient of the term); restricting it to the
   war's original target and the war goal's area would make it a foothold rule. Not built. In the foothold wars the
   occupied land next to the foothold was not taken under either define: against a coalition the overall war score
   stays low however well the attacker does against the target itself.

## Kit and saves

- Run files `Documents\...\Europa Universalis V\run\pp_nv*.txt` (set-ups, traces, top-ups, peace test).
- Test mod `mod\PP Naval Invasion Test` (inert; `variants\vanilla_peace_defines.txt`), playset mode
  `eu5_playset.ps1 -Mode nv`.
- Define variants in the test mod's `variants\` (`vanilla_peace_defines.txt`, `assignment_proximity_defines.txt`),
  copied to `loading_screen\common\defines\zz_pp_nv_defines.txt` for one launch each.
- Saves `save games\pp_nv_*.eu5` (incl. `pp_nv_base_1742`, `pp_nv_war_start`, the foothold runs `pp_nv_nv13*`,
  `pp_nv_nv14*`, `pp_nv_nv15*`); left for Jan to decide.
- The AI's war tasks are in the save (`military_objective`, `strategic_military_objective`); the private kit reads
  them. Scripts and the AI probes are in the private engine-research repo (`naval/`).
