#####
Setup
#####

First, make sure ``rrdtool`` is installed on your server. By default,
Modoboa will try the following locations to find the binary::

  RRDTOOL_LOOKUP_PATH = ("/usr/bin/rrdtool", "/usr/local/bin/rrdtool", )

You can override this setting (:file:`settings.py`) if it does not
match your installation.

To use the extension, go to the online parameters panel and adapt the
following ones to your environment:

+--------------------+--------------------+--------------------------+
|Name                |Description         |Default value             |
+====================+====================+==========================+
|Path to the log file|Path to log file    |/var/log/mail.log         |
|                    |used to collect     |                          |
|                    |statistics          |                          |
+--------------------+--------------------+--------------------------+
|Directory to store  |Path to directory   |/tmp/modoboa              |
|RRD files           |where RRD files are |                          |
|                    |stored              |                          |
+--------------------+--------------------+--------------------------+

Make sure the directory that will contain RRD files exists. If not,
create it before going further. For example (according to the previous
parameters)::

  $ mkdir /tmp/modoboa

To finish, you need to collect information periodically in order to
feed the RRD files. Add the following lines into root's crontab::

  */5 * * * * <modoboa_site>/manage.py logparser &> /dev/null
  #
  # Or like this if you use a virtual environment:
  # */5 * * * * <virtualenv path/bin/python> <modoboa_site>/manage.py logparser &> /dev/null

  0 * * * * <modoboa_site>/manage.py update_statistics
  #
  # Or like this if you use a virtual environment:
  # 0 * * * * <virtualenv path/bin/python> <modoboa_site>/manage.py update_statistics

Replace ``<modoboa_site>`` with the path of your Modoboa instance.

Graphics will be automatically created after each parsing.
