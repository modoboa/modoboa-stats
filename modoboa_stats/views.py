# coding: utf-8

"""Custom views."""

import re
import time

from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import (
    login_required, user_passes_test, permission_required
)

from modoboa.admin.models import Domain
from modoboa.lib import events
from modoboa.lib.exceptions import BadRequest, PermDeniedException, NotFound
from modoboa.lib.web_utils import (
    render_to_json_response
)

from .lib import date_to_timestamp


@login_required
@permission_required("admin.view_mailboxes")
def index(request):
    """
    FIXME: how to select a default graph set ?
    """
    deflocation = "graphs/?gset=mailtraffic"
    if not request.user.is_superuser:
        if not Domain.objects.get_for_admin(request.user).count():
            raise NotFound(_("No statistics available"))

    graph_sets = events.raiseDictEvent('GetGraphSets')
    periods = [
        {"name": "day", "label": _("Day")},
        {"name": "week", "label": _("Week")},
        {"name": "month", "label": _("Month")},
        {"name": "year", "label": _("Year")},
        {"name": "custom", "label": _("Custom")}
    ]
    return render(request, 'modoboa_stats/index.html', {
        "periods": periods,
        "selection": "stats",
        "deflocation": deflocation,
        "graph_sets": graph_sets
    })


def check_domain_access(user, pattern):
    """Check if an administrator can access a domain.

    If a non super administrator asks for the global view, we give him
    a view on the first domain he manage instead.

    :return: a domain name (str) or None.
    """
    if pattern in [None, "global"]:
        if not user.is_superuser:
            domains = Domain.objects.get_for_admin(user)
            if not domains.exists():
                return None
            return domains.first().name
        return "global"

    results = Domain.objects.filter(name__startswith=pattern)
    if results.count() != 1:
        return None
    if not user.can_access(results.first()):
        raise PermDeniedException
    return results.first().name


@login_required
@user_passes_test(lambda u: u.group != "SimpleUsers")
def graphs(request):
    gset = request.GET.get("gset", None)
    gsets = events.raiseDictEvent("GetGraphSets")
    if gset not in gsets:
        raise NotFound(_("Unknown graphic set"))
    searchq = request.GET.get("searchquery", None)
    period = request.GET.get("period", "day")
    tplvars = dict(graphs={}, period=period)
    domain = check_domain_access(request.user, searchq)
    if domain is None:
        return render_to_json_response({})
    tplvars["domain"] = domain

    if period == "custom":
        if "start" not in request.GET or "end" not in request.GET:
            raise BadRequest(_("Bad custom period"))
        start = request.GET["start"]
        end = request.GET["end"]
        expr = re.compile(r'[:\- ]')
        period_name = "%s_%s" % (expr.sub('', start), expr.sub('', end))
        start = date_to_timestamp(expr.split(start))
        end = date_to_timestamp(expr.split(end))
    else:
        end = int(time.mktime(time.localtime()))
        start = "-1%s" % period
        period_name = period

    tplvars["graphs"] = gsets[gset].export(tplvars["domain"], start, end)
    tplvars["period_name"] = period_name
    tplvars["start"] = start
    tplvars["end"] = end

    return render_to_json_response(tplvars)


@login_required
@user_passes_test(lambda u: u.group != "SimpleUsers")
def get_domain_list(request):
    """Get the list of domains the user can see."""
    doms = [dom.name for dom in Domain.objects.get_for_admin(request.user)]
    return render_to_json_response(doms)
