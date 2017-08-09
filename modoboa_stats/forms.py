"""Modoboa stats forms."""

import rrdtool

from django.utils.translation import ugettext_lazy
from django import forms

from versionfield.constants import DEFAULT_NUMBER_BITS
from versionfield.version import Version

from modoboa.lib import form_utils
from modoboa.parameters import forms as param_forms


class ParametersForm(param_forms.AdminParametersForm):
    """Stats global parameters."""

    app = "modoboa_stats"

    general_sep = form_utils.SeparatorField(label=ugettext_lazy("General"))

    logfile = forms.CharField(
        label=ugettext_lazy("Path to the log file"),
        initial="/var/log/mail.log",
        help_text=ugettext_lazy("Path to log file used to collect statistics"),
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    rrd_rootdir = forms.CharField(
        label=ugettext_lazy("Directory to store RRD files"),
        initial="/tmp/modoboa",
        help_text=ugettext_lazy(
            "Path to directory where RRD files are stored"),
        widget=forms.TextInput(attrs={"class": "form-control"})
    )

    greylist = form_utils.YesNoField(
        label=ugettext_lazy("Show greylisted messages"),
        initial=False,
        help_text=ugettext_lazy(
            "Differentiate between hard and soft rejects (greylisting)")
    )

    def __init__(self, *args, **kwargs):
        """Check RRDtool version."""
        super(ParametersForm, self).__init__(*args, **kwargs)
        rrd_version = Version(rrdtool.lib_version(), DEFAULT_NUMBER_BITS)
        required_version = Version("1.6.0", DEFAULT_NUMBER_BITS)
        if rrd_version < required_version:
            del self.fields["greylist"]
