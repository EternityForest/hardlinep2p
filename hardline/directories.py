import os, shutil, sys,traceback
try:
    from android.storage import app_storage_path
    settings_path = app_storage_path()
except:
    settings_path = os.path.expanduser('~/.hardlinep2p/')
    drayerDB_root = os.path.expanduser('~/.hardlinep2p/drayerdb')

try:
    from jnius import autoclass, cast
    PythonActivity = autoclass('org.kivy.android.PythonActivity')

    if PythonActivity and PythonActivity.mActivity:
        context = cast('android.content.Context', PythonActivity.mActivity)
    else:
        PythonActivity = autoclass('org.kivy.android.PythonService')
        context = cast('android.content.Context', PythonActivity.mService)

    Environment = autoclass('android.os.Environment')

    internalDir = context.getExternalFilesDir(None).getAbsolutePath()
    print("Internal App Dir", internalDir)
    r = internalDir

    for i in context.getExternalFilesDirs(None):
        print("Found storage dir:",i)
        p = i.getAbsolutePath()
        if p.startswith("/sdcard") or p.startswith("/storage/sdcard0/") or (p.startswith("/storage/") and not p.startswith("/storage/emulated/")):
            print("Found External SD")
            r= p
            break

    user_services_dir = os.path.join(r, "services")
    proxy_cache_root = os.path.join(r, "proxycache")
    drayerDB_root = os.path.join(r, "drayerdb")

    #First time copy-over to new SD card from internal storage.
    import shutil
    if not os.path.exists(proxy_cache_root) and os.path.exists(os.path.join(internalDir, "proxycache")):
        print("Copying proxy cache to external SD")
        shutil.copytree(os.path.join(internalDir, "proxycache"), proxy_cache_root)

    if not os.path.exists(user_services_dir) and os.path.exists(os.path.join(internalDir, "services")):
        print("Copying service files to external SD")
        shutil.copytree(os.path.join(internalDir, "services"), user_services_dir)

    if not os.path.exists(drayerDB_root) and os.path.exists(os.path.join(internalDir, "drayerdb")):
        print("Copying service files to external SD")
        shutil.copytree(os.path.join(internalDir, "drayerdb"), drayerDB_root)

    print(user_services_dir)

except:
    print(traceback.format_exc())
    user_services_dir = os.path.expanduser('~/.hardlinep2p/services/')
    proxy_cache_root = os.path.expanduser('~/.hardlinep2p/proxycache/')



try:
    os.makedirs(os.path.expanduser(settings_path))
except Exception:
    pass

DB_PATH = os.path.join(os.path.expanduser(settings_path), "peers.db")
