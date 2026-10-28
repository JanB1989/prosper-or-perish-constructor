# Posting the 0.10 release

Drafts, written 2026-10-28. Nothing here is posted yet.

## The three texts

- **Steam Workshop description** (`steam_workshop_description.bbcode`): the Workshop page, "Edit title & description". Once
  posted it replaces `docs/steam_workshop_description.bbcode`, the copy of the live description.
- **Steam change notes** (`steam_change_notes.bbcode`): the change note of the 0.10 upload (asked for on upload, or added
  later on the Workshop item's "Change Notes" tab).
- **GitHub release** (`github_release.md`): the body of the release for tag `0.10.0`, title `0.10 Land and Larder Release`.

## Limits (checked 2026-10-28)

- **Steam description:** at most 8,000 bytes (Steamworks `k_cchPublishedDocumentDescriptionMax`). The drafts use plain
  ASCII, so bytes = characters.
- **Steam change notes:** Steam documents no limit (its constant is marked unused); the draft stays under 8,000 bytes to
  be safe.
- **Steam title:** at most 128 bytes.
- **Steam BBCode:** h1 to h3, b, i, u, strike, spoiler, noparse, hr, url, list, olist, quote, code, table. Workshop
  descriptions also show `[img]` with a public URL, shrunk to the description column.
- **Steam gallery images** ("Add/edit images & videos"): each under 1 MB. The pictures here are 1600 x 533 JPEG,
  260 to 310 KB each.
- **GitHub release body:** at most 125,000 characters (the API's error message; GitHub's docs do not state it). Attached
  files under 2 GiB each.

## Pictures

- The Europedia paintings at web size: `docs/assets/steam/0.10/*.jpg` (12 pictures, one per Europedia card).
- GitHub Pages serves them from `main` at
  `https://janb1989.github.io/prosper-or-perish-constructor/assets/steam/0.10/<name>.jpg`. They appear there only after 0.10
  is merged into `main` and pushed; until then the image links in the drafts show nothing. Open one picture link before
  posting the Steam texts.
- For the Workshop gallery, upload the same files by hand (overview, food, arable_land, harvest, navigable_rivers,
  logistics).
- The old description pictures (`docs/assets/steam/*.png`, May 2026) show the 0.9 interface and the three capacity
  buckets, which are gone; the new description does not use them.

## Check before posting

1. **Release name:** "Land and Larder" is a placeholder in the style of "Foundations" and "Provisioning".
2. **Discord invite:** the Workshop page uses `discord.gg/HgFd69Sv83`, the 0.9 GitHub release `discord.gg/WVrSnfuW`; the
   drafts use the first. Check that it still works.
3. **Launcher text:** `short_description` in `.metadata/metadata.json` still holds the 0.8 description, cut off mid-word.
   A one-line replacement: *A food, land and population overhaul: stored food drives growth, arable land limits
   farms, harvests swing, and great rivers carry ships inland.*
4. **Release steps:** the release checklist in `AGENTS.md` (validation, merge into `main`, final sync, tag, release).
   `main` is at 0.9.1 and fast-forwards to `0.10`.
