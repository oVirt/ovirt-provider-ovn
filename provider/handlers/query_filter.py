# Copyright 2018 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#


def filter_query_results(response, query, path_parts):
    return {response.keys()[0]:
        filter(
            lambda e: all(
                map(
                    lambda (k, v): _compare_query_values( # noqa E999
                        e.get(k), v[0]
                    ),
                    query.items()
                )
            ),
            response.values()[0]
        )
    } if _should_be_filtered(response, query, path_parts) else response


def _should_be_filtered(response, query, path_parts):
    return (
        query and response and len(response.values()) == 1 and
        len(path_parts) == 1 and isinstance(response.values()[0], list)
    )


def _compare_query_values(entity_value, query_value):
    if isinstance(entity_value, bool):
        return str(entity_value).lower() == query_value.lower()
    return entity_value == query_value
