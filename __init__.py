bl_info = {
    "name": "Save Versions Redirector",
    "blender": (4, 2, 0),
    "version": (1, 3, 0),
    "author": "ray34g",
    "category": "System",
    "description": "Keeps a rolling set of backups: 'latest', 'prev1', 'prev2' … . Each slot has its own minimum‑age threshold before being overwritten."
}

import bpy
from bpy.app.handlers import persistent
import os
import shutil
import hashlib
import time
import re
import threading

# -----------------------------------------------------------------------------
# Preferences
# -----------------------------------------------------------------------------

class SaveVersionsRedirectorPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    save_directory: bpy.props.StringProperty(
        name="Backup Save Directory",
        description="Leave blank to use Blender's temporary path.",
        subtype='DIR_PATH',
        default=""
    )

    # Overwrite‑age thresholds (minutes) for each slot
    prev1_minutes: bpy.props.IntProperty(name="prev1 Threshold (min)", default=30, min=0)
    prev2_minutes: bpy.props.IntProperty(name="prev2 Threshold (min)", default=60, min=0)
    prev3_minutes: bpy.props.IntProperty(name="prev3 Threshold (min)", default=480, min=0)
    prev4_minutes: bpy.props.IntProperty(name="prev4 Threshold (min)", default=1440, min=0)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "save_directory")
        layout.separator()
        layout.label(text="Overwrite thresholds (minutes):")
        for a in (
            "prev1_minutes",
            "prev2_minutes",
            "prev3_minutes",
            "prev4_minutes",
        ):
            layout.prop(self, a)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _hash_name(fp: str) -> str:
    base = os.path.splitext(os.path.basename(fp))[0]
    return f"{base}_{hashlib.sha1(os.path.abspath(fp).encode()).hexdigest()[:8]}"


def _versions_dir() -> str:
    prefs = bpy.context.preferences.addons[__name__].preferences
    if prefs.save_directory.strip():
        return os.path.abspath(bpy.path.abspath(prefs.save_directory))
    tmp = bpy.context.preferences.filepaths.temporary_directory or bpy.app.tempdir
    return os.path.join(tmp, "versions")


def _ver(root: str, prefix: str, v: int) -> str:
    label = "latest" if v == 1 else f"prev{v-1}"
    return os.path.join(root, f"{prefix}_{label}.blend")


def _thresholds(max_v: int):
    """Return a dict {slot_index: seconds_before_overwrite}."""
    p = bpy.context.preferences.addons[__name__].preferences
    base = [0, p.prev1_minutes, p.prev2_minutes, p.prev3_minutes, p.prev4_minutes]
    thr = {i + 1: m * 60 for i, m in enumerate(base) if i + 1 <= max_v}
    # Extend linearly using prev4 spacing
    if p.prev4_minutes > 0:
        for v in range(6, max_v + 1):
            thr[v] = (p.prev4_minutes + p.prev4_minutes * (v - 5)) * 60
    return thr


def _rotate(prefix: str, root: str, max_v: int, start: int):
    """Shift existing slots backward to make room for a new file in *start*."""
    overflow = _ver(root, prefix, max_v)
    if os.path.exists(overflow):
        os.remove(overflow)
    for v in range(max_v - 1, start - 1, -1):
        src = _ver(root, prefix, v)
        dst = _ver(root, prefix, v + 1)
        if os.path.exists(src):
            shutil.move(src, dst)


def _find_slot(prefix: str, root: str, max_v: int, thresholds: dict, now: float):
    """Return (slot_index, need_rotate) or (None, False) if no slot available."""
    for v in range(2, max_v + 1):
        path = _ver(root, prefix, v)
        thresh = thresholds.get(v, 0)
        if not os.path.exists(path):
            return v, False
        if thresh == 0 or now - os.path.getmtime(path) >= thresh:
            return v, True
    return None, False


def _notify(message: str):
    def draw(self, _context):
        self.layout.label(text=message)
    bpy.context.window_manager.popup_menu(draw, title="Save Versions", icon='INFO')


def _copy_async(src: str, dst: str, *, notify: bool = True):
    """Copy *src* to *dst* in a daemon thread, then (optionally) show pop‑up."""
    def task():
        try:
            shutil.copy2(src, dst)
            if notify:
                bpy.app.timers.register(lambda: _notify(f"Copied: {os.path.basename(dst)}"), first_interval=0.0)
        except Exception as e:
            bpy.app.timers.register(lambda: _notify(f"Copy failed: {e}"), first_interval=0.0)
    threading.Thread(target=task, daemon=True).start()


def _safe_remove(path: str, *, retries: int = 5, delay: float = 2.0):
    """Attempt to remove *path*; retry a few times in case it is still in use."""
    def attempt(remaining):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            if remaining > 0:
                bpy.app.timers.register(lambda: attempt(remaining - 1), first_interval=delay)
    bpy.app.timers.register(lambda: attempt(retries), first_interval=delay)

# -----------------------------------------------------------------------------
# Handler
# -----------------------------------------------------------------------------

@persistent
def save_versions_post(_):
    fp = bpy.data.filepath
    if not fp:
        return

    # Backup created by Blender when Save Preferences > File > Save Versions > 1+
    src_bak = fp + "1"
    if not os.path.exists(src_bak):
        return

    max_v = max(bpy.context.preferences.filepaths.save_version, 1)
    root = _versions_dir()
    os.makedirs(root, exist_ok=True)
    prefix = _hash_name(fp)

    now = time.time()
    thresholds = _thresholds(max_v)

    # Determine destination slot and perform rotation if necessary
    slot, need_rot = _find_slot(prefix, root, max_v, thresholds, now)
    if slot is not None:
        if need_rot:
            _rotate(prefix, root, max_v, slot)
        _copy_async(src_bak, _ver(root, prefix, slot))

    # Always refresh the "latest" slot
    _copy_async(src_bak, _ver(root, prefix, 1))

    # Purge old files beyond *max_v*
    pat = re.compile(rf"{re.escape(prefix)}_(latest|prev(\d+))\.blend")
    for f in os.listdir(root):
        m = pat.match(f)
        if not m:
            continue
        idx = 1 if m.group(1) == "latest" else int(m.group(2)) + 1
        if idx > max_v:
            try:
                os.remove(os.path.join(root, f))
            except Exception:
                pass

    # Remove Blender‑generated backup after asynchronous copies finish
    _safe_remove(src_bak)

# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

def register():
    bpy.utils.register_class(SaveVersionsRedirectorPreferences)
    if save_versions_post not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(save_versions_post)


def unregister():
    if save_versions_post in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(save_versions_post)
    bpy.utils.unregister_class(SaveVersionsRedirectorPreferences)


if __name__ == "__main__":
    register()
