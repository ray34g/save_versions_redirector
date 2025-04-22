# Save Versions Redirector

Blender add‑on that keeps a rolling set of automatic backups for the current `.blend` file.

* **latest**  – snapshot of the most recent save
* **prev1/prev2/…**  – older checkpoints that are only overwritten when they exceed a user‑defined age

The add‑on lets you pick a common backup folder and fine‑tune how frequently each checkpoint may be replaced.

---

## Features

| Feature | Description |
|---------|-------------|
| Centralised storage | Redirects Blender’s auto‑generated `*.blend1` files to a single folder (local or custom path) |
| Rolling backups | Renames files to `latest`, `prev1`, `prev2`, … instead of cryptic version numbers |
| Age thresholds | Each slot can have its own *minimum age* (minutes) before it may be overwritten |
| Hash‑based prefix | Prevents collisions between files with the same name in different folders |
| Respect Save Versions | The count in **Edit ▶ Preferences ▶ File Paths ▶ Save Versions** limits the maximum number of backups |

---

## Installation

1. Open **Blender ▶ Edit ▶ Preferences ▶ Add‑ons ▶ Install…**  
   Select the `save_versions_redirector.py` (or a ZIP containing it) and enable the add‑on.
2. (Optional) Set a *Backup Save Directory* in the add‑on preferences.  
   If left blank, Blender’s temp folder is used.
3. Save any `.blend` file – backups will now appear in the chosen folder.

---

## Preferences

| Option | Default | What it does |
|--------|---------|--------------|
| **Backup Save Directory** | *empty* | Target folder for all backup files |
| **prev1 Threshold (min)** | 30 | *prev1* is replaced only if it is at least 30 minutes old |
| **prev2 Threshold (min)** | 60 | Same rule for *prev2* |
| **prev3 Threshold (min)** | 480 *(8 h)* | Same rule for *prev3* |
| **prev4 Threshold (min)** | 1440 *(1 d)* | Same rule for *prev4* |

> **Tip ·** Additional slots beyond *prev4* inherit an expanded threshold (prev4 + n × prev4).

---

## How it works (quick flow)

1. Blender saves a backup `yourfile.blend1`.
2. The handler:
   * Copies it to **latest**.
   * Scans *prev1 … prevN* to find the first slot that is either empty *or* older than its threshold.
   * If that slot already exists and is old enough, every older file is shifted back one position to make space.
   * Places a fresh copy into the eligible slot.
3. Anything beyond **Save Versions** is deleted.
4. The original `.blend1` file is removed to avoid clutter.

---

## Example output

```
scene_95ab38c0_latest.blend   ← most recent save
scene_95ab38c0_prev1.blend    ← ≥ 30 min old
scene_95ab38c0_prev2.blend    ← ≥ 60 min old
```

When you save repeatedly within 30 minutes, only **latest** changes. Once 30 minutes pass, *prev1* is shifted to *prev2* and the new save becomes *prev1*.

---

## Customisation ideas

* Increase *Save Versions* to keep more history (slots appear as *prev5*, *prev6*, …).
* Set one of the thresholds to 0 to force overwriting on every save.
* Sync the backup directory to cloud storage for off‑site safety.

---

## Known limitations

* Backups are created only on manual **File ▶ Save** or autosave events that generate `.blend1`.
* Extremely long filenames may hit OS path‑length limits.
* The add‑on does not currently restore files; you must open the desired backup manually.

---

## Changelog (excerpt)

| Version | Highlights |
|---------|------------|
| 1.7 | Switched to `latest/prevN` naming & renamed preferences to `prevN_minutes` |
| 1.6 | Added custom thresholds, improved clean‑up |
| 1.0 | Initial release |

---

## License

This add‑on is released under the MIT License. See `LICENSE` for details.

