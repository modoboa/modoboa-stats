#!/usr/bin/env python
# coding: utf-8
"""
Postfix log parser.

This scripts parses a log file produced by postfix (or using the same
format). It looks for predefined events and build statistics about
their occurence rate.

At the, somes default graphics are generated using the grapher module.
(see grapher.py)

Predefined events are:
 * Per domain sent/received messages,
 * Per domain received bad messages (bounced, reject for now),
 * Per domain sent/received traffics size,
 * Global consolidation of all previous events.

"""

import os
import re
import string
import sys
import time

import rrdtool

from django.core.management.base import BaseCommand

from modoboa.admin.models import Domain
from modoboa.parameters import tools as param_tools

from ...lib import date_to_timestamp
from ...modo_extension import Stats


rrdstep = 60
xpoints = 540
points_per_sample = 3
variables = ["sent", "recv", "bounced", "reject", "spam", "virus",
             "size_sent", "size_recv"]


class LogParser(object):

    def __init__(self, options, workdir, year=None):
        """Constructor
        """
        self.logfile = options["logfile"]
        self.debug = options["debug"]
        self.verbose = options["verbose"]
        try:
            self.f = open(self.logfile)
        except IOError as errno:
            self._dprint("%s" % errno)
            sys.exit(1)
        self.workdir = workdir
        self.__year = year
        self.cfs = ['AVERAGE', 'MAX']

        curtime = time.localtime()
        if not self.__year:
            self.__year = curtime.tm_year
        self.curmonth = curtime.tm_mon

        self.data = {}
        self.domains = []
        self._load_domain_list()
        self.data["global"] = {}

        self.workdict = {}
        self.lupdates = {}
        self._s_date_expr = \
            re.compile(
                r"(?P<month>\w+)\s+(?P<day>\d+)\s+(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)(?P<eol>.*)")
        self._hp_date_expr = \
            re.compile(
                r"(?P<year>\d+)-(?P<month>\d+)-(?P<day>\d+)T(?P<hour>\d+):(?P<min>\d+):(?P<sec>\d+)\.\d+\+\d+:\d+(?P<eol>.*)")
        self.date_expr = None
        self.line_expr = \
            re.compile(r"\s+([-\w\.]+)\s+(\w+)/?\w*[[](\d+)[]]:\s+(.*)")

        self._virus_sigs = []
        self._spam_sigs = []
        spam_pattern = ""
        spam_tool = param_tools.get_global_parameter(
            "spam_detection", app="modoboa_stats")
        if spam_tool == "amavis":
            spam_pattern = \
                r"(?P<result>INFECTED|SPAM|SPAMMY) .* <[^>]+> -> <[^@]+@(?P<domain>[^>]+)>.*"
            self._virus_sigs = ["INFECTED"]
            self._spam_sigs = ["SPAM", "SPAMMY"]
        elif spam_tool == "rmilter":
            spam_pattern = \
                r"<[0-9a-f]{10}>; msg done: .*; from: <[^>]+>; rcpt: <[^@]+@(?P<domain>[^>]+)>.*; spam scan: (?P<result>[^;]+); virus scan: .*$"
            self._virus_sigs = []  # Can't be detected from one line.
            self._spam_sigs = ["rejected, action: reject", "action: add header"]
        self._spam_detect_expr = re.compile(spam_pattern)

        self._id_expr = re.compile(r"(\w+): (.*)")
        self._prev_se = -1
        self._prev_mi = -1
        self._prev_ho = -1
        self.cur_t = 0

    def _load_domain_list(self):
        """Load the list of allowed domains."""
        for dom in Domain.objects.all():
            self.domains += [str(dom.name)]
            self.data[str(dom.name)] = {}

    def _dprint(self, msg):
        """Print a debug message if required.

        :param str msg: debug message
        """
        if not self.debug:
            return
        print msg

    def _parse_date(self, line):
        """Try to match a date inside :kw:`line` and to convert it to
        a timestamp.

        We try different date format until we find valid one. We then
        store it for future use.

        :param str line: a log entry
        :return: the remaining part of the line or None
        """
        match = None
        if self.date_expr is None:
            for expr in [self._s_date_expr, self._hp_date_expr]:
                match = expr.match(line)
                if match is not None:
                    self.date_expr = expr
                    break
        else:
            match = self.date_expr.match(line)
        if match is None:
            return None
        ho = match.group("hour")
        mi = match.group("min")
        se = match.group("sec")
        se = int(int(se) / rrdstep)  # rrd step is one-minute => se = 0
        if self._prev_se != se or self._prev_mi != mi or self._prev_ho != ho:
            mo = match.group("month")
            da = match.group("day")
            try:
                ye = match.group("year")
            except IndexError:
                ye = self.year(mo)
            self.cur_t = date_to_timestamp([ye, mo, da, ho, mi, se])
            self.cur_t = self.cur_t - self.cur_t % rrdstep
            self._prev_mi = mi
            self._prev_ho = ho
            self._prev_se = se
        return match.group('eol')

    def init_rrd(self, fname, m):
        """init_rrd

        Set-up Data Sources (DS)
        Set-up Round Robin Archives (RRA):
        - day,week,month and year archives
        - 2 types : AVERAGE and MAX

        parameter : start time
        return    : last epoch recorded
        """
        ds_type = 'ABSOLUTE'
        rows = xpoints / points_per_sample
        realrows = int(rows * 1.1)    # ensure that the full range is covered
        day_steps = int(3600 * 24 / (rrdstep * rows))
        week_steps = day_steps * 7
        month_steps = week_steps * 5
        year_steps = month_steps * 12

        # Set up data sources for our RRD
        params = []
        for v in variables:
            params += ['DS:%s:%s:%s:0:U' % (v, ds_type, rrdstep * 2)]

        # Set up RRD to archive data
        for cf in ['AVERAGE', 'MAX']:
            for step in [day_steps, week_steps, month_steps, year_steps]:
                params += ['RRA:%s:0.5:%s:%s' % (cf, step, realrows)]

        # With those setup, we can now created the RRD
        rrdtool.create(str(fname),
                       '--start', str(m),
                       '--step', str(rrdstep),
                       *params)
        return m

    def update_rrd(self, dom, t):
        """update_rrd

        Update RRD with records at t time.

        True  : if data are up-to-date for current minute
        False : syslog may have probably been already recorded
        or something wrong
        """
        fname = "%s/%s.rrd" % (self.workdir, dom)
        m = t - (t % rrdstep)
        if not os.path.exists(fname):
            self.lupdates[fname] = self.init_rrd(fname, m)
            self._dprint("[rrd] create new RRD file %s" % fname)
        else:
            if fname not in self.lupdates:
                self.lupdates[fname] = rrdtool.last(str(fname))

        if m <= self.lupdates[fname]:
            if self.verbose:
                print "[rrd] VERBOSE events at %s already recorded in RRD" % m
            return False

        tpl = ""
        for v in variables:
            if tpl != "":
                tpl += ":"
            tpl += v
        # Missing some RRD steps
        # Est ce vraiment nécessaire... ?
        if m > self.lupdates[fname] + rrdstep:
            values = ""
            for v in variables:
                if values != "":
                    values += ":"
                values += "0"
            for p in range(self.lupdates[fname] + rrdstep, m, rrdstep):
                if self.verbose:
                    print "[rrd] VERBOSE update -t %s %s:%s (SKIP)" \
                        % (tpl, p, values)
                rrdtool.update(str(fname), "-t", tpl, "%s:%s" % (p, values))

        values = "%s" % m
        tpl = ""
        for v in variables:
            values += ":"
            values += str(self.data[dom][m][v])
            if tpl != "":
                tpl += ":"
            tpl += v
        if self.verbose:
            print "[rrd] VERBOSE update -t %s %s" % (tpl, values)

        rrdtool.update(str(fname), "-t", tpl, values)
        self.lupdates[fname] = m
        return True

    def initcounters(self, dom):
        init = {}
        for v in variables:
            init[v] = 0
        self.data[dom][self.cur_t] = init

    def inc_counter(self, dom, counter, val=1):
        if dom is not None and dom in self.domains:
            if self.cur_t not in self.data[dom]:
                self.initcounters(dom)
            self.data[dom][self.cur_t][counter] += val

        if self.cur_t not in self.data["global"]:
            self.initcounters("global")
        self.data["global"][self.cur_t][counter] += val

    def year(self, month):
        """Return the appropriate year

        Date used in log files don't always embark the year so we need
        to guess it :p

        This method tries to deal with year changes in a simply
        (ugly?) way: if we currently are in january and the given
        month is different, return the current year -1. Otherwise,
        return the current year.

        Obviously, this method only works for year to year + 1
        changes.

        :param month: the month of the current record beeing parsed
        :return: an integer
        """
        month = time.strptime(month, "%b").tm_mon if not month.isdigit() \
            else int(month)
        if self.curmonth == 1 and month != self.curmonth:
            return self.__year - 1
        return self.__year

    def _parse_line(self, line):
        """Parse a single log line.

        :param str line: log line
        """
        line = self._parse_date(line)
        if line is None:
            return
        m = self.line_expr.match(line)
        if not m:
            return
        host, prog, pid, log = m.groups()
        m = self._spam_detect_expr.search(log)
        if m is not None:
            domain = m.group("domain")
            spam_result = m.group("result")
            if domain is not None and domain in self.domains:
                if spam_result in self._virus_sigs:
                    self.inc_counter(domain, 'virus')
                elif spam_result in self._spam_sigs:
                    self.inc_counter(domain, 'spam')
                return
        m = self._id_expr.match(log)
        if m is None:
            self._dprint("Unknown line format: %s" % log)
            return
        (line_id, line_log) = m.groups()
        if line_id == "NOQUEUE":
            addrto = re.match(
                "reject: .*from=<.*> to=<[^@]+@([^>]+)>",
                line_log)
            if addrto and addrto.group(1) in self.domains:
                self.inc_counter(addrto.group(1), 'reject')
            return
        m = re.search("message-id=<([^>]*)>", line_log)
        if m is not None:
            self.workdict[line_id] = {'from': m.group(1), 'size': 0}
            return
        m = re.search(r"from=<([^>]*)>, size=(\d+)", line_log)
        if m is not None:
            self.workdict[line_id] = {
                'from': m.group(1), 'size': string.atoi(m.group(2))
            }
            return

        m = re.search(r"to=<([^>]*)>.*status=(\S+)", line_log)
        if m is not None:
            if line_id not in self.workdict:
                self._dprint("Inconsistent mail (%s: %s), skipping"
                             % (line_id, m.group(1)))
                return
            if not m.group(2) in variables:
                self._dprint("Unsupported status %s, skipping" % m.group(2))
                return
            addrfrom = re.match("([^@]+)@(.+)", self.workdict[line_id]['from'])
            if addrfrom is not None and addrfrom.group(2) in self.domains:
                self.inc_counter(addrfrom.group(2), 'sent')
                self.inc_counter(addrfrom.group(2), 'size_sent',
                                 self.workdict[line_id]['size'])
            addrto = re.match("([^@]+)@(.+)", m.group(1))
            domname = addrto.group(2) if addrto is not None else None
            if m.group(2) == "sent":
                self.inc_counter(domname, 'recv')
                self.inc_counter(domname, 'size_recv',
                                 self.workdict[line_id]['size'])
            else:
                self.inc_counter(domname, m.group(2))
            return
        self._dprint("Unknown line format: %s" % line_log)

    def process(self):
        """Process the log file.

        We parse it and then generate standard graphics (day, week,
        month).
        """
        for line in self.f.readlines():
            self._parse_line(line)

        for dom, data in self.data.iteritems():
            self._dprint("[rrd] dealing with domain %s" % dom)
            for t in sorted(data.keys()):
                self.update_rrd(dom, t)


class Command(BaseCommand):
    help = 'Log file parser'

    def add_arguments(self, parser):
        """Add extra arguments to command line."""
        parser.add_argument(
            "--logfile", default=None,
            help="postfix log in syslog format", metavar="FILE")
        parser.add_argument(
            "--verbose", default=False, action="store_true",
            dest="verbose", help="Set verbose mode")
        parser.add_argument(
            "--debug", default=False, action="store_true",
            help="Set debug mode")

    def handle(self, *args, **options):
        Stats().load()
        if options["logfile"] is None:
            options["logfile"] = param_tools.get_global_parameter(
                "logfile", app="modoboa_stats")
        p = LogParser(options, param_tools.get_global_parameter(
            "rrd_rootdir", app="modoboa_stats"))
        p.process()
