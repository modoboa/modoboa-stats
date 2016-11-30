# coding: utf-8

"""
Graphical statistics about emails traffic using RRDtool.

This module provides support to retrieve statistics from postfix log :
sent, received, bounced, rejected

"""
from django.utils.translation import ugettext_lazy

from modoboa.core.extensions import ModoExtension, exts_pool
from modoboa.parameters import tools as param_tools

from . import __version__
from . import forms


class Stats(ModoExtension):
    name = "modoboa_stats"
    label = "Statistics"
    version = __version__
    description = ugettext_lazy(
        "Graphical statistics about emails traffic using RRDtool"
    )
    needs_media = True
    url = "stats"

    def load(self):
        param_tools.registry.add(
            "global", forms.ParametersForm,
            ugettext_lazy("Graphical statistics"))

exts_pool.register_extension(Stats)
