Installing Hypothesis on Fedora
###############################

To install the dependencies, run these commands:

.. code-block:: bash

    yum install nodejs npm python-{pip,virtualenv} rubygem-{compass,sass}
    yum install libyaml-devel

Make sure to install at least version 0.12.2 of rubygem-compass.
If not available as an RPM, you can use this:

.. code-block:: bash

    gem install compass

Follow the instructions at elastisearch_rpm_ to build and install the elasticsearch server,
but don't start it just yet:

Before you start the elasticsearch daemon:

 - Edit the /etc/init.d/elasticsearch script and insert the following line
   at the beginning of the script (before it sources /etc/rc.d/init.d/functions):

.. code-block:: bash

     SYSTEMCTL_SKIP_REDIRECT=1

 - In /usr/share/elasticsearch/bin/elasticsearch.in.sh,
    comment out the javaopts that reduces the per-thread stack:

.. code-block:: bash

     #JAVA_OPTS="$JAVA_OPTS -Xss128k"

After installing the above, create the virtualenv,
as described in the INSTALL.rst

(Run the commands from the directory where you've cloned the repository.)

.. _elasticsearch_rpm: https://github.com/tavisto/elasticsearch-rpms
