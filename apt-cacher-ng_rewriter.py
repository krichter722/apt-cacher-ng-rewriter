#!/usr/bin/python

#    A squid rewrite helper to rewrite URLs of requests to Ubuntu package
#    repositories to go to apt-cacher-ng.
#    Copyright (C) 2016 Karl-Philipp Richter (krichter@posteo.de)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import re
import logging
import plac
import urlparse
import traceback

logger = logging.getLogger(__name__)
logger_formatter = logging.Formatter('%(asctime)s:%(message)s')

# Adding a new repository requires:
# - defining a __match_[name]__ function taking the processed URL as parameter
# - adding the defined match function to the check chain below
# - add configuration files to `apt-cacher-ng` (not yet sure about correct way
# because the default configuration file is documentation-free)

# result code string according to http://wiki.squid-cache.org/Features/Redirectors
RESULT_ERR = "ERR" # indicates "Success. No change for this URL."
RESULT_OK = "OK" # indicates "Success. A new URL is presented"
RESULT_BH = "BH" # indicates "Failure. The helper encountered a problem."

# unclear how to handle access from within function in function (should work to, but doesn't)
class ResultObject(object):
    def __init__(self, url_new, result):
        self.url_new = url_new
        self.result = result

@plac.annotations(log_file_path=("Path to a file used for logging. Make sure the file exists and is writable by the user invoking this squid helper", "option"),
    debug=("Enables debug messages in logging", "flag"),
    apt_cacher_ng_url=("The URL of the apt-cacher-ng instance to use", "option"))
def apt_cacher_ng_rewriter(log_file_path="/usr/local/squid/var/log/apt-cacher-ng_rewriter.log", debug=False, apt_cacher_ng_url="http://192.168.178.20:3142"):
    if log_file_path == None:
        logger_handler = logging.StreamHandler(stream=sys.stderr) # must not log to stdout because it's used for communication with squid
    else:
        logger_handler = logging.FileHandler(log_file_path)
    if debug is True:
        logger_handler.setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    else:
        logger_handler.setLevel(logging.INFO)
        logger.setLevel(logging.INFO)
    logger_handler.setFormatter(logger_formatter)
    logger.addHandler(logger_handler)

    logger.debug("rewrite helper 'apt-cacher-ng_rewriter.py' started")
    def __rewrite_url__(url, tail, repo_name=None):
        """At some point it became necessary to use the repo_name in the redirection URL which wasn't necessary before (reason unclear)"""
        urlsplit_result = urlparse.urlsplit(url)
        if repo_name == None:
            repo_name = urlsplit_result.netloc
        ret_value = "%s/%s%s" % (apt_cacher_ng_url.strip("/"), # use strip to ensure that exactly one / is present
             repo_name,
             tail, # includes leading /
             )
        return ret_value
    # internal implementation notes:
    # - since there's often a leading regular expression which contains a suffix (like `/ubuntu` in `http://(.*)archive.ubuntu.com/ubuntu/(pool|dists).*`) urlsplit_result.path can't be used, but tail argument must be passed instread
    # - `tail` expects a leading slash in order to allow easy usage of URL pathes (if ever used) which have leading `/` by definition

    def __read_line__():
        logger.debug("reading new line")
        line = sys.stdin.readline() # EOF is indicated by returning ""
        logger.debug("new line '%s' read" % (line,))
        return line
    result_object = ResultObject(None, None)
    try:
        line = __read_line__()
        while line != "":
            # channel-ID and kv-pairs seem to be optional
            line_split = line.split(" ")
            # if a channel-ID is passed it is an integer<ref>http://www.squid-cache.org/Doc/config/url_rewrite_program/</ref>
            try:
                id = str(int(line_split[0]))
                url = line_split[1].strip()
            except ValueError:
                id = ""
                url = line_split[0].strip()

            def __match_ubuntu_archive__(url):
                match = re.search("^http://(([^/]*)archive.ubuntu.com/ubuntu/(?P<tail>.*.deb$))", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="ubuntu", # needs the shortcuts specified in apt-cacher-ng configuration (unclear why)
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False
            def __match_ubuntu_ddebs__(url):
                match = re.search("^http://ddebs.ubuntu.com/(?P<tail>.*.d?deb$)", url)
                    # downloads `ddeb` packages (instead of `deb` packages)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="ddebs.ubuntu.com",
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False
            def __match_ubuntu_security__(url):
                match = re.search("^http://(security.ubuntu.com/ubuntu/(?P<tail>.*.deb$))", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="ubuntu-security",
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False
            def __match_ubuntu_ports__(url):
                match = re.search("^http://ports.ubuntu.com/ubuntu-ports/(?P<tail>.*.u?deb$)", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="ubuntu-ports",
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False
            def __match_debian__(url):
                """handles both special archive.debian.org (for archived releases) and all mirrors of supported releases"""
                match = re.search("^http://archive.debian.org/debian/(?P<tail>.*.deb$)", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="archive.debian.org/debian",
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                match = re.search("^http://(([^/]*).debian.org/debian/(?P<tail>.*.deb$))", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="debian",
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False
            def __match_ubuntu_ppas__(url):
                match = re.search("^http://(ppa.launchpad.net/(?P<user>[^/]+)/(?P<name>[^/]+)/ubuntu/(?P<tail>.*.deb$))", url)
                if match != None:
                    try:
                        tail = "/"+match.group("tail")
                        user = match.group("user")
                        name = match.group("name")
                    except IndexError:
                        raise RuntimeError("The unexpected exception '%s' occured which must have resulted for malious URL input" % (str(ex),))
                    url_new = __rewrite_url__(url,
                        repo_name="ppa.launchpad.net/%s/%s/ubuntu" % (user, name,),
                        tail=tail)
                    logger.info("rewriting to '%s'" % (url_new,))
                    result = RESULT_OK
                    result_object.url_new = url_new
                    result_object.result = result
                    return True
                return False

            logger.info("id=%s; url=%s" % (id, url))
            if url.startswith(apt_cacher_ng_url):
                logger.info("skipping URL starting with apt-cacher-ng URL")
                result_object.url_new = url
                result_object.result = RESULT_ERR
            elif url.endswith(".gpg") or url.endswith("ReleaseAnnouncement") or url.endswith("InRelease"): # unclear whether caching Sources.bz2 and Packages.gz might be a problem (cache until a problem appears)
                logger.info("skipping URL ending with '.gpg' or 'ReleaseAnnouncement'")
                result_object.url_new = url
                result_object.result = RESULT_ERR
            elif __match_ubuntu_archive__(url):
                pass
            elif __match_ubuntu_ddebs__(url):
                pass
            elif __match_ubuntu_security__(url):
                pass
            elif __match_ubuntu_ports__(url):
                pass
            elif __match_debian__(url):
                pass
            elif __match_ubuntu_ppas__(url):
                pass
            else:
                logger.debug("skipping line '%s'" % (line,))
                result_object.url_new = url
                result_object.result = RESULT_ERR
            def __kv_pairs__():
                if result_object.result == RESULT_ERR:
                    return result_object.url_new #""
                return 'rewrite-url="%s"' % (result_object.url_new,)
            if result_object.result == RESULT_ERR:
                reply = ""
            else:
                reply = ("%s %s %s" % (id, result_object.result, __kv_pairs__())).strip() # file.writelines doesn't add newline characters
            logger.debug("replying '%s'" % (reply,))
            sys.stdout.write(reply+"\n") # unclear whether URL is specified as forth attribute like in http://wiki.squid-cache.org/Features/Redirectors or in rewrite-url= key as in http://www.squid-cache.org/Doc/config/url_rewrite_program/
            sys.stdout.flush()
            line = __read_line__()
        logger.debug("rewrite helper 'apt-cacher-ng_rewriter.py' finished")
    except Exception as ex:
        logger.error("Exception '%s' occured, replying 'BH' result to squid" % (traceback.format_exc(ex),))
        sys.stdout.write("%s %s\n" % (id, RESULT_BH)) # file.writelines doesn't add newline characters
            # if id isn't assigned the program will crash which is fine because squid must have sent nonsense
        sys.stdout.flush()

if __name__ == "__main__":
    plac.call(apt_cacher_ng_rewriter)
