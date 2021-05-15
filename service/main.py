#!/usr/bin/python3

#This is an Android service thing only!!
import hardline
import hardline.daemonconfig

loadedServices = hardline.daemonconfig.loadUserServices(
                    hardline.directories.user_services_dir)


hardline.daemonconfig.loadDrayerServerConfig()
for i in hardline.daemonconfig.loadUserDatabases(None):
    print("Android background service loading: "+str(i))

# This is the android service
hardline.start(7009)

from jnius import autoclass
PythonService = autoclass('org.kivy.android.PythonService')
PythonService.mService.setAutoRestartService(True)