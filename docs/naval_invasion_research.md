# Naval invasion research: what a European AI needs to attack India or China (EU5 1.4, PP 0.10)

Branch `naval-invasion-testing`, 2026-10-12. Research only: no mod change on this branch.

Question (Jan): which casus belli, claims, cores and conquest desire do European naval/colonial AIs need to declare
war on a decently strong coastal state in India or China and actually take a location, and how many ships and
troops do they need in Europe for it.

Answer in one line: with PP 0.10 as shipped it cannot happen. Five independent gates stop it before any army moves,
two more stop the declaration, the AI ships no troops even with 71 transports, and PP's peace rule blocks the land.
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
  about a month, so the next check saw an estimate of 0.13-0.14 and the plan was dropped. No AI-declared war on an
  Asian target happened in about three game years of tests.

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

## Execution: no ferrying

Wars declared by console and then run by the AI (Spain -> CMO, Brittany -> Kobirhat, 1744-1746): both raised levies
(Spain ~450 army size) and shipped nothing in 12 months with 11 transports each, nor in 5 more months after +60
transports each (71). Both wars ended after 17-18 months on the defenders' ticking war score with no land taken.
(The 1767 test of the trade-expedition branch, run 12, did see 16 regiments shipped with 78-79 transports.)

## Peace: PP's adjacency rule blocks the foothold

Same war-start save, both targets fully occupied by console, +100 war score for the attacker, then the AI decides:

| Peace define | Spain -> CMO (North-China preference) | Brittany -> Kobirhat (preference removed) |
| --- | --- | --- |
| PP 0.10 (`AI_CONQUER_TREATY_DESIRE_ADJECENT` 100001, `FROM_WORTH_MULT` 0.00025) | no peace in 10 months at war score 99; its ideal deal held 19 `pp_cede_preferred_location` terms | peace after ~5 months, no land (its ideal deal held only gold, reparations and annulled treaties) |
| Vanilla (5 / 5) | took all 9 CMO locations within ~2 months | took 6 Kobirhat locations after ~5 months |

Under PP's rule a first foothold overseas needs a conquest preference, and in this one test the preference route
put the land into the AI's wish list but the war did not close. With vanilla's define the AI takes the land at once.

## What would have to change (levers, none built)

1. Desire: cores and a conquest preference on the target area, for example from the trade-expedition stations or a
   charter event. Cores alone or a CB alone do nothing at this distance.
2. Reach: diplomatic range of roughly 4,000-6,500 px for India and China (or targets inside range of an owned
   colony, untested).
3. Candidate list: enough cored locations to beat the European desire sums, or fewer European desires.
4. Forces: a peacetime army and navy the AI can afford, or a lower `win_war_chance_threshold` for colonizers.
   Lowering the threshold acts world-wide.
5. Execution: unsolved; even 71 transports did not make the AI ship troops in 1742.
6. Peace: either revert the adjacency define for overseas wars (not possible per war: one global define), or find
   out why the preference term does not close the war (next test: watch the peace offers being sent and refused).

## Kit and saves

- Run files `Documents\...\Europa Universalis V\run\pp_nv*.txt` (set-ups, traces, top-ups, peace test).
- Test mod `mod\PP Naval Invasion Test` (inert; `variants\vanilla_peace_defines.txt`), playset mode
  `eu5_playset.ps1 -Mode nv`.
- Saves `save games\pp_nv_*.eu5` (18, incl. `pp_nv_base_1742`, `pp_nv_war_start`); left for Jan to decide.
- Scripts and the AI probe are in the private engine-research repo (`naval/`).
