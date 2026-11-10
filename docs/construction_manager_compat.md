# Construction Manager compatibility (branch `cmf-compat`, 2026-11-10, Jan)

Jan: play Prosper or Perish with [Construction Manager](https://steamcommunity.com/sharedfiles/filedetails/?id=3736668860)
(CM, needs the Community Mod Framework, CMF) instead of our own Construction Plan, with Prosper or Perish's rules for
improvements, Granaries, food and logistics inside CM. Branch `cmf-compat` is `stockpile-prices` plus this; it carries no
Construction Plan (that lives on `location-profiles`).

**Playset (load order):** Community Mod Framework, Prosper or Perish, Construction Manager, **Prosper or Perish -
Construction Manager Compatibility** (last). The test playset "PP CM Test" (`pp_testing\eu5_playset.ps1 -Mode cm`) adds
the Iberia test world after Prosper or Perish.

**The patch** is its own repository, `pp-construction-manager-compat` (JanB1989 on GitHub; README there). It is
generated from the mods as installed:

- merged GUI files: the location window and the building view (both mods replace them), the build panel content, the
  build entry template, the food view types and the production row headers (both mods change them), merged part by part
  against vanilla; an unknown conflict stops its build;
- Prosper or Perish rules as CM rows (CM's priority list, Settings tab): CM's Auto-Food runs our food rule; new rows
  Granaries, Improvements (setting Improvement Line, % of capacity) and Logistics (setting Logistics Line, market access %).
  The rules are the Construction Plan's (its generator vendored as `plan_core.py`); they pick, CM builds (its queues, Gold
  Reserve, Min Discount, a free construction slot, the construction goods);
- CM's farming village food option switched off (Prosper or Perish has no farming_village; the links failed at load).

**Sync:** with `[cm_compat] repo` in `constructor.local.toml`, `ppc sync` rebuilds and deploys the patch after the mod
(`cli._deploy_cm_compat`). Without that the patch's merged copies of our location window and building view would hide
every later change to them. While EU5 runs the patch deploys interface and text only, like the mod.

**After an update of CM, CMF or the game:** rebuild the patch (`uv run ppcm build` in its repository); a moved anchor or a
new GUI conflict stops it with the place to look.

Not tested in game yet (2026-11-10): the patch loads without script or GUI errors at the main menu; the CM rows, the
merged windows and what the rules build were not run (no computer-use access, no test save).
