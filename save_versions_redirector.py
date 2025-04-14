bl_info = {
    "name": "Save Versions Redirector",
    "blender": (2, 80, 0),
    "version": (1, 0, 0),
    "author": "ray34g",
    "category": "System",
    "description": "Redirects save versions to a centralized or custom folder and preserves time-based checkpoints.",
}

import bpy
from bpy.app.handlers import persistent
import os
import shutil
import hashlib
import time
import re

# ------------------------
# アドオン設定クラス
# ------------------------

class SaveVersionsRedirectorPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    save_directory: bpy.props.StringProperty(
        name="Backup Save Directory",
        description="Directory to save versioned backup files. Leave blank to use Blender's temporary path.",
        subtype='DIR_PATH',
        default=""
    )

    v2_minutes: bpy.props.IntProperty(name="v2 Threshold (minutes)", default=30, min=0)
    v3_minutes: bpy.props.IntProperty(name="v3 Threshold (minutes)", default=60, min=0)
    v4_minutes: bpy.props.IntProperty(name="v4 Threshold (minutes)", default=480, min=0)
    v5_minutes: bpy.props.IntProperty(name="v5 Threshold (minutes)", default=1440, min=0)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Save Location:")
        layout.prop(self, "save_directory")

        layout.separator()
        layout.label(text="Time-based versioning thresholds:")
        layout.prop(self, "v2_minutes")
        layout.prop(self, "v3_minutes")
        layout.prop(self, "v4_minutes")
        layout.prop(self, "v5_minutes")

# ------------------------
# ユーティリティ関数
# ------------------------

def get_unique_prefix(filepath):
    full_path = os.path.abspath(filepath)
    hashed = hashlib.sha1(full_path.encode("utf-8")).hexdigest()[:8]
    name = os.path.splitext(os.path.basename(filepath))[0]
    return f"{name}_{hashed}"

def get_versions_dir():
    prefs = bpy.context.preferences.addons[__name__].preferences
    if prefs.save_directory.strip():
        return os.path.abspath(bpy.path.abspath(prefs.save_directory))
    else:
        return os.path.join(
            bpy.context.preferences.filepaths.temporary_directory or bpy.app.tempdir,
            "versions"
        )

def get_version_path(versions_dir, prefix, v):
    return os.path.join(versions_dir, f"{prefix}_v{v}.blend")

def get_threshold_seconds_map(max_versions: int):
    prefs = bpy.context.preferences.addons[__name__].preferences
    thresholds = {
        1: 0,  # v1 は常時保存
        2: prefs.v2_minutes * 60,
        3: prefs.v3_minutes * 60,
        4: prefs.v4_minutes * 60,
        5: prefs.v5_minutes * 60,
    }

    v5_minutes = prefs.v5_minutes
    if v5_minutes > 0:
        for v in range(6, max_versions + 1):
            minutes = v5_minutes + v5_minutes * (v - 5)
            thresholds[v] = minutes * 60
    return thresholds

# ------------------------
# 保存処理
# ------------------------

@persistent
def move_backup_file(dummy):
    filepath = bpy.data.filepath
    if not filepath:
        return

    source_backup = filepath + "1"
    if not os.path.exists(source_backup):
        return

    max_versions = bpy.context.preferences.filepaths.save_version
    prefix = get_unique_prefix(filepath)
    versions_dir = get_versions_dir()
    os.makedirs(versions_dir, exist_ok=True)

    now = time.time()
    thresholds = get_threshold_seconds_map(max_versions)

    # 既存バージョン一覧取得
    version_files = []
    pattern = re.compile(rf"{re.escape(prefix)}_v(\d+)\.blend")
    for f in os.listdir(versions_dir):
        m = pattern.match(f)
        if m:
            version_files.append((int(m.group(1)), f))

    # max_versions を超えるバージョンを削除
    for version_num, fname in sorted(version_files, reverse=True):
        if version_num > max_versions:
            try:
                os.remove(os.path.join(versions_dir, fname))
                print(f"[Save Versions Redirector] Removed v{version_num} ({fname})")
            except Exception as e:
                print(f"[Save Versions Redirector] Failed to remove v{version_num}: {e}")

    # v1〜max_versions を処理
    for v in range(1, max_versions + 1):
        threshold = thresholds.get(v, 0)
        version_path = get_version_path(versions_dir, prefix, v)

        if not os.path.exists(version_path):
            shutil.copy2(source_backup, version_path)
            print(f"[Save Versions Redirector] Created v{v} → {version_path}")
            break
        else:
            last_modified = os.path.getmtime(version_path)
            if threshold == 0 or now - last_modified >= threshold:
                shutil.copy2(source_backup, version_path)
                print(f"[Save Versions Redirector] Updated v{v} → {version_path}")
                break
            else:
                print(f"[Save Versions Redirector] Skipped v{v} (not enough time elapsed)")

    try:
        os.remove(source_backup)
    except Exception as e:
        print(f"[Save Versions Redirector] Failed to remove .blend1: {e}")

# ------------------------
# 登録・解除
# ------------------------

def register():
    bpy.utils.register_class(SaveVersionsRedirectorPreferences)
    if move_backup_file not in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.append(move_backup_file)

def unregister():
    if move_backup_file in bpy.app.handlers.save_post:
        bpy.app.handlers.save_post.remove(move_backup_file)
    bpy.utils.unregister_class(SaveVersionsRedirectorPreferences)

if __name__ == "__main__":
    register()
