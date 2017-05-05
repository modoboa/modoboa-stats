"""Modoboa stats forms."""

from django.utils.translation import ugettext_lazy
from django import forms

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

    spam_detection = forms.ChoiceField(
        label=ugettext_lazy("Spam detection software"),
        choices=[("amavis", "Amavis"),
                 ("rmilter", "Rmilter/Rspamd")],
        initial="amavis",
        help_text=ugettext_lazy("Anti-spam software used"),
        widget=forms.Select(attrs={"class": "form-control"})
    )
