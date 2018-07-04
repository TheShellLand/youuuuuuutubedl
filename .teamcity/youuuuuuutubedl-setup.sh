#!/bin/bash

cd $(dirname $0)

venv="youuuuuuutubedl"

pip3 install --user virtualenv \
&& python3 -m virtualenv $venv \
&& source $venv/bin/activate \
&& pip3 install bs4 \
&& pip3 install requests \
&& echo "" \
&& echo "Activate virtualenv by running the following:" \
&& echo -e "\n" \
        "\tsource $(pwd)/$(ls */bin/activate)\n" \
        "\tpython3 $(pwd)/$(ls */bin/python3)\n" \
&& echo -e "$(pwd)/$(ls */bin/activate)" > activate.txt \
&& echo -e "$(pwd)/$(ls */bin/python3)" >> activate.txt
