#! /usr/local/bin/python2.7
import util

def main():
    util.poll_for_services_available("localhost", None, timeout=1200)

if __name__ == '__main__':
    main()