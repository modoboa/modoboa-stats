"""General callbacks events."""

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from modoboa.lib import events

from .graphics import MailTraffic


@events.observe("UserMenuDisplay")
def menu(target, user):
    if target != "top_menu" or user.group == "SimpleUsers":
        return []
    return [
        {"name": "stats",
         "label": _("Statistics"),
         "url": reverse('modoboa_stats:fullindex')}
    ]


@events.observe("GetGraphSets")
def get_default_graphic_sets():
    gset = MailTraffic()
    return {gset.html_id: gset}
