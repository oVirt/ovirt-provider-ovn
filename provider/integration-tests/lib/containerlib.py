#
# Copyright 2018-2021 Red Hat, Inc.
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license

import os
import subprocess


CONTAINER_CLI = os.environ['CONTAINER_PLATFORM']


def get_container_ip(container_name):
    container_ip_command = [
        CONTAINER_CLI,
        'inspect',
        '-f',
        '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}',
        container_name,
    ]
    return (
        subprocess.check_output(container_ip_command, stderr=subprocess.STDOUT)
        .decode()
        .strip()
    )


def inner_ping(
    container_name,
    source_namespace,
    target_ip,
    expected_result=0,
    ip_version=4,
    data_size=56,
):
    command = [
        CONTAINER_CLI,
        'exec',
        container_name,
        'bash',
        '-c',
        'ip netns exec {ns} ping -{ip_version} -c 1 '
        '-M do -s {size} {ip}'.format(
            ns=source_namespace,
            ip_version=ip_version,
            size=data_size,
            ip=target_ip,
        ),
    ]
    result = subprocess.call(command)
    if result != expected_result:
        if expected_result == 0:
            reason = 'Connectivity issues'
        else:
            reason = 'Unexpected connectivity'
        raise Exception(reason)
    return result


def get_container_id_from_img_name(image_name):
    command = [
        CONTAINER_CLI,
        'ps',
        '-q',
        '--filter',
        'ancestor={img}'.format(img=image_name),
    ]
    return (
        subprocess.check_output(command, stderr=subprocess.STDOUT)
        .decode()
        .strip()
    )


def reconfigure_interface(container_name, target_namespace, interface_name):
    for status in ['down', 'up']:
        command = [
            CONTAINER_CLI,
            'exec',
            container_name,
            'bash',
            '-c',
            'ip netns exec {ns} ip link set {if_name} {status}'.format(
                ns=target_namespace, if_name=interface_name, status=status
            ),
        ]
        subprocess.call(command)
