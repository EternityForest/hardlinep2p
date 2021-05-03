#!/usr/bin/python3

#This is an Android service thing only!!
import hardline
import hardline.daemonconfig

loadedServices = hardline.daemonconfig.loadUserServices(
                    hardline.directories.user_services_dir)
hardline.daemonconfig.loadDrayerServerConfig()
# This is the android service
hardline.start(7009)
db= hardline.daemonconfig.loadUserDatabases(None)
