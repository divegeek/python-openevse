#! /usr/bin/env python

import datetime
import holidays
import math
import openevse
import sqlite3
import time

import pdb

long_delay = 3600
short_delay = 5

holidayObj = holidays.US(state = 'UT')
includedHolidays = [
    "New Year's Day",
    "Washington's Birthday",
    "Memorial Day",
    "Independence Day",
    "Pioneer Day",
    "Labor Day",
    "Christmas Day",
]

def weekend(localtime):
    return localtime.weekday() >= 5
    #return False

def getHoliday(localtime):
    return holidayObj.get(localtime.strftime('%Y-%m-%d'));

def powerHoliday(localtime):
    if getHoliday(localtime) in includedHolidays:
        return True

    one_day = datetime.timedelta(days = 1)
    if localtime.weekday() == 4:
        #It's Friday.  If Saturday is a holiday, then today is a power holiday.
        tomorrow = localtime + one_day
        return getHoliday(tomorrow) in includedHolidays
    elif localtime.weekday() == 0:
        #It's Monday.  If Sunday is a holiday, then today is a power holiday.
        yesterday = localtime - one_day
        return getHoliday(yesterday) in includedHolidays

    return False

# Return next off-peak interval in the form of (start hour, start min,
# end hour, end min).
def nextOffPeakInterval(localtime):
    hour = localtime.hour

    # Default the charge interval to from 8:01 PM to 2:59 PM, so we
    # won't charge from 3:00 PM to 8:00 PM
    default = 20, 1, 14, 59

    month = localtime.month
    # On winter mornings, though, we instead use 10:01 AM to 7:59 AM,
    # so we won't charge from 8:00 AM to 10:00 AM.  This is obviously
    # wrong when 3:00 PM rolls around, but we should have checked
    # again and changed to the default interval by then.
    if hour < 10 and (month < 5 or month > 9):
        return 10, 1, 7, 59

    return default

def update(name, evse, chargeTimer):
    try:
        print "%s is %s" % (name, evse.status())
        evse_time = evse.time()
        sys_time = datetime.datetime.now()
        diff = abs(sys_time - evse_time).total_seconds()
        if diff > 10:
            print "%s clock is off by %d seconds. Updating" % (name, diff)
            evse.time(sys_time)

        starthour, startmin, endhour, endmin = chargeTimer
        evse.timer(starthour, startmin, endhour, endmin)

    except Exception as err:
        print "Unable to communicate with %s!" % name
        print err
        return short_delay

    return long_delay

if __name__ == "__main__":
    tesla = openevse.WifiOpenEVSE('192.168.86.177', 'admin', 'hikingisfun')
    leaf = openevse.WifiOpenEVSE('192.168.86.178', 'admin', 'hikingisfun')

    while True:
        localtime = datetime.datetime.now()
        print "Time: ", localtime

        chargeTimer = 0, 0, 0, 0
        if weekend(localtime):
            print "This is a weekend, power is cheap!"
        elif powerHoliday(localtime):
            print "This is a holiday, power is cheap!"
        else:
            chargeTimer = nextOffPeakInterval(localtime)

        print "Charge interval", chargeTimer

        tesla_delay = update("Tesla", tesla, chargeTimer)
        leaf_delay = update("Leaf", leaf, chargeTimer)

        to_wait = min(tesla_delay, leaf_delay, long_delay)

        print "waiting " + str(to_wait)
        print

        time.sleep(to_wait)

    teslaDb.close()
    leafDb.close()
