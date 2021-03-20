#!/usr/bin/python3

#This is an Android service thing only!!
import hardline


loadedServices = hardline.loadUserServices(
                    hardline.user_services_dir)
# This is the android service
hardline.start(7009)
