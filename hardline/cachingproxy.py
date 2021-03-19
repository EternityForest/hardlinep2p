# A simple HTTP proxy which does caching of requests.
# Inspired by: https://gist.github.com/bxt/5195500
# but updated for Python 3 and some additional sanity improvements:
# - shutil is used to serve files in a streaming manner, so the entire data is not loaded into memory.
# - the http request is written to a temp file and renamed on success
# - forward headers

import os
import traceback
import shutil
import time
import threading
import random

import shutil
import urllib.request
import socketserver
import http.server


def countDirSize(d):
    total_size = 0
    for path, dirs, files in os.walk(d):
        for f in files:
            fp = os.path.join(path, f)
            total_size += os.path.getsize(fp)
    return total_size


def deleteOldFiles(d, maxSize):
    "Delete the oldest in D until the whole cache is smaller than maxSize*0.75"
    total_size = countDirSize(d)
    if total_size < (maxSize):
        return

    listing = []

    for path, dirs, files in os.walk(d):
        for f in files:
            fp = os.path.join(path, f)
            listing.append((os.stat(fp).st_mtime, fp))

    listing.sort()

    for i in listing:
        # These are not cached files they are fully manual.
        if '@mako' in i[1] or '@data' in i[1]:
            continue
        total_size -= os.path.getsize(i[1])
        os.remove(i[1])

        # Use some hysteresis
        if total_size < (maxSize*0.75):
            break

    # Cleanup empty
    for path, dirs, files in os.walk(d):
        if not dirs or files:
            os.remove(path)

    return total_size


class CachingProxy():
    "Return an object that can be used as either a caching proxy or a plain static file server."

    def __init__(self, site, directory, maxAge=7*24*3600, downloadRateLimit=1200, maxSize=1024*1024*256, allowListing=False, dynamicContent=False):

        # Convert to int because we have to expect that the params will be supplied directly from an ini file parser.
        # And the user may have supplied blanks.

        # Calculate in 128kb blocks
        maxRequestsPerHour = int(downloadRateLimit or 1200)*8

        timePerBlock = 3600/maxRequestsPerHour

        maxAge = int(maxAge or 7*24*3600)
        maxSize = int(maxSize or 1024*1024*256)

        downloadQuotaHolder = [maxRequestsPerHour]
        downloadQuotaTimestamp = [time.time()]
        self.port = None

        try:
            from mako.lookup import TemplateLookup
            templateLookup = TemplateLookup([directory])
            self.templateLookup = templateLookup
        except ImportError as e:
            print("No mako support for dynamic content in cache files.")

        def makeListPage(p):
            s = "<html><body><ul>"

            for i in os.listdir(os.path.join(directory, p)):
                s += '<li><a href="'+i+"</a></li>"
            s += "</ul></body></html>"
            return s.encode()

        try:
            os.makedirs(directory)
        except:
            pass

        totalSize = [countDirSize(directory)]

        class CacheHandler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):

                cache_filename = self.path

                if cache_filename.startswith("/"):
                    cache_filename = cache_filename[1:]
                unquoted = cache_filename

                cache_filename = urllib.parse.quote(cache_filename)

                # Defensive programming because we may depend on @ files for special purposes.
                if '@' in cache_filename:
                    raise RuntimeError("This should not happen")

                # Very lightweight dynamic content support in the form of Mako templates.
                # Just enough for a tiny bit of custom stuff on top of a cached site to compensate
                # for the non-dynamicness.
                if dynamicContent:
                    makoName = unquoted.split("#")[0].split("?")[0]
                    makoName = makoName+"@mako"
                    if os.path.exists(os.path.join(directory, makoName)):
                        t = templateLookup.get_template(
                            makoName).render(path=self.path, __file__=makoName)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(t.encode())
                        return

                cache_filename = os.path.join(directory, cache_filename)

                if not os.path.exists(cache_filename):
                    # HTTP lets you access a dir and a file the same way.  Filesystems do not,
                    # So retrieved files need the special postfix to be sure they never collide with dirs.

                    # However, we also need to be compatible with manually-created directory structures which
                    # The user wants to serve exactly as-is.   To accomodate that we only do the posfixing IF the
                    # original one does not exist.
                    cache_filename = cache_filename+"@http"

                useCache = True
                # Approximately calculate how many download blocks are left in the quota

                def doQuotaCalc():
                    # Accumulate quota units up to the maximum allowed
                    downloadQuotaHolder[0] += min(((time.time()-downloadQuotaTimestamp[0])/3600)
                                                  * maxRequestsPerHour+maxRequestsPerHour, maxRequestsPerHour)
                    downloadQuotaTimestamp[0] = time.time()
                    return downloadQuotaHolder[0]

                if not os.path.exists(cache_filename):
                    useCache = False

                else:
                    age = time.time()-os.stat(cache_filename).st_mtime
                    if age > maxAge:
                        # If totally empty, we are in high load conditions,
                        # Use cache even if it is old, to prioritize getting stuff we don't have already.
                        if doQuotaCalc():
                            useCache = False

                doQuotaCalc()

                if not useCache:
                    if site:

                        try:
                            os.makedirs(os.path.dirname(cache_filename))
                        except:
                            pass
                        with open(cache_filename + ".temp", "wb") as output:
                            req = urllib.request.Request(site + self.path)
                            # copy request headers
                            for k in self.headers:
                                if k not in ["Host"]:
                                    req.add_header(k, self.headers[k])
                            try:
                                with urllib.request.urlopen(req) as resp:
                                    self.send_response(200)
                                    self.end_headers()

                                    for i in range(256000):
                                        # Partial blocks count for one whole block.
                                        d = resp.read(128*1024)
                                        if not d:
                                            break

                                        totalSize[0] += len(d)

                                        downloadQuotaHolder[0] -= 1
                                        for i in range(1000):
                                            if doQuotaCalc():
                                                break
                                            time.sleep(0.1)

                                        if not downloadQuotaHolder[0]:
                                            time.sleep(timePerBlock)

                                        # No write the too big
                                        # TODO avoid this in the first place.
                                        if totalSize[0] < maxSize:
                                            output.write(d)

                                        self.wfile.write(d)

                                os.rename(cache_filename +
                                          ".temp", cache_filename)

                                if totalSize[0] > maxSize:
                                    totalSize[0] = deleteOldFiles(directory)

                                return

                            except urllib.error.HTTPError as err:
                                self.send_response(err.code)
                                self.end_headers()
                                return

                    else:
                        self.send_redsponse(404)
                        self.end_heaers()
                        return

                if os.path.isfile(cache_filename):
                    with open(cache_filename, "rb") as cached:
                        self.send_response(200)
                        self.end_headers()
                        shutil.copyfileobj(cached, self.wfile)
                else:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(makeListPage(cache_filename))

        def f():
            for i in range(128):
                p = 50000 + int(random.random()*8192)
                try:
                    with socketserver.TCPServer(("localhost", p), CacheHandler) as httpd:
                        self.port = p
                        self.server = httpd
                        httpd.serve_forever()
                except:
                    print(traceback.format_exc())

            self.port = None

        self.thread = threading.Thread(target=f, daemon=True)
        self.thread.start()
