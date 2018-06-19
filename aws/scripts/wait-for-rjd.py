#! /usr/local/bin/python2.7
import util
import logger
import urllib3

def main():
    util.kill_ssl_warnings(logger, urllib3)
    util.poll_for_services_available("localhost", None, timeout=1200)

if __name__ == '__main__':
    main()