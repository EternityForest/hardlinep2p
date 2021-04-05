#!/usr/bin/python3

#This is an Android service thing only!!
import hardline


loadedServices = hardline.loadUserServices(
                    hardline.user_services_dir)
hardline.loadDrayerServerConfig()
# This is the android service
hardline.start(7009)
db= hardline.loadUserDatabases(None)
