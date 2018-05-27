#!/bin/bash

# fine I'll do it this way

cd $(dirname $0)

venv="youuuuuuutubedl"

pip3 install --user virtualenv \
&& python3 -m virtualenv $venv \
&& source $venv/bin/activate \
&& pip3 install bs4 \
&& pip3 install requests \
&& echo "" \
&& echo "Activate virtualenv by running the following:" \
&& echo -e "\n    " \
        "source $(ls */bin/activate)\n"
