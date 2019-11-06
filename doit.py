#! /usr/bin/env python

import datetime
import holidays
import math
import openevse
import sqlite3
import time

import pdb

long_delay = 30
short_delay = 1

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

def createDbConnection(db_file):
    try:
        return sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(e)

def createTable(db, sql):
    try:
        cursor = db.cursor()
        cursor.execute(sql)
        db.commit()
    except sqlite3.Error as e:
        print(e)

def weekend(localtime):
    return localtime.weekday() >= 5

def offPeakHour(localtime):
    hour = localtime.hour

    if hour < 8 or (hour >= 10 and hour < 15) or hour >= 20:
        #Summer or winter, these hours are off - peak
        return True

    month = localtime.month
    if month > 4 and month < 10 and hour < 15:
        #Summer before 3 PM
        return True

    return False

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

def cheapPower(localtime):
    print "Offpeakhour", offPeakHour(localtime)
    print "Weekend", weekend(localtime)
    print "Holiday", powerHoliday(localtime)

    return (offPeakHour(localtime) or
            weekend(localtime) or
            powerHoliday(localtime))

createHistoryTableSql = """
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY,
        time TIMESTAMP DEFAULT (strftime('%s', 'now')),
        status TEXT,
        sessionTime INTEGER,
        sessionWh REAL,
        lifeWh INTEGER,
        currentAmps REAL,
        ampLimit INTEGER,
        voltage INTEGER DEFAULT 247,
        temperature REAL
    );
"""

insertSql  = """
    INSERT INTO history(
        status,
        sessionTime,
        sessionWh,
        lifeWh,
        currentAmps,
        ampLimit,
        temperature
    ) VALUES (?, ?, ?, ?, ?, ?, ?);
"""

def updateIfNeeded(name, evse, cheap_power, db):
    try:
        status = evse.status()
        ampLimit = evse.current_capacity()
        currentAmps = evse.charging_current_and_voltage()['amps']
        temperature = evse.temperature()['tmp007temp'];
        sessionTime = 0
        sessionWh = 0
        if status == 'charging':
            try:
                elapsed = evse.elapsed()
                sessionTime = elapsed['seconds']
                sessionWh = elapsed['Wh']
            except NotCharging:
                pass
        lifeWh = evse.accumulated_wh()
    except:
        print "Unable to communicate with %s!" % name
        return short_delay

    if db is not None:
        cursor = db.cursor()
        cursor.execute(insertSql,
                       (status, sessionTime, sessionWh, lifeWh, currentAmps,
                        ampLimit, temperature))
        db.commit()

    print name + " is " + status
    if not cheap_power and status != 'sleeping':
        print "Wasting money!  Disabling " + name + " charger!"
        evse.status('sleep')
        return short_delay
    elif cheap_power and status == 'sleeping':
        print "Wasting charging opportunity!  Enabling " + name + " charger!"
        evse.status('enable')
        return short_delay
    else:
        return long_delay

if __name__ == "__main__":
    tesla = openevse.WifiOpenEVSE('192.168.86.177', 'admin', 'hikingisfun')
    leaf = openevse.WifiOpenEVSE('192.168.86.178', 'admin', 'hikingisfun')

    teslaDb = createDbConnection("db/tesla.db");
    createTable(teslaDb, createHistoryTableSql);
    leafDb = createDbConnection("db/leaf.db");
    createTable(leafDb, createHistoryTableSql);

    while True:
        localtime = datetime.datetime.now()
        cheap_power = cheapPower(localtime)

#        pdb.set_trace()

        print localtime
        if cheap_power:
            print "Power is cheap"
        else:
            print "Power is expensive"

        tesla_delay = updateIfNeeded("Tesla", tesla, cheap_power, teslaDb)
        leaf_delay = updateIfNeeded("Leaf", leaf, cheap_power, leafDb)
        print

        minute_delay = long_delay
        if localtime.minute == 59:
            minute_delay = 61 - localtime.second

        to_wait = min(tesla_delay, leaf_delay, minute_delay)

        print "waiting " + str(to_wait)
        print

        time.sleep(to_wait)

    teslaDb.close()
    leafDb.close()
